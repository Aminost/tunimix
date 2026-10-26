"""Telegram bot: share a recipe link / dish name / photo from your phone,
get the Thermomix version back, tap to push it to Cookidoo.

Setup: create a bot with @BotFather, put TELEGRAM_BOT_TOKEN in .env, and
TELEGRAM_ALLOWED_USER_IDS=<your numeric id> (send /id to the bot to see it).
Run:   tunimix bot
"""
from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

from ..config import settings
from ..library import Library
from ..outputs.text import to_copy_paste, to_markdown

log = logging.getLogger(__name__)
lib = Library()

HELP = (
    "Schick mir:\n"
    "• einen Rezept-Link (jede Webseite, YouTube)\n"
    "• einen Gerichtnamen, z. B. „Kafteji“\n"
    "• ein Foto oder PDF (auch handgeschriebene Familienrezepte)\n"
    "• oder einen ganzen Rezepttext\n\n"
    "Ich wandle es in ein Thermomix-Rezept um. Mit ☁ landet es in Cookidoo.\n\n"
    "Befehle: /list · /book (PDF-Kochbuch) · /uploadall · /seeds · /id"
)


def _allowed(update) -> bool:
    uid = update.effective_user.id if update.effective_user else 0
    return not settings.telegram_allowed_users or uid in settings.telegram_allowed_users


def _summary(r) -> str:
    lines = [f"✅ *{r.title}*", f"{r.servings} {r.unit_text} · {r.total_time_min} Min. · {len(r.steps)} Schritte · {r.machine}"]
    if r.cookidoo_url:
        lines.append(f"☁ In Cookidoo: {r.cookidoo_url}")
    if r.warnings:
        lines.append("⚠️ " + " · ".join(r.warnings[:4]))
    return "\n".join(lines)


def _buttons(slug: str):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("☁ Zu Cookidoo", callback_data=f"up:{slug}"),
        InlineKeyboardButton("📄 PDF", callback_data=f"pdf:{slug}"),
    ], [
        InlineKeyboardButton("📝 Rezept anzeigen", callback_data=f"md:{slug}"),
        InlineKeyboardButton("📋 Copy-Paste", callback_data=f"txt:{slug}"),
    ]])


async def _reply_recipe(msg, r):
    await msg.reply_text(_summary(r), parse_mode="Markdown", reply_markup=_buttons(r.slug),
                         disable_web_page_preview=True)


async def start(update, context):
    await update.message.reply_text(HELP)


async def my_id(update, context):
    await update.message.reply_text(f"Deine Telegram-ID: {update.effective_user.id}")


async def on_text(update, context):
    if not _allowed(update):
        return
    from ..pipeline import process
    value = update.message.text.strip()
    note = await update.message.reply_text("⏳ Wandle um … (20–60 Sek.)")
    try:
        r = await asyncio.to_thread(process, value, None, lib)
        await _reply_recipe(update.message, r)
    except Exception as exc:
        await update.message.reply_text(f"❌ {type(exc).__name__}: {exc}")
    finally:
        await note.delete()


async def on_file(update, context):
    if not _allowed(update):
        return
    from ..pipeline import process_bytes
    msg = update.message
    if msg.photo:
        tg_file = await msg.photo[-1].get_file()
        name = "foto.jpg"
    else:
        tg_file = await msg.document.get_file()
        name = msg.document.file_name or "datei.pdf"
    data = bytes(await tg_file.download_as_bytearray())
    note = await msg.reply_text("⏳ Lese das Rezept … (30–90 Sek.)")
    try:
        r = await asyncio.to_thread(process_bytes, data, name, None, lib)
        await _reply_recipe(msg, r)
    except Exception as exc:
        await msg.reply_text(f"❌ {type(exc).__name__}: {exc}")
    finally:
        await note.delete()


async def on_button(update, context):
    q = update.callback_query
    await q.answer()
    if not _allowed(update):
        return
    action, slug = q.data.split(":", 1)
    r = lib.get(slug)
    if action == "up":
        from ..outputs.cookidoo import upload_many
        try:
            r = (await upload_many([r]))[0]
            lib.save(r)
            await q.message.reply_text(f"☁ Gespeichert: {r.cookidoo_url}\nAm Thermomix unter Meine Kreationen.")
        except Exception as exc:
            await q.message.reply_text(f"❌ Upload fehlgeschlagen: {exc}")
    elif action == "pdf":
        from ..outputs.pdf import build_pdf
        path = Path(tempfile.mkdtemp()) / f"{slug}.pdf"
        await asyncio.to_thread(build_pdf, [r], path, r.title)
        await q.message.reply_document(path.open("rb"), filename=path.name)
    elif action == "md":
        text = to_markdown(r)
        for i in range(0, len(text), 3900):
            await q.message.reply_text(text[i:i + 3900])
    elif action == "txt":
        await q.message.reply_text(to_copy_paste(r)[:4000])


async def cmd_list(update, context):
    if not _allowed(update):
        return
    rs = lib.all()
    text = "\n".join(f"{'☁' if r.cookidoo_id else '•'} {r.title}" for r in rs) or "Noch leer – /seeds lädt Basisrezepte."
    await update.message.reply_text(text[:4000])


async def cmd_book(update, context):
    if not _allowed(update):
        return
    from ..outputs.pdf import build_pdf
    path = Path(tempfile.mkdtemp()) / "kochbuch.pdf"
    await asyncio.to_thread(build_pdf, lib.all(), path)
    await update.message.reply_document(path.open("rb"), filename="Tunesisches-Thermomix-Kochbuch.pdf")


async def cmd_upload_all(update, context):
    if not _allowed(update):
        return
    from ..outputs.cookidoo import upload_many
    todo = [r for r in lib.all() if not r.cookidoo_id]
    await update.message.reply_text(f"☁ Lade {len(todo)} Rezept(e) hoch …")
    try:
        await upload_many(todo, on_done=lib.save)
        await update.message.reply_text("✅ Fertig.")
    except Exception as exc:
        await update.message.reply_text(f"❌ {exc}")


async def cmd_seeds(update, context):
    if not _allowed(update):
        return
    await update.message.reply_text(f"{lib.import_seeds()} Rezept(e) geladen.")


def run():
    from telegram.ext import (ApplicationBuilder, CallbackQueryHandler, CommandHandler,
                              MessageHandler, filters)
    if not settings.telegram_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN missing in .env")
    if not settings.telegram_allowed_users:
        print("⚠  TELEGRAM_ALLOWED_USER_IDS is empty – anyone who finds the bot can use it.")
    app = ApplicationBuilder().token(settings.telegram_token).build()
    app.add_handler(CommandHandler(["start", "help"], start))
    app.add_handler(CommandHandler("id", my_id))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("book", cmd_book))
    app.add_handler(CommandHandler("uploadall", cmd_upload_all))
    app.add_handler(CommandHandler("seeds", cmd_seeds))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, on_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    print("TuniMix bot running – send it a recipe link.")
    app.run_polling()

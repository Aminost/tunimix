/* TuniMix bookmarklet. The APP placeholder is replaced with the app URL when the button is built.
   On a recipe page  -> captures the recipe (schema.org data or visible text) and opens TuniMix.
   On cookidoo.*     -> saves recipes converted in TuniMix into "Created recipes" with the
                        user's own logged-in session (no password ever leaves the browser). */
(function () {
  var APP = "__APP__";
  var APP_ORIGIN = new URL(APP).origin;
  var host = location.hostname;
  var IS_COOKIDOO = /(^|\.)cookidoo\.[a-z.]+$/.test(host) || /(^|\.)cookidoo\.thermomix\.com$/.test(host);
  var T = {
    de: { capture: "Rezept wird an TuniMix gesendet …", blocked: "Pop-up blockiert. Erlaube Pop-ups für diese Seite und klicke erneut.",
      sent: "Gesendet ✓ – im TuniMix-Fenster weitermachen.", title: "TuniMix → Cookidoo", wait: "Hole Rezepte aus TuniMix …",
      paste: "Oder den Cookidoo-Code aus TuniMix hier einfügen:", go: "In Cookidoo speichern", none: "Keine Rezepte in der Warteschlange.",
      login: "Bitte zuerst bei Cookidoo anmelden und die Seite neu laden.", saving: "Speichere", done: "Gespeichert ✓ – am Thermomix unter „Meine Kreationen“.",
      open: "öffnen", fail: "Fehler", close: "Schließen", locale: "Cookidoo-Sprache nicht erkannt. Öffne cookidoo.de (bzw. dein Land) und klicke erneut." },
    en: { capture: "Sending recipe to TuniMix …", blocked: "Pop-up blocked. Allow pop-ups for this site and click again.",
      sent: "Sent ✓ – continue in the TuniMix window.", title: "TuniMix → Cookidoo", wait: "Fetching recipes from TuniMix …",
      paste: "Or paste the Cookidoo code from TuniMix here:", go: "Save to Cookidoo", none: "No recipes in the queue.",
      login: "Please log in to Cookidoo first and reload the page.", saving: "Saving", done: "Saved ✓ – on the Thermomix under “Created recipes”.",
      open: "open", fail: "Error", close: "Close", locale: "Cookidoo language not detected. Open your Cookidoo site and click again." },
    fr: { capture: "Envoi de la recette à TuniMix …", blocked: "Pop-up bloquée. Autorisez les pop-ups pour ce site et recliquez.",
      sent: "Envoyé ✓ – continuez dans la fenêtre TuniMix.", title: "TuniMix → Cookidoo", wait: "Récupération des recettes TuniMix …",
      paste: "Ou collez ici le code Cookidoo de TuniMix :", go: "Enregistrer dans Cookidoo", none: "Aucune recette en attente.",
      login: "Connectez-vous d'abord à Cookidoo puis rechargez la page.", saving: "Enregistrement", done: "Enregistré ✓ – sur le Thermomix dans « Mes créations ».",
      open: "ouvrir", fail: "Erreur", close: "Fermer", locale: "Langue Cookidoo non détectée. Ouvrez votre site Cookidoo et recliquez." },
  };
  var lang = (navigator.language || "de").slice(0, 2);
  var t = T[lang] || T[lang === "ar" ? "fr" : "de"] || T.de;

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  function panel() {
    var old = document.getElementById("tunimix-panel");
    if (old) old.remove();
    var host = document.createElement("div");
    host.id = "tunimix-panel";
    host.style.cssText = "position:fixed;z-index:2147483647;right:16px;bottom:16px;max-width:380px;width:calc(100% - 32px)";
    var root = host.attachShadow({ mode: "open" });
    root.innerHTML = '<style>*{box-sizing:border-box}.p{font:14px/1.5 system-ui,sans-serif;background:#fff;color:#14213a;border:2px solid #1b5fae;border-radius:14px;padding:14px 16px;box-shadow:0 10px 30px rgba(0,0,0,.25)}' +
      'h3{margin:0 0 6px;font-size:16px;color:#1b5fae}button{font:600 14px system-ui;border-radius:9px;padding:8px 12px;border:1px solid #1b5fae;cursor:pointer;background:#1b5fae;color:#fff;margin-top:8px}' +
      'button.s{background:#fff;color:#1b5fae}textarea{width:100%;min-height:70px;margin-top:6px;border:1px solid #ccd6e6;border-radius:8px;font:12px monospace;padding:6px}' +
      'a{color:#1b5fae;font-weight:600}.x{float:right;background:none;border:none;color:#5b6780;font-size:20px;margin:0;padding:0 4px}.ok{color:#2e7d32}.er{color:#c8341f}ul{padding-left:18px;margin:6px 0}</style>' +
      '<div class="p"><button class="x" aria-label="' + t.close + '">×</button><h3>TuniMix</h3><div class="b"></div></div>';
    root.querySelector(".x").onclick = function () { host.remove(); };
    document.body.appendChild(host);
    return { body: root.querySelector(".b"), root: root };
  }

  /* ---------------- capture mode: any recipe page ---------------- */
  function findRecipe(node) {
    if (!node || typeof node !== "object") return null;
    if (Array.isArray(node)) { for (var i = 0; i < node.length; i++) { var f = findRecipe(node[i]); if (f) return f; } return null; }
    var ty = node["@type"]; var types = Array.isArray(ty) ? ty : [ty];
    if (types.indexOf("Recipe") >= 0) return node;
    return findRecipe(node["@graph"]) || findRecipe(node.mainEntity) || null;
  }
  function capture() {
    var ui = panel();
    ui.body.textContent = t.capture;
    var recipe = null;
    document.querySelectorAll('script[type="application/ld+json"]').forEach(function (s) {
      if (recipe) return;
      try { recipe = findRecipe(JSON.parse(s.textContent)); } catch (e) {}
    });
    var meta = function (p) { var m = document.querySelector('meta[property="' + p + '"],meta[name="' + p + '"]'); return m ? m.content : ""; };
    var main = document.querySelector("article") || document.querySelector("main") || document.body;
    var data = {
      type: "tunimix-capture", url: location.href, title: document.title,
      description: meta("og:description") || meta("description"), image: meta("og:image"),
      jsonld: recipe ? JSON.stringify(recipe).slice(0, 60000) : "",
      text: recipe ? "" : (main.innerText || "").slice(0, 40000),
    };
    var w = window.open(APP + "#capture", "tunimix");
    if (!w) { ui.body.textContent = t.blocked; return; }
    var acked = false, tries = 0;
    window.addEventListener("message", function (ev) {
      if (ev.origin === APP_ORIGIN && ev.data && ev.data.type === "tunimix-capture-ack") { acked = true; ui.body.textContent = t.sent; }
    });
    var timer = setInterval(function () {
      if (acked || ++tries > 60) return clearInterval(timer);
      try { w.postMessage(data, APP_ORIGIN); } catch (e) {}
    }, 400);
  }

  /* ---------------- import mode: on cookidoo ---------------- */
  var HOST_LOCALE = { "cookidoo.de": "de-DE", "cookidoo.at": "de-AT", "cookidoo.ch": "de-CH", "cookidoo.fr": "fr-FR", "cookidoo.be": "fr-BE",
    "cookidoo.lu": "fr-LU", "cookidoo.it": "it-IT", "cookidoo.es": "es-ES", "cookidoo.pt": "pt-PT", "cookidoo.co.uk": "en-GB", "cookidoo.pl": "pl-PL",
    "cookidoo.nl": "nl-NL", "cookidoo.thermomix.com": "en-US", "cookidoo.international": "en", "cookidoo.com.au": "en-AU", "cookidoo.mx": "es-MX" };
  function localeCandidates() {
    var c = [];
    var m = location.pathname.match(/^\/[a-z-]+\/([a-z]{2}(?:-[A-Z]{2})?)(\/|$)/);
    if (m) c.push(m[1]);
    var l = document.documentElement.lang;
    if (l) c.push(l.length === 2 ? l : l.slice(0, 2).toLowerCase() + "-" + l.slice(3).toUpperCase());
    var h = host.replace(/^www\./, "");
    if (HOST_LOCALE[h]) c.push(HOST_LOCALE[h]);
    return c.filter(function (x, i) { return x && c.indexOf(x) === i; });
  }
  function findBase() {
    var cands = localeCandidates();
    var i = 0;
    function next() {
      if (i >= cands.length) return Promise.reject(new Error("locale"));
      var base = location.origin + "/created-recipes/" + cands[i++];
      return fetch(base, { headers: { Accept: "application/json" }, credentials: "include", redirect: "manual" }).then(function (r) {
        var ct = r.headers.get("content-type") || "";
        if (r.status === 401 || r.status === 403) throw new Error("login");
        if (r.ok && ct.indexOf("json") >= 0) return base;
        return next();
      }, next);
    }
    return next();
  }
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function saveOne(base, item) {
    var headers = { "Content-Type": "application/json", Accept: "application/json" };
    return fetch(base, { method: "POST", headers: headers, credentials: "include", body: JSON.stringify({ recipeName: item.payload.name }) })
      .then(function (r) {
        if (r.status === 401 || r.status === 403) throw new Error("login");
        if (!r.ok) return r.text().then(function (x) { throw new Error("create " + r.status + " " + x.slice(0, 200)); });
        return r.json();
      }).then(function (j) {
        var id = j.recipeId;
        return fetch(base + "/" + id, { method: "PATCH", headers: headers, credentials: "include", body: JSON.stringify(item.payload) })
          .then(function (r) {
            if (!r.ok) return r.text().then(function (x) { throw new Error("update " + r.status + " " + x.slice(0, 200)); });
            return base + "/" + id + "/edit";
          });
      });
  }
  function runImport(ui, items, bridge) {
    if (!items.length) { ui.body.innerHTML = esc(t.none); return showPaste(ui); }
    var list = document.createElement("ul");
    ui.body.innerHTML = "";
    ui.body.appendChild(list);
    var done = [];
    findBase().then(function (base) {
      var chain = Promise.resolve();
      items.forEach(function (it, n) {
        chain = chain.then(function () {
          var li = document.createElement("li");
          li.textContent = t.saving + ": " + it.payload.name + " …";
          list.appendChild(li);
          return (n ? sleep(9000) : Promise.resolve()).then(function () { return saveOne(base, it); }).then(function (url) {
            li.innerHTML = '<span class="ok">✓</span> ' + esc(it.payload.name) + ' – <a href="' + esc(url) + '" target="_blank" rel="noopener">' + t.open + "</a>";
            if (it.id) done.push(it.id);
          }, function (err) {
            li.innerHTML = '<span class="er">✗</span> ' + esc(it.payload.name) + ": " + esc(err.message === "login" ? t.login : err.message);
            if (err.message === "login") throw err;
          });
        });
      });
      return chain;
    }).then(function () {
      var p = document.createElement("p"); p.className = "ok"; p.textContent = t.done; ui.body.appendChild(p);
    }, function (err) {
      var p = document.createElement("p"); p.className = "er";
      p.textContent = err.message === "login" ? t.login : err.message === "locale" ? t.locale : t.fail + ": " + err.message;
      ui.body.appendChild(p);
    }).then(function () {
      if (bridge && done.length) try { bridge.postMessage({ type: "tunimix-done", ids: done }, APP_ORIGIN); } catch (e) {}
    });
  }
  function parseCode(text) {
    var data = JSON.parse(text.trim());
    var arr = Array.isArray(data) ? data : [data];
    return arr.map(function (x) { return x.payload ? x : { payload: x }; }).filter(function (x) { return x.payload && x.payload.name && x.payload.instructions; });
  }
  function showPaste(ui) {
    var wrap = document.createElement("div");
    wrap.innerHTML = '<div style="margin-top:8px">' + esc(t.paste) + '</div><textarea aria-label="code"></textarea><button>' + esc(t.go) + "</button>";
    ui.body.appendChild(wrap);
    wrap.querySelector("button").onclick = function () {
      try { runImport(ui, parseCode(wrap.querySelector("textarea").value), null); }
      catch (e) { alert(t.fail + ": " + e.message); }
    };
  }
  function importMode() {
    var ui = panel();
    ui.root.querySelector("h3").textContent = t.title;
    ui.body.textContent = t.wait;
    var bridge = window.open(APP + "bridge.html", "tunimix-bridge", "width=420,height=300");
    if (!bridge) { ui.body.textContent = ""; return showPaste(ui); }
    var got = false, tries = 0;
    window.addEventListener("message", function (ev) {
      if (ev.origin !== APP_ORIGIN || !ev.data || ev.data.type !== "tunimix-queue" || got) return;
      got = true;
      runImport(ui, ev.data.items || [], bridge);
    });
    var timer = setInterval(function () {
      if (got) return clearInterval(timer);
      if (++tries > 25) { clearInterval(timer); ui.body.textContent = ""; showPaste(ui); return; }
      try { bridge.postMessage({ type: "tunimix-hello" }, APP_ORIGIN); } catch (e) {}
    }, 300);
  }

  if (IS_COOKIDOO) importMode(); else capture();
})();

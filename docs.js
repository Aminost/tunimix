// Reads recipe files in the browser with open-source libraries (loaded on demand from CDNs):
//   PDF   -> pdf.js (text; scanned pages are rendered and OCR'd)
//   Word  -> mammoth.js (text, lists, tables, first embedded photo)
//   Photo -> tesseract.js (OCR in German, French, English, Arabic)
// Nothing is uploaded anywhere: files are processed on the user's device.
const LIBS = {
  pdf: "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js",
  pdfWorker: "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js",
  mammoth: "https://cdn.jsdelivr.net/npm/mammoth@1.8.0/mammoth.browser.min.js",
  tesseract: "https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js",
};
const loaded = {};
function load(src) {
  return loaded[src] ||= new Promise((ok, fail) => {
    const s = document.createElement("script");
    s.src = src; s.onload = ok; s.onerror = () => fail(new Error(`Could not load ${src.split("/").slice(-1)[0]} – check your internet connection.`));
    document.head.appendChild(s);
  });
}

function b64ToBytes(b64) { return Uint8Array.from(atob(b64), (c) => c.charCodeAt(0)); }

export function ocrLangs(uiLang = "de") {
  const set = ["deu", "fra", "eng"];
  if (uiLang === "ar") set.push("ara");
  return set.join("+");
}

async function ocr(images, langs, onStatus) {
  await load(LIBS.tesseract);
  const worker = await window.Tesseract.createWorker(langs, 1, {
    logger: (m) => { if (m.status === "recognizing text") onStatus?.("ocr", Math.round(m.progress * 100)); },
  });
  try {
    let text = "";
    for (const img of images) text += (await worker.recognize(img)).data.text + "\n";
    return text;
  } finally { await worker.terminate(); }
}

async function readPdf(bytes, langs, onStatus) {
  await load(LIBS.pdf);
  const pdfjs = window.pdfjsLib;
  pdfjs.GlobalWorkerOptions.workerSrc = LIBS.pdfWorker;
  const doc = await pdfjs.getDocument({ data: bytes }).promise;
  let text = "";
  for (let p = 1; p <= Math.min(doc.numPages, 15); p++) {
    const page = await doc.getPage(p);
    const content = await page.getTextContent();
    let lastY = null;
    for (const it of content.items) {           // keep line breaks: a new y position = a new line
      const y = it.transform?.[5];
      if (lastY !== null && Math.abs(y - lastY) > 2) text += "\n";
      text += it.str;
      lastY = y;
    }
    text += "\n";
  }
  if (text.trim().length >= 80) return { text, images: [] };
  const canvases = [];                          // scanned PDF -> render pages, then OCR
  for (let p = 1; p <= Math.min(doc.numPages, 6); p++) {
    const page = await doc.getPage(p);
    const vp = page.getViewport({ scale: 2.5 });
    const c = document.createElement("canvas");
    c.width = vp.width; c.height = vp.height;
    await page.render({ canvasContext: c.getContext("2d"), viewport: vp }).promise;
    canvases.push(c);
  }
  return { text: await ocr(canvases, langs, onStatus), images: [], ocr: true };
}

async function readDocx(bytes) {
  await load(LIBS.mammoth);
  const images = [];
  const result = await window.mammoth.convertToHtml({ arrayBuffer: bytes.buffer }, {
    convertImage: window.mammoth.images.imgElement(async (image) => {
      const b64 = await image.read("base64");
      const src = `data:${image.contentType};base64,${b64}`;
      images.push({ src, size: b64.length });
      return { src: "" };
    }),
  });
  const doc = new DOMParser().parseFromString(result.value, "text/html");
  const lines = [];
  let title = "";
  doc.body.querySelectorAll("h1,h2,h3,h4,p,li,tr").forEach((el) => {
    if (el.tagName === "P" && el.closest("li,td")) return;
    let t = el.tagName === "TR" ? [...el.querySelectorAll("td,th")].map((c) => c.textContent.trim()).filter(Boolean).join(" ") : el.textContent.trim();
    if (!t) return;
    if (!title && el.tagName === "H1") title = t;
    if (el.tagName === "LI" && t.length < 70) t = "- " + t;
    lines.push(t);
  });
  images.sort((a, b) => b.size - a.size);
  return { text: lines.join("\n"), title, images: images.slice(0, 1).map((i) => i.src) };
}

/** file: {name, mime, base64} -> {text, title, images: [dataURL], ocr} */
export async function readFile(file, { uiLang = "de", onStatus } = {}) {
  const name = (file.name || "").toLowerCase();
  const bytes = b64ToBytes(file.base64);
  if (file.mime === "application/pdf" || name.endsWith(".pdf")) return readPdf(bytes, ocrLangs(uiLang), onStatus);
  if (name.endsWith(".docx") || file.mime.includes("wordprocessingml")) return readDocx(bytes);
  if (name.endsWith(".doc")) throw new Error("Old .doc files: save as .docx and try again.");
  if (name.endsWith(".txt") || name.endsWith(".md") || file.mime.startsWith("text/")) return { text: new TextDecoder().decode(bytes), images: [] };
  if (file.mime.startsWith("image/")) {
    const blob = new Blob([bytes], { type: file.mime });
    return { text: await ocr([blob], ocrLangs(uiLang), onStatus), images: [], ocr: true };
  }
  throw new Error(`Unsupported file: ${file.name}`);
}

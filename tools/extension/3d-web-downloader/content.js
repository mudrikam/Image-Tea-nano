// 3D Web Downloader — content script
// Scans the active page for 3D asset URLs and reports them to the side panel.
(() => {
  if (window.__TWD_CONTENT__) return;
  window.__TWD_CONTENT__ = true;

  const EXT_PATTERN = /\.(glb|gltf|usdz)(\?|#|$)/i;

  const seen = new Set();
  let nextId = 1;

  function absolutize(src) {
    if (!src) return null;
    const s = String(src).trim().replace(/&amp;/g, "&");
    if (!s) return null;
    if (/^(data|blob|chrome-extension|about):/i.test(s)) return null;
    try { return new URL(s, location.href).href; } catch { return null; }
  }

  function filenameFromUrl(raw) {
    try {
      const u = new URL(raw, location.href);
      const path = u.pathname.split("/").pop() || "";
      const clean = path.split("?")[0].split("#")[0];
      if (clean && /\.(glb|gltf|usdz)$/i.test(clean)) return clean;
      const ext = (u.pathname.match(/\.(glb|gltf|usdz)/i) || [, ""])[1];
      return `model.${ext || "bin"}`;
    } catch {
      return "model.bin";
    }
  }

  function classifyKind(url) {
    const m = url.toLowerCase().match(/\.(glb|gltf|usdz)(\?|#|$)/);
    if (!m) return { ext: "bin", kind: "unknown", previewable: false, label: "Unknown" };
    const ext = m[1];
    if (ext === "glb") return { ext, kind: "model", previewable: true, label: "GLB" };
    if (ext === "gltf") return { ext, kind: "model", previewable: true, label: "glTF" };
    return { ext, kind: "model", previewable: false, label: "USDZ" };
  }

  function describeSize(url) {
    try {
      const u = new URL(url, location.href);
      if (u.pathname.toLowerCase().endsWith(".gltf")) {
        const base = u.pathname.replace(/\.gltf$/i, "");
        return { kind: "scene+bin", related: [`${base}.bin`] };
      }
    } catch {}
    return { kind: "single", related: [] };
  }

  function push(rawUrl, source) {
    const url = absolutize(rawUrl);
    if (!url) return;
    if (seen.has(url)) return;
    if (!EXT_PATTERN.test(url)) return;
    seen.add(url);
    const cls = classifyKind(url);
    const size = describeSize(url);
    send({
      id: `twd-${Date.now()}-${nextId++}`,
      url,
      filename: filenameFromUrl(url),
      ext: cls.ext,
      kind: cls.kind,
      label: cls.label,
      previewable: cls.previewable,
      size: size.kind,
      related: size.related,
      source,
      origin: location.host,
      foundAt: Date.now(),
    });
  }

  function send(asset) {
    try {
      chrome.runtime.sendMessage({ type: "TWD_ASSET_FOUND", asset }, () => void chrome.runtime.lastError);
    } catch {}
  }

  // Find all candidate 3D URLs anywhere in a chunk of HTML/text.
  // Catches: relative hrefs ("/foo/bar.usdz"), absolute URLs, encoded forms,
  // quoted inside JSON / template strings / HTML attributes.
  const URL_REGEX = /(?:https?:\/\/[^\s"'<>)]+|\/[A-Za-z0-9_\-./]+\.(?:glb|gltf|usdz)(?:\?[^\s"'<>)]*)?)/gi;
  function scanText(text, source) {
    if (!text) return;
    let m;
    URL_REGEX.lastIndex = 0;
    while ((m = URL_REGEX.exec(text)) !== null) {
      const candidate = m[0];
      // Quick filter: must look like our extensions
      if (!/\.(glb|gltf|usdz)(\?|#|$)/i.test(candidate)) continue;
      push(candidate, source);
    }
  }

  function scanDom(root = document) {
    if (!root) return;

    // 1. <a href> — a.href resolves relative URLs automatically.
    root.querySelectorAll("a[href]").forEach((a) => push(a.getAttribute("href"), "anchor"));
    // 2. <source/src/video/audio src>
    root.querySelectorAll("source[src], video[src], audio[src]").forEach((el) => push(el.getAttribute("src"), "media"));
    // 3. <model-viewer src>
    root.querySelectorAll("model-viewer[src]").forEach((el) => push(el.getAttribute("src"), "model-viewer"));
    // 4. <iframe src> — frequently hosts GLB previews
    root.querySelectorAll("iframe[src]").forEach((el) => push(el.getAttribute("src"), "iframe"));
    // 5. <link rel=preload/prefetch/modulepreload href>
    root.querySelectorAll('link[href][rel*="preload"], link[href][rel="prefetch"], link[href][rel="modulepreload"]').forEach((el) => push(el.getAttribute("href"), "preload"));
    // 6. <meta itemprop="contentUrl" content> + og:* 3D metas
    root.querySelectorAll("meta[itemprop][content], meta[property*='og:'][content]").forEach((el) => {
      const v = el.getAttribute("content");
      if (v && /\.(glb|gltf|usdz)(\?|#|$)/i.test(v)) push(v, "meta");
    });
    // 7. <img/srcset/use> — model-viewer often uses posters
    root.querySelectorAll("img[src], img[srcset]").forEach((el) => {
      const src = el.getAttribute("src");
      if (src) push(src, "img");
      const ss = el.getAttribute("srcset");
      if (ss) ss.split(",").forEach((s) => push(s.trim().split(/\s+/)[0], "img-srcset"));
    });
    // 8. JSON-LD scripts
    root.querySelectorAll("script[type='application/ld+json']").forEach((el) => scanText(el.textContent, "jsonld"));
    // 9. ANY inline script — Apple & Shopify embed model URLs in module scripts
    root.querySelectorAll("script:not([src])").forEach((el) => scanText(el.textContent, "script"));
    // 10. data-* attributes that may carry URLs
    root.querySelectorAll("[data-src], [data-url], [data-model], [data-asset], [data-3d]").forEach((el) => {
      ["data-src", "data-url", "data-model", "data-asset", "data-3d"].forEach((attr) => {
        const v = el.getAttribute(attr);
        if (v) push(v, "data-attr");
      });
    });
    // 11. Fallback: scan the entire document HTML for URL strings (catches rare attrs / text nodes).
    if (root === document) scanText(root.documentElement.outerHTML, "page-source");
  }

  // Hook fetch & XHR — capture runtime 3D requests.
  try {
    const origFetch = window.fetch;
    if (origFetch) {
      window.fetch = function (...args) {
        try {
          const a = args[0];
          const url = typeof a === "string" ? a : a?.url;
          if (url) push(url, "fetch");
        } catch {}
        return origFetch.apply(this, args);
      };
    }
  } catch {}
  try {
    const origOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (method, url) {
      try { if (url) push(url, "xhr"); } catch {}
      return origOpen.apply(this, arguments);
    };
  } catch {}

  // PerformanceObserver for entries already requested.
  try {
    const po = new PerformanceObserver((list) => {
      list.getEntries().forEach((entry) => push(entry.name, "perf"));
    });
    po.observe({ type: "resource", buffered: true });
  } catch {}

  // Initial scans.
  scanDom();
  document.addEventListener("DOMContentLoaded", () => scanDom());
  window.addEventListener("load", () => scanDom());

  // SPA-aware observer.
  const mo = new MutationObserver(() => {
    clearTimeout(window.__twdMutDeb);
    window.__twdMutDeb = setTimeout(() => scanDom(document), 250);
  });
  const startMO = () => {
    try { mo.observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ["href", "src"] }); } catch {}
  };
  if (document.documentElement) startMO();
  else document.addEventListener("DOMContentLoaded", startMO);

  // Side-panel rescan.
  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg?.type === "TWD_RESCAN") {
      seen.clear();
      scanDom();
      sendResponse({ ok: true });
      return false;
    }
    if (msg?.type === "TWD_FETCH_IN_PAGE") {
      // Fetch in page context (page origin) so same-origin requests bypass CORS,
      // and many cross-origin CDNs that return proper Access-Control-Allow-Origin
      // will also work here. Return ArrayBuffer for structured clone.
      (async () => {
        try {
          const res = await fetch(msg.url, { credentials: "include", mode: "cors" });
          if (!res.ok) {
            sendResponse({ ok: false, error: `HTTP ${res.status}` });
            return;
          }
          const blob = await res.blob();
          const buffer = await blob.arrayBuffer();
          sendResponse({ ok: true, mime: blob.type || "application/octet-stream", buffer: new Uint8Array(buffer) });
        } catch (err) {
          sendResponse({ ok: false, error: err?.message || String(err) });
        }
      })();
      return true; // keep channel open for async sendResponse
    }
    return false;
  });
})();
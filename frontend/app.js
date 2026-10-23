/* AI Assignment Scanner — vanilla JS SPA (no build step).
   HCI touches: skeletons→feedback, dropzone+chips→error prevention,
   step tracker→visibility of system state, icons+labels→recognition. */

const view = document.getElementById("view");
const statusPill = document.getElementById("status-pill");
const themeToggle = document.getElementById("theme-toggle");
const themeIcon = document.getElementById("theme-icon");

let statusInfo = null;
let deferredInstallPrompt = null;

/* ------------------------------------------------------------------ */
/* icons (stroke SVG, consistent 1.8 weight)                           */

const ICONS = {
  plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>',
  arrow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M5 12h14m0 0-5-5m5 5-5 5"/></svg>',
  camera: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M3 8a2 2 0 0 1 2-2h2l1.5-2h7L17 6h2a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><circle cx="12" cy="13" r="3.4"/></svg>',
  pencil: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 20h4L19.5 8.5a2.1 2.1 0 0 0-3-3L5 17z"/></svg>',
  trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 7h16M9 7V5h6v2m-8 0 1 13h8l1-13M10 11v6m4-6v6"/></svg>',
  doc: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4"/></svg>',
  refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M21 12a9 9 0 1 1-2.6-6.3M21 3v5h-5"/></svg>',
  save: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M5 3h11l3 3v15H5z"/><path d="M8 3v5h7V3M8 13h8m-8 4h5"/></svg>',
  image: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="m5 17 5-5 4 4 2-2 3 3"/></svg>',
};

/* ------------------------------------------------------------------ */
/* theme                                                                */

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("scanner-theme", theme);
  themeIcon.innerHTML =
    theme === "dark"
      ? '<circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2.2m0 14.6v2.2M2.5 12h2.2m14.6 0h2.2M5 5l1.6 1.6M17.4 17.4 19 19M19 5l-1.6 1.6M6.6 17.4 5 19"/>'
      : '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>';
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = theme === "dark" ? "#121812" : "#f3eee1";
}
applyTheme(localStorage.getItem("scanner-theme") ||
  (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
themeToggle.onclick = () =>
  applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");

/* ------------------------------------------------------------------ */
/* PWA: service worker + install button                                 */

if ("serviceWorker" in navigator && location.protocol !== "file:") {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}
window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  deferredInstallPrompt = e;
  document.getElementById("install-btn").style.display = "inline-flex";
});
document.getElementById("install-btn").onclick = async () => {
  if (!deferredInstallPrompt) return;
  deferredInstallPrompt.prompt();
  const choice = await deferredInstallPrompt.userChoice;
  if (choice.outcome === "accepted") toast("App installed — find it on your home screen.");
  deferredInstallPrompt = null;
  document.getElementById("install-btn").style.display = "none";
};

/* ------------------------------------------------------------------ */
/* helpers                                                              */

async function api(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (_) { /* not json */ }
    throw new Error(detail);
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res;
}

function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function toast(msg) {
  let t = document.querySelector(".toast");
  if (!t) { t = el(`<div class="toast"></div>`); document.body.appendChild(t); }
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("show"), 2800);
}

function badge(status) {
  return `<span class="badge ${status}">${status}</span>`;
}

function skeletons(kind) {
  if (kind === "cards") {
    return `
      <div class="sk skel-card"></div><div class="sk skel-card"></div>
      <div class="sk" style="margin-top:10px"><div style="padding:18px">
        <div class="sk skel-x2"></div><div class="sk skel-x2"></div><div class="sk skel-x2"></div>
      </div></div>`;
  }
  if (kind === "thumbs") {
    return `<div class="skel-grid"><div class="sk skel-th"></div><div class="sk skel-th"></div><div class="sk skel-th"></div></div>`;
  }
  if (kind === "editor") {
    return `<div class="page-layout"><div class="sk" style="height:480px"></div><div class="sk" style="height:480px"></div></div>`;
  }
  return `<div class="sk" style="height:64px"></div>`;
}

/* ------------------------------------------------------------------ */
/* status                                                              */

async function loadStatus() {
  try {
    statusInfo = await api("/api/status");
    const mock = statusInfo.recognizer === "mock";
    statusPill.classList.toggle("warn", mock);
    statusPill.textContent = mock ? "Mock mode" : `AI: TrOCR (${statusInfo.device})`;
  } catch (_) {
    statusPill.textContent = "offline";
    statusPill.classList.add("warn");
  }
}

/* ------------------------------------------------------------------ */
/* upload selection with live validation (error prevention)            */

const MAX_MB = 15;
let selectedFiles = [];   // per current create form, validated

function isAllowedFile(f) {
  const ok = /\.(jpe?g|png)$/i.test(f.name || "");
  return ok && f.size > 0 && f.size <= MAX_MB * 1024 * 1024;
}

function fmtKB(bytes) {
  return bytes > 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.round(bytes / 1024)} KB`;
}

function renderChips(container) {
  container.innerHTML = "";
  for (const f of selectedFiles) {
    const chip = el(`
      <span class="chip">
        <span class="chip-name">${esc(f.name)}</span>
        <span class="chip-size">${fmtKB(f.size)}</span>
        <button aria-label="Remove ${esc(f.name)}" title="Remove">✕</button>
      </span>`);
    chip.querySelector("button").onclick = () => {
      selectedFiles = selectedFiles.filter((x) => x !== f);
      renderChips(container);
    };
    container.appendChild(chip);
  }
}

function addFiles(fileList, chipsEl) {
  let added = 0, rejected = 0;
  for (const f of fileList) {
    if (isAllowedFile(f) && !selectedFiles.includes(f)) { selectedFiles.push(f); added++; }
    else rejected++;
  }
  if (rejected) toast(`Skipped ${rejected} file(s) — use JPG/PNG up to ${MAX_MB} MB, not already added.`);
  if (added) toast(`Added ${added} page photo${added > 1 ? "s" : ""}.`);
  renderChips(chipsEl);
}

function wireDropzone(zone, input, chipsEl) {
  zone.addEventListener("click", () => input.click());
  zone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); }
  });
  input.addEventListener("change", () => addFiles(input.files, chipsEl));
  for (const kind of ["dragover", "dragenter"]) {
    zone.addEventListener(kind, (e) => { e.preventDefault(); zone.classList.add("over"); });
  }
  for (const kind of ["dragleave", "drop"]) {
    zone.addEventListener(kind, () => zone.classList.remove("over"));
  }
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    addFiles(e.dataTransfer.files, chipsEl);
  });
  input.value = ""; // keep re-picking the same file possible
}

document.addEventListener("paste", async (e) => {
  const chipsEl = document.getElementById("chips");
  if (!chipsEl || !e.clipboardData?.files?.length) return;
  addFiles(e.clipboardData.files, chipsEl);
});

/* ------------------------------------------------------------------ */
/* dashboard                                                           */

async function renderDashboard() {
  view.innerHTML = `
    <div class="card">
      <h2>New assignment</h2>
      <div class="grid-2">
        <div>
          <label for="new-name">Assignment name</label>
          <input id="new-name" type="text" placeholder="Assignment 2 — Digital Logic" autocomplete="off" />
          <label for="new-subject">Subject</label>
          <input id="new-subject" type="text" placeholder="Digital Logic Design" list="subjects" autocomplete="off" />
          <datalist id="subjects"></datalist>
        </div>
        <div>
          <label>Page photos</label>
          <div id="dz" class="dropzone" role="button" tabindex="0" aria-label="Add page photos: click, drag files here, or paste">
            ${ICONS.camera}
            <b style="font-size:13.5px;color:var(--ink-2)">Click to choose photos</b>
            <span class="dz-hint">…or drag &amp; drop here · paste with Ctrl+V · JPG/PNG up to ${MAX_MB} MB</span>
          </div>
          <input id="new-files" type="file" accept="image/jpeg,image/png" multiple hidden />
          <div id="chips" class="chips" aria-live="polite"></div>
          <button id="new-submit" style="width:100%;margin-top:14px">${ICONS.arrow} Scan assignment</button>
          ${statusInfo?.recognizer === "mock"
            ? `<div class="subtitle" style="margin:10px 0 0;text-align:center">Mock mode: outputs placeholder text — deploy with TrOCR for real recognition.</div>`
            : ""}
        </div>
      </div>
    </div>
    <section class="card">
      <h2>Your assignments</h2>
      <div id="a-list" class="a-cards">${skeletons("cards")}</div>
    </section>`;

  const list = view.querySelector("#a-list");
  wireDropzone(view.querySelector("#dz"), view.querySelector("#new-files"), view.querySelector("#chips"));

  const assignments = await api("/api/assignments");
  const subjects = [...new Set(assignments.map((a) => a.subject).filter(Boolean))];
  view.querySelector("#subjects").innerHTML = subjects.map((s) => `<option value="${esc(s)}">`).join("");

  if (!assignments.length) {
    list.innerHTML = `<div class="empty">Nothing scanned yet.<br/>Add page photos above and press <b>Scan assignment</b>.</div>`;
  }
  for (const a of assignments) {
    const card = el(`
      <div class="a-card">
        <div class="a-main">
          <a class="a-title" href="#/assignment/${a.id}">${esc(a.name)}</a>
          <div class="a-meta">${esc(a.subject || "no subject")} · ${a.page_count} page${a.page_count === 1 ? "" : "s"} · ${bottleneck(a)}</div>
        </div>
        <div class="a-actions">
          <button class="small ghost ren" aria-label="Rename">${ICONS.pencil} Rename</button>
          <a class="btn small ghost" href="/api/assignments/${a.id}/export?kind=searchable_pdf">${ICONS.doc} Text PDF</a>
          <a class="btn small ghost" href="/api/assignments/${a.id}/export?kind=docx">${ICONS.doc} DOCX</a>
          <button class="small ghost del" aria-label="Delete">${ICONS.trash}</button>
        </div>
      </div>`);
    card.querySelector(".ren").onclick = async () => {
      const name = prompt("New assignment name:", a.name);
      if (name?.trim()) {
        await api(`/api/assignments/${a.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) });
        toast("Renamed ✔"); renderDashboard();
      }
    };
    card.querySelector(".del").onclick = async () => {
      if (confirm(`Delete “${a.name}” and all its pages? This cannot be undone.`)) {
        await api(`/api/assignments/${a.id}`, { method: "DELETE" });
        toast("Deleted"); renderDashboard();
      }
    };
    list.appendChild(card);
  }

  view.querySelector("#new-submit").onclick = async (e) => {
    const btn = e.currentTarget;
    const name = view.querySelector("#new-name").value.trim();
    const subject = view.querySelector("#new-subject").value.trim();
    if (!name) { toast("Enter an assignment name first."); return; }
    if (!selectedFiles.length) { toast("Add at least one page photo."); return; }
    btn.disabled = true;
    const fd = new FormData();
    fd.append("name", name); fd.append("subject", subject);
    for (const f of selectedFiles) fd.append("files", f);
    try {
      const created = await api("/api/assignments", { method: "POST", body: fd });
      selectedFiles = [];
      toast("Uploaded — processing…");
      location.hash = `#/assignment/${created.id}`;
    } catch (err) {
      toast(err.message);
      btn.disabled = false;
    }
  };
}

function bottleneck(a) {
  const c = a.status_counts;
  if (c.error) return `${c.error} failed`;
  if (c.processing) return "recognizing…";
  if (c.pending) return `queued (${c.done}/${a.page_count} done)`;
  return "ready";
}

/* step tracker: visibility of pipeline state */
function stepTracker(a) {
  const stages = ["Upload", "Enhance", "Recognize", "Review", "Export"];
  const c = a.status_counts;
  let cur = 0;
  if (a.page_count === 0) cur = 0;
  else if (c.done === a.page_count) cur = 3;          // at review/export
  else if (c.error && c.done + c.error === a.page_count) cur = 3;
  else cur = 2;                                        // enhancing/recognizing
  return `<div class="steps" role="list" aria-label="Processing stage">` +
    stages.map((name, i) => {
      let cls = "step";
      if (i < cur) cls += " done";
      else if (i === cur) cls += " active";
      return `<div class="${cls}" data-i="${i + 1}" aria-current="${i === cur}" title="${name}">${name}</div>`;
    }).join("") + `</div>`;
}

/* ------------------------------------------------------------------ */
/* assignment detail                                                   */

async function renderAssignment(id, refresh = false) {
  if (!refresh) {
    view.innerHTML = `<section class="card">${skeletons("thumbs")}</section>`;
  }
  const a = await api(`/api/assignments/${id}`);

  view.replaceChildren(
    el(`
      <div>
        <div class="crumb"><a href="#/">← All assignments</a></div>
        <h1>${esc(a.name)}</h1>
        <div class="subtitle">
          ${esc(a.subject || "no subject")} ·
          <span id="a-status">${bottleneck(a)}</span>
        </div>
        ${stepTracker(a)}
        <section class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:14px">
            <h2 style="margin:0">Pages</h2>
            <div class="toolbar">
              <a class="btn small ghost" href="/api/assignments/${id}/export?kind=original_pdf" title="PDF of the original pages">${ICONS.image} Scan PDF</a>
              <a class="btn small ghost" href="/api/assignments/${id}/export?kind=searchable_pdf" title="PDF with hidden text layer">${ICONS.doc} Search PDF</a>
              <a class="btn small ghost" href="/api/assignments/${id}/export?kind=docx">${ICONS.doc} DOCX</a>
              <a class="btn small ghost" href="/api/assignments/${id}/export?kind=txt">${ICONS.doc} TXT</a>
              <button class="small ghost ren">${ICONS.pencil} Rename</button>
              <button class="small danger del">${ICONS.trash}</button>
            </div>
          </div>
          <div class="thumbs"></div>
          <div style="margin-top:18px;border-top:1px dashed var(--line);padding-top:14px">
            <label>Add more pages</label>
            <div id="dz" class="dropzone" tabindex="0" role="button" aria-label="Add more pages">
              ${ICONS.camera}<b style="font-size:13.5px;color:var(--ink-2)">Click, drag &amp; drop, or paste photos</b>
            </div>
            <input id="add-files" type="file" accept="image/jpeg,image/png" multiple hidden />
            <div id="chips" class="chips"></div>
            <button id="add-btn" style="width:100%;margin-top:12px">${ICONS.plus} Upload pages</button>
          </div>
        </section>
      </div>`),
  );

  const thumbs = view.querySelector(".thumbs");
  if (!a.pages.length) {
    thumbs.innerHTML = `<div class="empty">No pages yet — add some below.</div>`;
  }
  for (const p of a.pages) {
    const showImg = p.processed_url || p.original_url;
    const t = el(`
      <a class="thumb" href="#/page/${p.id}" aria-label="Open page ${p.index} (${p.status})">
        <img src="${p.status === "done" ? showImg : p.original_url}" alt="page ${p.index}" loading="lazy"/>
        <div class="cap"><span>Page ${p.index}</span>${badge(p.status)}</div>
      </a>`);
    thumbs.appendChild(t);
  }

  const stillBusy = a.status_counts.pending + a.status_counts.processing > 0;
  if (stillBusy) pollAssignment(id);

  wireDropzone(view.querySelector("#dz"), view.querySelector("#add-files"), view.querySelector("#chips"));
  view.querySelector("#add-btn").onclick = async () => {
    if (!selectedFiles.length) { toast("Add page photos first."); return; }
    const btn = view.querySelector("#add-btn");
    btn.disabled = true;
    const fd = new FormData();
    for (const f of selectedFiles) fd.append("files", f);
    selectedFiles = [];
    try {
      await api(`/api/assignments/${id}/add_pages`, { method: "POST", body: fd });
      toast("Pages added — processing…");
      renderAssignment(id, true);
    } catch (err) { toast(err.message); btn.disabled = false; }
  };

  view.querySelector(".ren").onclick = async () => {
    const name = prompt("New assignment name:", a.name);
    if (name?.trim()) {
      await api(`/api/assignments/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) });
      toast("Renamed ✔"); renderAssignment(id, true);
    }
  };
  view.querySelector(".del").onclick = async () => {
    if (confirm(`Delete “${a.name}” and all its pages? This cannot be undone.`)) {
      await api(`/api/assignments/${id}`, { method: "DELETE" });
      toast("Deleted"); location.hash = "#/";
    }
  };
}

function pollAssignment(id) {
  const timer = setInterval(async () => {
    if (!location.hash.startsWith(`#/assignment/${id}`)) { clearInterval(timer); return; }
    try {
      const a = await api(`/api/assignments/${id}`);
      const busy = a.status_counts.pending + a.status_counts.processing;
      if (busy > 0) renderAssignment(id, true);
      else { renderAssignment(id, true); toast("Processing finished ✔"); clearInterval(timer); }
    } catch (_) { clearInterval(timer); }
  }, 1800);
}

/* ------------------------------------------------------------------ */
/* page editor                                                         */

async function renderPage(id) {
  view.innerHTML = `<section class="card">${skeletons("editor")}</section>`;
  const p = await api(`/api/pages/${id}`);
  const a = await api(`/api/assignments/${p.assignment_id}`).catch(() => null);

  const lowHtml = p.low_confidence.length
    ? p.low_confidence.map((l) =>
        `<div class="lowline">Line ${l.i + 1} · ${(l.confidence * 100).toFixed(0)}% confidence — “${esc(l.text)}”</div>`).join("")
    : `<div class="empty" style="padding:12px">No line fell below the confidence threshold ✓</div>`;

  view.replaceChildren(
    el(`
      <div>
        <div class="crumb">
          <a href="#/">← All assignments</a>
          ${a ? ` / <a href="#/assignment/${a.id}">${esc(a.name)}</a>` : ""}
          · page ${p.index}
        </div>
        <h1>Review &amp; correct</h1>
        <div class="subtitle">Fix anything the model misread — corrections flow into DOCX/TXT exports.</div>
        <div class="page-layout">
          <section class="card page-img">
            <h2>Page</h2>
            <div class="variant-tabs" role="tablist">
              <button data-v="original" class="on">Original</button>
              <button data-v="processed">Enhanced</button>
              <button data-v="boxes">Line boxes</button>
            </div>
            <img id="pv" src="${p.original_url}" alt="page preview"/>
            <div class="statrow" id="pstats"></div>
          </section>
          <section class="card">
            <div style="display:flex;justify-content:space-between;align-items:baseline;gap:10px">
              <h2 style="margin:0">Recognised text</h2>
              ${p.status === "done" ? "" : badge(p.status)}
            </div>
            <textarea id="editor" aria-label="Recognised text editor">${esc(p.text)}</textarea>
            <div class="toolbar" style="margin-top:12px">
              <button id="save-text">${ICONS.save} Save corrections</button>
              <button class="ghost" id="reprocess">${ICONS.refresh} Re-run recognition</button>
            </div>
            <h2 style="margin-top:20px">Low-confidence lines</h2>
            ${lowHtml}
          </section>
        </div>
      </div>`),
  );

  const pv = view.querySelector("#pv");
  const urls = {
    original: p.original_url,
    processed: p.processed_url || p.original_url,
    boxes: p.boxes_url || p.processed_url || p.original_url,
  };
  view.querySelectorAll(".variant-tabs button").forEach((b) => {
    b.onclick = () => {
      view.querySelectorAll(".variant-tabs button").forEach((x) => x.classList.remove("on"));
      b.classList.add("on");
      pv.src = urls[b.dataset.v];
    };
  });

  view.querySelector("#pstats").innerHTML = [
    `status <b>${p.status}</b>`,
    `lines <b>${p.lines.length}</b>`,
    p.mean_confidence != null ? `confidence <b>${(p.mean_confidence * 100).toFixed(0)}%</b>` : "",
    p.processing_ms != null ? `time <b>${(p.processing_ms / 1000).toFixed(1)}s</b>` : "",
    p.status === "error" ? `<span style="color:var(--red)">error: ${esc(p.error)}</span>` : "",
  ].filter(Boolean).join("");

  view.querySelector("#save-text").onclick = async (e) => {
    const btn = e.currentTarget;
    btn.disabled = true;
    try {
      await api(`/api/pages/${id}/text`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: view.querySelector("#editor").value }),
      });
      toast("Corrections saved — used by DOCX/TXT exports ✔");
    } catch (err) { toast(err.message); }
    btn.disabled = false;
  };

  view.querySelector("#reprocess").onclick = async () => {
    await api(`/api/pages/${id}/reprocess`, { method: "POST" });
    toast("Re-running recognition…");
    pollPage(id);
  };
}

function pollPage(id) {
  const timer = setInterval(async () => {
    if (!location.hash.startsWith(`#/page/${id}`)) { clearInterval(timer); return; }
    try {
      const p = await api(`/api/pages/${id}`);
      if (p.status !== "processing" && p.status !== "pending") {
        clearInterval(timer);
        renderPage(id);
        toast("Recognition finished ✔");
      }
    } catch (_) { clearInterval(timer); }
  }, 1800);
}

/* ------------------------------------------------------------------ */
/* router                                                              */

async function route() {
  const hash = location.hash || "#/";
  loadStatus();
  try {
    if (hash === "#/" || hash === "#") await renderDashboard();
    else {
      const mAss = hash.match(/^#\/assignment\/(\d+)$/);
      const mPage = hash.match(/^#\/page\/(\d+)$/);
      if (mAss) await renderAssignment(+mAss[1]);
      else if (mPage) await renderPage(+mPage[1]);
      else view.innerHTML = `<div class="empty">Unknown page.</div>`;
    }
  } catch (e) {
    view.innerHTML = `<section class="card"><h2>Something went wrong</h2><div class="empty">${esc(e.message)}</div></section>`;
  }
}

window.addEventListener("hashchange", route);
route();

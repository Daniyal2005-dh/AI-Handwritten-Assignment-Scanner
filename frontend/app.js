/* AI Assignment Scanner — vanilla JS single page app (no build step). */

const view = document.getElementById("view");
const statusPill = document.getElementById("status-pill");
const footerMeta = document.getElementById("footer-meta");

let statusInfo = null;
let deferredInstallPrompt = null;

/* ------------------------------------------------------------------ */
/* PWA: service worker + install button                                */

if ("serviceWorker" in navigator && location.protocol !== "file:") {
  navigator.serviceWorker.register("/sw.js").catch(() => { /* Service worker is optional */ });
}

window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  deferredInstallPrompt = e;
  const btn = document.getElementById("install-btn");
  if (btn) btn.style.display = "inline-flex";
});

document.getElementById("install-btn").onclick = async () => {
  if (!deferredInstallPrompt) return;
  deferredInstallPrompt.prompt();
  const choice = await deferredInstallPrompt.userChoice;
  if (choice.outcome === "accepted") {
    document.getElementById("install-btn").style.display = "none";
    toast("App installed — find it on your home screen.");
  }
  deferredInstallPrompt = null;
};

window.addEventListener("appinstalled", () => {
  document.getElementById("install-btn").style.display = "none";
});

/* ------------------------------------------------------------------ */
/* helpers                                                             */

async function api(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch (_) { /* not json */ }
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
  if (!t) {
    t = el(`<div class="toast"></div>`);
    document.body.appendChild(t);
  }
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2600);
}

function badge(status) {
  return `<span class="badge ${status}">${status}</span>`;
}

/* ------------------------------------------------------------------ */
/* status                                                              */

async function loadStatus() {
  try {
    statusInfo = await api("/api/status");
    const mock = statusInfo.recognizer === "mock";
    statusPill.classList.toggle("warn", mock);
    statusPill.textContent = mock ? "Mock mode" : `AI: TrOCR (${statusInfo.device})`;
    footerMeta.textContent = statusInfo.hint;
  } catch (_) {
    statusPill.textContent = "offline";
  }
}

/* ------------------------------------------------------------------ */
/* dashboard                                                           */

async function renderDashboard() {
  view.innerHTML = `<div class="empty">Loading…</div>`;
  const [assignments, subjects] = await Promise.all([
    api("/api/assignments"),
    api("/api/assignments").then((l) => [...new Set(l.map((a) => a.subject).filter(Boolean))]).catch(() => []),
  ]);

  const createCard = el(`
    <section class="card">
      <h2>New assignment</h2>
      <div class="grid-2">
        <div>
          <label>Assignment name</label>
          <input id="new-name" type="text" placeholder="Assignment 2 — Digital Logic" />
          <label>Subject</label>
          <input id="new-subject" type="text" placeholder="Digital Logic Design" list="subjects" />
          <datalist id="subjects">${subjects.map((s) => `<option value="${esc(s)}">`).join("")}</datalist>
        </div>
        <div>
          <label>Page photos (JPG / PNG, multiple allowed)</label>
          <input id="new-files" type="file" accept="image/jpeg,image/png" multiple style="margin-top:6px" />
          <button id="new-submit" style="margin-top:14px">Scan assignment →</button>
          <div class="subtitle" style="margin:8px 0 0">
            ${statusInfo?.recognizer === "mock"
              ? "Run with SCANNER_RECOGNIZER=trocr to enable real handwriting recognition."
              : "Recognition runs in the background; status updates live."}
          </div>
        </div>
      </div>
    </section>`);

  const listCard = el(`<section class="card"><h2>Your assignments</h2><div class="a-cards"></div></section>`);
  const list = listCard.querySelector(".a-cards");

  if (!assignments.length) {
    list.innerHTML = `<div class="empty">No assignments yet — upload page photos above.</div>`;
  }
  for (const a of assignments) {
    const counts = a.status_counts;
    const summary =
      `${a.page_count} page${a.page_count === 1 ? "" : "s"} — ` +
      bottleneck(a);
    const card = el(`
      <div class="a-card">
        <div class="a-main">
          <a class="a-title" href="#/assignment/${a.id}">${esc(a.name)}</a>
          <div class="a-meta">${esc(a.subject || "no subject")} · ${summary}</div>
        </div>
        <div class="a-actions">
          <button class="small ghost ren">Rename</button>
          <a class="btn small ghost" href="/api/assignments/${a.id}/export?kind=original_pdf">Scan PDF</a>
          <a class="btn small ghost" href="/api/assignments/${a.id}/export?kind=searchable_pdf">Text PDF</a>
          <a class="btn small ghost" href="/api/assignments/${a.id}/export?kind=docx">DOCX</a>
          <button class="small danger del">Delete</button>
        </div>
      </div>`);
    card.querySelector(".ren").onclick = async () => {
      const name = prompt("New name:", a.name);
      if (name && name.trim()) { await api(`/api/assignments/${a.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) }); toast("Renamed"); renderDashboard(); }
    };
    card.querySelector(".del").onclick = async () => {
      if (confirm(`Delete "${a.name}" and all its pages?`)) {
        await api(`/api/assignments/${a.id}`, { method: "DELETE" });
        toast("Deleted");
        renderDashboard();
      }
    };
    list.appendChild(card);
  }

  view.replaceChildren(createCard, listCard);
  const submit = createCard.querySelector("#new-submit");
  submit.onclick = async () => {
    const name = createCard.querySelector("#new-name").value.trim();
    const subject = createCard.querySelector("#new-subject").value.trim();
    const files = createCard.querySelector("#new-files").files;
    if (!name) { toast("Enter an assignment name"); return; }
    if (!files.length) { toast("Select at least one page image"); return; }
    submit.disabled = true;
    submit.textContent = "Uploading…";
    const fd = new FormData();
    fd.append("name", name);
    fd.append("subject", subject);
    for (const f of files) fd.append("files", f);
    try {
      const created = await api("/api/assignments", { method: "POST", body: fd });
      toast("Uploaded — processing…");
      location.hash = `#/assignment/${created.id}`;
    } catch (e) {
      toast(e.message);
      submit.disabled = false;
      submit.textContent = "Scan assignment →";
    }
  };
}

function bottleneck(a) {
  const c = a.status_counts;
  if (c.error) return `${c.error} failed`;
  if (c.processing) return "processing…";
  if (c.pending) return `queued (${c.done}/${a.page_count} done)`;
  return "done";
}

/* ------------------------------------------------------------------ */
/* assignment detail                                                   */

async function renderAssignment(id, refresh = false) {
  if (!refresh) view.innerHTML = `<div class="empty">Loading…</div>`;
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
        <section class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
            <h2 style="margin:0">Pages</h2>
            <div style="display:flex;gap:14px;flex-wrap:wrap">
              <a class="btn small ghost" href="/api/assignments/${id}/export?kind=original_pdf">Scan PDF</a>
              <a class="btn small ghost" href="/api/assignments/${id}/export?kind=searchable_pdf">Searchable PDF</a>
              <a class="btn small ghost" href="/api/assignments/${id}/export?kind=docx">DOCX</a>
              <a class="btn small ghost" href="/api/assignments/${id}/export?kind=txt">TXT</a>
            </div>
          </div>
          <div class="thumbs" style="margin-top:14px"></div>
          <div style="margin-top:16px">
            <label>Add more pages</label>
            <input id="add-files" type="file" accept="image/jpeg,image/png" multiple style="margin-top:4px" />
            <button class="small" id="add-btn" style="margin-top:10px">Upload pages</button>
          </div>
        </section>
      </div>`),
  );

  const thumbs = view.querySelector(".thumbs");
  for (const p of a.pages) {
    const showImg = p.processed_url || p.original_url;
    const t = el(`
      <a class="thumb" href="#/page/${p.id}">
        <img src="${p.status === "done" ? showImg : p.original_url}" alt="page ${p.index}" loading="lazy"/>
        <div class="cap"><span>Page ${p.index}</span>${badge(p.status)}</div>
      </a>`);
    t.onclick = () => { location.hash = `#/page/${p.id}`; };
    thumbs.appendChild(t);
  }
  if (!a.pages.length) thumbs.innerHTML = `<div class="empty">No pages yet.</div>`;

  const stillBusy = a.status_counts.pending + a.status_counts.processing > 0;
  if (stillBusy) pollAssignment(id);

  view.querySelector("#add-btn").onclick = async () => {
    const input = view.querySelector("#add-files");
    const files = input.files;
    if (!files.length) { toast("Select page images first"); return; }
    const btn = view.querySelector("#add-btn");
    btn.disabled = true;
    btn.textContent = "Uploading…";
    const fd = new FormData();
    for (const f of files) fd.append("files", f);
    try {
      await api(`/api/assignments/${id}/add_pages`, { method: "POST", body: fd });
      toast("Pages added — processing…");
    } catch (e) {
      toast(e.message);
    }
    btn.disabled = false;
    btn.textContent = "Upload pages";
    input.value = "";
    renderAssignment(id, true);
  };
}

function pollAssignment(id) {
  const timer = setInterval(async () => {
    if (!location.hash.startsWith(`#/assignment/${id}`)) { clearInterval(timer); return; }
    try {
      const a = await api(`/api/assignments/${id}`);
      if (a.status_counts.pending + a.status_counts.processing > 0) renderAssignment(id, true);
      else { renderAssignment(id, true); toast("Processing finished."); clearInterval(timer); }
    } catch (_) { clearInterval(timer); }
  }, 1500);
}

/* ------------------------------------------------------------------ */
/* page editor                                                         */

async function renderPage(id) {
  view.innerHTML = `<div class="empty">Loading…</div>`;
  const p = await api(`/api/pages/${id}`);
  const a = await api(`/api/assignments/${p.assignment_id}`).catch(() => null);

  const lowHtml = p.low_confidence.length
    ? p.low_confidence.map((l) =>
        `<div class="lowline">Line ${l.i + 1} · ${(l.confidence * 100).toFixed(0)}% — "${esc(l.text)}"</div>`).join("")
    : `<div class="empty">Nothing flagged — every line passed the confidence check.</div>`;

  view.replaceChildren(
    el(`
      <div>
        <div class="crumb">
          <a href="#/">← All assignments</a>
          ${a ? ` / <a href="#/assignment/${a.id}">${esc(a.name)}</a>` : ""}
          · page ${p.index}
        </div>
        <h1>Review &amp; correct</h1>
        <div class="page-layout">
          <section class="card page-img">
            <div class="variant-tabs">
              <button class="small ghost" data-v="original">Original</button>
              <button class="small ghost" data-v="processed">Enhanced</button>
              <button class="small ghost" data-v="boxes">Line boxes</button>
            </div>
            <img id="pv" src="${p.original_url}" alt="page preview"/>
            <div class="statrow" id="pstats"></div>
          </section>
          <section class="card">
            <div style="display:flex;justify-content:space-between;align-items:baseline">
              <h2 style="margin:0">Recognised text</h2>
              ${p.status === "done" ? "" : badge(p.status)}
            </div>
            <textarea id="editor">${esc(p.text)}</textarea>
            <button id="save-text" style="margin-top:10px">Save corrections</button>
            <button class="ghost" id="reprocess" style="margin-top:10px">Re-run recognition</button>
            <h2 style="margin-top:18px">Low-confidence lines</h2>
            ${lowHtml}
          </section>
        </div>
      </div>`),
  );

  const pv = view.querySelector("#pv");
  const urls = { original: p.original_url, processed: p.processed_url || p.original_url, boxes: p.boxes_url || p.processed_url || p.original_url };
  view.querySelectorAll(".variant-tabs button").forEach((b) => {
    b.onclick = () => { pv.src = urls[b.dataset.v]; };
  });

  const stats = view.querySelector("#pstats");
  stats.innerHTML = `
    <span>status <b>${p.status}</b></span>
    <span>lines <b>${p.lines.length}</b></span>
    ${p.mean_confidence != null ? `<span>mean confidence <b>${(p.mean_confidence * 100).toFixed(0)}%</b></span>` : ""}
    ${p.processing_ms != null ? `<span>process time <b>${(p.processing_ms / 1000).toFixed(1)}s</b></span>` : ""}
    ${p.status === "error" ? `<span style="color:var(--red)">error: ${esc(p.error)}</span>` : ""}`;

  view.querySelector("#save-text").onclick = async () => {
    const text = view.querySelector("#editor").value;
    const btn = view.querySelector("#save-text");
    btn.disabled = true;
    try {
      await api(`/api/pages/${id}/text`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      toast("Corrections saved — exports will use this text.");
    } catch (e) { toast(e.message); }
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
        toast("Recognition finished.");
      }
    } catch (_) { clearInterval(timer); }
  }, 1500);
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
loadStatus();
route();

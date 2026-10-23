# AI Handwritten Assignment Scanner

Photo or scan → clean digital page, editable text, searchable PDF.

An AI + Computer Vision + OCR system that takes photographs of handwritten
assignments, fixes perspective/shadows/skew, detects the text layout, converts
each line to digital text, and exports **original-scan PDFs, searchable PDFs,
DOCX and TXT** — with a review editor and an assignment dashboard on top.

Backend: **Python · FastAPI · OpenCV · SQLAlchemy (SQLite)**
Frontend: **static HTML/JS served by the same server**
Recognition: **Microsoft TrOCR** (`microsoft/trocr-base-handwritten`) with an
offline **mock mode** so the whole product works before any model download.

---

## Quick start

```powershell
cd Documents\AI-Handwritten-Assignment-Scanner
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt   # CPU torch is installed on Windows by default
.venv\Scripts\python -m uvicorn backend.app:app --port 8000
```

Open **http://localhost:8000** in your browser, create an assignment,
upload page photos, and wait for the processing badges to turn green.
One-line alternative on any OS: `./run.sh` or `run.bat`.

## Deploy (cloud)

```powershell
# first run only
.venv\Scripts\pip install huggingface_hub
# creates daniyal2005-dh/AI-Assignment-Scanner Space, pushes code,
# sets SCANNER_RECOGNIZER=trocr, and prints the live URL
.venv\Scripts\python scripts\deploy_hf.py
```

The script logs you in through the browser once. First build takes a few
minutes (CPU-torch Docker image); afterwards every `scripts/deploy_hf.py`
run updates the Space. Files served publicly run the **real TrOCR model**.

## Install as an app (PWA)

The web app is a Progressive Web App:

* **Android/Chrome**: open the site → "Install app" (button appears after
  first load, or ⋮ menu → *Add to Home screen*).
* **Windows/Edge**: address-bar install icon → *Install App as*.
* **iOS/Safari**: Share → *Add to Home Screen*.

Installed, it launches standalone (own window, app icon) and keeps working
with cached shell + offline notice; assignments always require the server.

### Switch on real recognition (TrOCR)

```powershell
$env:SCANNER_RECOGNIZER = "trocr"
.venv\Scripts\python -m uvicorn backend.app:app --port 8000
```

The first request downloads ~1.5 GB of model weights from Hugging Face
(cached afterwards). On CPU expect roughly 1–3 s per text line. Current mode
is visible in the app badge (top-right) and at `GET /api/status`.

| Environment variable | Meaning | Default |
|---|---|---|
| `SCANNER_RECOGNIZER` | `mock` or `trocr` | `mock` |
| `SCANNER_TROCR_MODEL` | Hugging Face model id | `microsoft/trocr-base-handwritten` |
| `SCANNER_DEVICE` | `cpu` / `cuda` / `auto` | `auto` |
| `SCANNER_DATA_DIR` | where uploads, processed pages and the DB live | `./data` |
| `SCANNER_MAX_UPLOAD_MB` | per-page upload limit | `15` |

---

## How it works

```
photo upload ─▶ page-corner detection ─▶ perspective warp (A4)
             ─▶ shadow removal (division normalisation)
             ─▶ denoise → deskew → CLAHE contrast
             ─▶ ink-projection line segmentation + paragraph grouping
             ─▶ TrOCR per line (+ token confidence)
             ─▶ review editor (low-confidence lines highlighted)
             ─▶ exports: original PDF · searchable PDF · DOCX · TXT
```

Recognition runs in the background after upload; the editor polls page
status. Corrected text always wins over raw recognition in DOCX/TXT exports;
the searchable PDF keeps per-line alignment of the recognition layer.

### Processing notes

* **Mock mode** writes `"(mock recognition) line N"` — it exists so the full
  product (editor, exports, dashboard) is demonstrable instantly and so unit
  tests stay offline.
* **TrOCR** is applied per detected line with average token-probability as
  its confidence score; lines below 60% are flagged for review.
* Segmentation assumes single-column pages (true for assignments).

## The three output modes

1. **Scan PDF** — page images only; looks exactly like the sheet.
2. **Searchable PDF** — same images with an invisible text layer aligned to
   each recognised line (selectable/searchable, still visually original).
3. **Editable** — DOCX with detected headings and paragraphs, or plain TXT.

## Android app (Kotlin)

`mobile/` contains a Kotlin client that wraps the web app for Android:

* saves you from typing URLs — the deployed HF Space is set as default
* **photo picking** via the system picker (multi-select JPEG/PNG, camera apps included)
* pull-to-refresh, back-gesture navigation, offline screen with Retry
* configurable target: run locally (`http://10.0.2.2:8000` on the emulator or
  `http://<laptop-ip>:8000` from your phone) or on the cloud server

Build (requires JDK 17 + Android SDK):

```powershell
cd mobile
.\gradlew.bat assembleDebug      # APK at app/build/outputs/apk/debug/app-debug.apk
.\gradlew.bat assembleRelease    # signed-free release build
```

## Evaluation (CER / WER)

```powershell
# 1. generate synthetic pages with exact ground truth
.venv\Scripts\python scripts\make_sample_page.py --count 3

# 2. score them (use mock to check the harness, trocr for real numbers)
$env:SCANNER_RECOGNIZER = "trocr"
.venv\Scripts\python scripts\evaluate.py --csv COVERAGE_EVAL.csv
```

Planned extensions: IAM dataset benchmarking, ablation toggles per pipeline
step (does shadow removal help CER?), TrOCR vs. baseline comparison, and
writer-independent testing. See `docs/PLAN.md`.

## Project structure

```
backend/
  app.py               FastAPI wiring, static frontend, status endpoint
  config.py            environment-driven settings
  database.py          engine/session management (SQLite)
  models.py            Assignment + Page ORM models
  routers/assignments  create/list/detail/rename/delete/export/add pages
  routers/pages        detail, image with line-box overlay, correct text, reprocess
  services/preprocessing.py  corner detect → warp → shadow removal → deskew → CLAHE
  services/layout.py   ink-projection line segmentation, paragraphs, headings
  services/recognition.py    mock + TrOCR providers behind one interface
  services/pipeline.py upload → enhance → segment → recognise → persist
  services/exports.py  original PDF / searchable PDF / DOCX / TXT builders
frontend/              PWA: index.html + app.js + styles.css (no build step)
mobile/                Kotlin Android client (WebView host of the PWA)
scripts/               sample-page generator, CER/WER evaluation, HF Space deployer
tests/                 pytest: pipeline units + full API flow (mock mode)
```

## Development

```powershell
.venv\Scripts\python -m pytest tests -q          # full offline test suite
```

License: MIT.

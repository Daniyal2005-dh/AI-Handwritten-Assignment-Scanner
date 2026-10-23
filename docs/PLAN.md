# FYP Plan — AI Assignment Scanner & Handwriting Recognition System

Companion to `README.md`: the research framing, feature checklist and
evaluation methodology this codebase (and your report) are built around.

## Problem

Students submit handwritten assignments and later need digital copies for
archiving, editing, sharing and plagiarism-safe re-use. Manual retyping is
slow; plain OCR struggles with connected handwriting, uneven lighting, page
curvature and mathematical symbols. This system corrects document
imperfections, recognises handwritten text and reconstructs usable documents
while preserving page structure.

## Feature checklist (v1 status)

| Feature | Status |
|---|---|
| Upload/capture pages, multi-page assignments | ✅ |
| Page enhancement: corners, perspective, shadows, deskew, contrast | ✅ |
| Line segmentation, reading order, paragraph + heading reconstruction | ✅ |
| Handwriting recognition (TrOCR) with confidence scores | ✅ |
| Side-by-side review editor with low-confidence flagging | ✅ |
| Exports: original-scan PDF / searchable PDF / DOCX / TXT | ✅ |
| Dashboard: subjects, rename, delete, history, downloads | ✅ |
| CER/WER evaluation harness + synthetic ground-truth pages | ✅ |

## Research contributions to make it defensible

1. **Enhancement ablation** — every preprocessing stage is a separate,
   switchable function in `services/preprocessing.py`. Re-run
   `scripts/evaluate.py` with one stage disabled at a time and report ΔCER:
   does shadow removal or CLAHE actually help recognition?
2. **Model comparison** — `services/recognition.py` is a single-provider
   interface; implement a second provider (e.g. a CRNN trained on IAM or
   EasyOCR) and compare on the same held-out pages.
3. **Layout preservation metric** — score whether headings/paragraph
   boundaries survive reconstruction (compare paragraph counts against GT).
4. **Writer independence** — evaluate on students whose writing is not in
   any training material (IAM writer partitions map naturally).
5. **Confidence-assisted correction** — quantify how much human editing time
   is saved by highlighting only lines below the confidence threshold.

## Datasets

* **IAM Handwriting Database** — English lines/words, research benchmark
  (non-commercial terms; register for download). Use for fine-tuning and
  CER/WER benchmarking.
* **IPC-WritDAR** — handwriting incl. Urdu; targeted at Pakistani
  assignments. Check licensing/size before committing to it.

## Metrics

`scripts/evaluate.py` computes both canonical metrics:

* **CER** = Levenshtein(characters) / ‖reference‖
* **WER** = Levenshtein(words) / ‖reference‖
* plus per-page processing time (stored per page as `processing_ms`).

Report rule: same held-out set, same preprocessing, only the variable under
test changes.

## Roadmap

- [ ] Batch TrOCR line inference (GPU) for <1 s/page
- [ ] Extension: second recognition provider for comparison table
- [ ] Urdu script support (WritDAR fine-tune or separate model)
- [ ] Mathematical notation (separately trained symbol model)
- [ ] Ablation CLI flags on `evaluate.py`
- [ ] Per-page layout diagram in the review editor

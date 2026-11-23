# Hard corpus, access controls and visual verification

## Reproducible evidence

The [manifest](../tests/corpus/manifest.csv) contains 350 inputs, each with source, license, SHA-256, independently specified expected fields and routing. There are 100 public CORD receipt photographs (CC BY 4.0), three public MIT invoice fixtures, and 247 synthetic fixtures. CORD fields use the dataset creators' human annotations; they were not manually transcribed by this project. Synthetic expectations were authored before extraction. Layout variants are correlated and do not count as independent business cases.

CORD attribution: [Clova AI CORD](https://github.com/clovaai/cord), downloaded from the [Heliosoph mirror](https://huggingface.co/datasets/Heliosoph/CORD); [license](../tests/corpus/CORD-LICENSE.txt). The upstream dataset redacts store/payment information. Mirror JPEG re-encoding is documented by the source URLs in the manifest.

| Measure | Before | After |
|---|---:|---:|
| Decision accuracy | 94.57% | 98.57% |
| False auto-approval rate | 0% | 0% |
| Straight-through rate | 3.43% | 4.57% |
| Synthetic field accuracy | 59.10% | 96.97% |
| External field accuracy | 0.92% | 7.34% |

These are measured regression results on the same fixed labels, not production guarantees. All OCR documents require source verification before approval. Safe review routing is not evidence of accurate extraction.

Full [before JSON](../reports/hard-before.json), [before HTML](../reports/hard-before.html), [after JSON](../reports/hard-after.json), and [after HTML](../reports/hard-after.html) include field scores, confusion matrix, latency, OCR measurements and ten worst remaining failures with expected/extracted values and causes. Reports in the app display the comparison. Run `python scripts/evaluate.py local --require-zero-false-approves` to reproduce; runtime/OCR results can vary by environment. CI runs the full corpus without relabeling it.

## Coverage map

| Cases | Executable evidence |
|---|---|
| 100 real receipt photos, 5 difficult layouts, 15 degraded photos, multiple invoices | [Hard corpus builder](../scripts/build_hard_corpus.py), [manifest](../tests/corpus/manifest.csv) |
| Duplicate identity, cumulative budget, concurrent reservations, tolerance, closed PO, blocked/unknown vendor, currency, missing total, negative values, future dates, OCR verification | [Workflow tests](../tests/test_workflow.py) |
| Indian amounts, date formats, PO lookalikes, Laptop/Notebook synonyms, item quantity/price/unit, repeated lines, expired PO, old invoice, GST components, shipping/discount/rounding, proforma, credit note, Hindi labels, hostile instruction text | [Extended tests](../tests/test_extended.py) |
| Empty file, executable signature, 200 MB size guard, atomic overrides, conflicting IDs, European amounts and Tax ID/Tax label separation | [Hardening tests](../tests/test_hardening.py) |
| Authentication, uploads, review and exports | [HTTP tests](../tests/test_http.py) |
| Cross-user detail/source/export/event isolation; reviewer admin restrictions; create/disable/audit; mandatory password change | [Access tests](../tests/access.test.mjs) |
| Three role screens, server restrictions, logout and responsive AA checks | [Role browser tests](../tests/e2e/roles.spec.mjs) |
| Signup/verification, native PDF, scan, duplicate, split balance, corrections, stream fallback | [Workflow browser tests](../tests/e2e/workflow.spec.mjs) |

The 200 MB guard test simulates the byte length at the service boundary without allocating or transmitting 200 MB. HTTP multipart uploads are separately size-limited.

## Screenshots

Fresh-browser live verification is recorded in [live role results](../reports/live-roles.json). It checked login/logout, the 350-document report, uploader ownership, reviewer restrictions, a public receipt upload and admin assignment. Live captures: [Admin](qa/live/admin.png), [Reviewer](qa/live/reviewer.png), [Uploader](qa/live/uploader.png), [source and decision](qa/live/uploader-run.png). These images contain only fictional accounts and a public dataset receipt.

[Admin](qa/admin-dashboard.png), [admin controls](qa/admin-controls.png), [Reviewer](qa/reviewer-dashboard.png), [review queue](qa/reviewer-queue.png), [Uploader](qa/uploader-dashboard.png), [submissions](qa/admin-submissions.png), [upload](qa/invoices.png), [procurement](qa/procurement.png), [reports](qa/evaluation.png), [settings](qa/settings.png). [Side-by-side gallery](qa/index.html) compares the shared tokens with marketing. These are local browser test artifacts; live verification is recorded separately.

## Known limitations and mocks

- External receipt field accuracy is only 7.34%. Five routing mismatches remain: four unreadable images were safely rejected instead of labeled Review, and one email-embedded valid invoice was conservatively held because sender and vendor differed. The top ten field/routing failures are preserved in the report.
- This is not universal invoice understanding. Merged cells, wrapped line items, arbitrary handwritten corrections and all regional date conventions are not comprehensively supported. Ambiguous numeric dates need source verification; PO issue-date comparison is not implemented. The corpus does not establish coverage of every combination requested.
- Stamp/handwriting overlays and screen/crease variants are synthetic approximations, not independently captured phone photographs of each degradation. The 100 CORD photos provide actual external visual diversity.
- Vendor/PO master data, semantic synonym mappings and procurement are fictional fixtures. There is no ERP connection or payment execution. No paid LLM is used; extraction uses PDF text and Tesseract.
- Field confidence is not calibrated. The UI reports document OCR confidence and source evidence rather than invented per-field probabilities. Line items are displayed; the current correction form edits header/totals fields.
- Shared demo accounts intentionally expose the fictional workspace according to role. Their profile, password, deletion and role/disable controls are protected while demo mode is enabled. Use personal accounts only in a private deployment; turn off `DEMO_MODE` and replace demo passwords before private use.
- The audit UI shows the latest 500 account events; run event history is available per document. Submissions filtering loads accessible runs in memory and is intended for a small demo, not enterprise volume.
- The free hosting tier can cold-start. Persistent database storage and original source retention are quota-limited. No paid resources are required or provisioned.

## Record a 4–6 minute demo

1. Open the live marketing page, explain invoice intake → validation → human review → audit. Show the three roles briefly.
2. Sign in as Uploader. Upload a fictional sample and show the stages, source, extracted fields and plain-language decision. Explain that the uploader sees only its submissions.
3. Sign in as Reviewer in a separate browser profile. Open the review queue, inspect an ambiguous or scanned invoice, correct its PO, add a note, verify the source and revalidate. Show the recorded actor and before/after values.
4. Sign in as Admin. Demonstrate submissions filters/CSV, user controls, reviewer assignment, rules and an explicitly labeled manual override. Do not imply an override is automatic approval or a real payment.
5. Open Reports. Show all 350 inputs, before/after scores, zero false approvals and the poor real-receipt extraction score. Open one worst failure to demonstrate honest fallback.
6. Show the GitHub CI result and logout. Record with Windows Snipping Tool or OBS; use only fictional data and never show `.env`, keys, reset links or private account details.

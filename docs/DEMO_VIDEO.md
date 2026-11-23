# Five-minute Vellum demo

Record the browser at 1920x1080, 100% zoom, with microphone narration. Close personal tabs and notifications. Keep credentials, `.env`, verification tokens and provider dashboards out of frame. Use only fictional sample invoices. Windows Snipping Tool screen recording or another recorder you already have is sufficient.

## Prepare

Run `scripts/start-local.cmd` (works without changing PowerShell execution policy), or open the verified public deployment. Create and verify the owner account beforehand. Use a clean demonstration workspace so the sample invoices are not already duplicates; for local recording point DATA_DIR at a new directory and leave DATABASE_URL empty. Set BOOTSTRAP_ADMIN before signing up. Keep the server terminal outside the recording.

Have `samples/01-happy-path.pdf`, `02-split-over-budget.pdf`, `03-semantic-duplicate.pdf`, `04-ambiguous-po.pdf`, and `09-scanned-invoice.pdf` ready. The clean invoice must precede the split/duplicate examples. Repeat takes need a new local data directory, not manual deletion of audit rows.

| Time | Show | Suggested narration |
|---|---|---|
| 0:00–0:30 | Marketing page and How it works | “Vellum takes an invoice and explains whether it is safe to approve, needs review, or must be rejected. Nothing here sends a payment.” |
| 0:30–0:50 | Login and dashboard | “Verified accounts have uploader, reviewer or admin permissions. This procurement data is fictional.” |
| 0:50–1:35 | Upload 01-happy-path; open stages, original and budget rule | “The document is parsed, validated, matched to a PO, and checked against policy. The approval reserves the PO balance atomically.” |
| 1:35–2:05 | Upload 02-split-over-budget | “The second invoice cannot reuse the original balance. It sees the remaining 420 including the 2% allowance and goes to review.” |
| 2:05–2:25 | Upload 03-semantic-duplicate | “A changed file still cannot reuse the same vendor invoice reference. The duplicate is rejected.” |
| 2:25–3:00 | Upload 09-scanned-invoice; show confidence and source | “Tesseract reads the scan. OCR confidence is measured, but this policy still requires a person to verify every scan.” |
| 3:00–3:40 | Upload 04-ambiguous-po, choose PO-2001, note buyer confirmation, check verified, revalidate | “Ambiguity is not guessed away. The correction and note are recorded, then all rules run again.” |
| 3:40–4:20 | Dashboard, audit events, exports, procurement balance | “Every run has its reasons and history. Reviewers can inspect corrections and download the decision.” |
| 4:20–4:45 | Evaluation report and external slice | “The 134-file regression corpus has zero false approvals and 100% expected routing. Only 8.96% approves automatically. External field extraction is 10.53%, so unfamiliar layouts still need work.” |
| 4:45–5:00 | Logout, then open /app | “Logout revokes the server session; protected pages send us back to login.” |

Avoid saying “100% invoice accuracy”: the metric is routing accuracy on this controlled corpus. Mention the three external fixtures and correlated synthetic variants. Do not imply email ingestion, ERP integration or payment execution is implemented. Do not fake processing waits or splice a simulated output into the run.

Export MP4 at 1080p, check that text and narration are readable, and submit the video together with the repository, live URL (once verified), and evaluation report. A simple continuous recording is stronger than elaborate transitions.

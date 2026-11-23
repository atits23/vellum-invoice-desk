# Verification status

Recorded 2026-11-23. Only completed checks are claimed.

- Browser: five Playwright tests passed, including signup, verification, login, clean/split/duplicate/ambiguous/scanned workflows, dashboard and logout. Axe WCAG A/AA checks passed on the authenticated dashboard and marketing at 360, 768, 1024 and 1440 pixels.
- Accounts: 12 Node test results passed using Neon PostgreSQL, covering verification, sessions, CSRF, password reset, protected pages and contact persistence.
- PostgreSQL engine: migration, approval, original-file persistence across a new filesystem directory, and duplicate rejection passed against the new Neon project.
- Corpus: 134/134 expected decisions, zero false approvals among 122 unsafe inputs. External field extraction remains 10.53%; review routing is not an extraction success claim.
- Python suite: 62 tests passed, including repeated-line cumulative quantity coverage and HTTP integration. The earlier restricted-shell networking failures passed when rerun with loopback access.
- Docker and Linux CI: [run 45131071148](https://github.com/atits23/vellum-invoice-desk/actions/runs/45131071148) passed all steps for code revision `b457fad`: Python, accounts on SQLite and PostgreSQL, browser/accessibility, corpus, Docker build and Python tests inside the container. Docker is not installed on the local machine; container validation ran on GitHub Actions and the image also runs on Render.
- Lighthouse: local mobile navigation scored 100 performance, 100 accessibility, 100 best practices and 100 SEO. The generated HTML/JSON report records the machine and tool version. Scores do not prove complete WCAG conformance or guarantee hosted/cold-start performance.
- Public deployment: https://vellum-invoice-desk-atits23.onrender.com passed real signup/email verification, login, clean PDF approval, split-invoice review, duplicate rejection, scanned-PDF OCR review, dashboard and logout. Email delivery was confirmed by the provider and by the owner completing verification.
- Redeployment: the account, four prior runs, original PDF bytes and reserved PO balance survived deployment. A further ambiguous-PO review correction approved successfully and logout revoked the session.

Reports contain actual timings from the recorded machine. Cold starts, CPU limits and OCR version differences can change them. Corpus timestamps are fixed; the old-invoice policy may intentionally change expected routing as the fixtures age. Regenerate dated synthetic fixtures and independently review labels before a future benchmark.

The first Linux browser runs exposed a delayed dialog-close event clearing a newly opened invoice's active state. The final revision guards that event, uses a stream-local handle, and falls back to persisted polling if streaming is interrupted. The regression test deliberately blocks event streams after the first invoice.

Not claimed: a production load test, independent security certification, universal OCR accuracy, a live-host Lighthouse score, or full manual assistive-technology certification. The Compose wrapper has not been executed locally; its Docker image was built, tested and deployed successfully.

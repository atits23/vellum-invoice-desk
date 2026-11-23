# Verification status

Recorded 2026-11-23. Application revision `3e278ce` is live.

- 67 Python tests, 19 Node test results and 8 Playwright tests passed. Browser coverage includes all roles, logout, signup/verification, uploads, corrections, scan review, duplicate/budget checks and stream fallback. Automated Axe A/AA checks passed at 360/768/1024/1440 widths.
- [GitHub CI run 45141303434](https://github.com/atits23/vellum-invoice-desk/actions/runs/45141303434) passed every step: Python, Node, SQLite/PostgreSQL accounts, PostgreSQL engine persistence, browsers, full corpus, Docker build and Python tests inside Docker.
- The 350-document local evaluation achieved 345/350 expected decisions, 0/333 false auto-approvals on unsafe inputs, and 16/350 straight-through approvals. External field extraction remains 7.34%. [Full evidence and limitations](HARDENING.md).
- [Fresh-browser live results](../reports/live-roles.json) confirm all three roles, report access, permissions, uploader ownership, public receipt upload, admin assignment and logout, with no browser JavaScript errors. [Live screenshots](qa/live/).
- Live URL: https://vellum-invoice-desk-atits23.onrender.com. Deployment dep-dc1vqq59fdbs73c14otg reached live for application revision 3e278ce. No paid resources were added.
- Linux CI exposed a delayed dialog-close event cancelling a newly opened run. The final version clears active state on explicit close or Escape and ignores stale asynchronous responses. The corrected workflow passed on Windows and Linux.

Timings depend on CPU, OCR version and cold starts. Fixed corpus dates will age. No production load test, independent security audit, universal OCR accuracy, full manual accessibility certification, live spreadsheet connection, ERP integration or payment execution is claimed. See the [coverage map and remaining gaps](HARDENING.md).

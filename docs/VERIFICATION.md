# Verification status

Recorded 2026-11-23. Only completed checks are claimed.

- Browser: five Playwright tests passed, including signup, verification, login, clean/split/duplicate/ambiguous/scanned workflows, dashboard and logout. Axe WCAG A/AA checks passed on the authenticated dashboard and marketing at 360, 768, 1024 and 1440 pixels.
- Accounts: 12 Node test results passed using Neon PostgreSQL, covering verification, sessions, CSRF, password reset, protected pages and contact persistence.
- PostgreSQL engine: migration, approval, original-file persistence across a new filesystem directory, and duplicate rejection passed against the new Neon project.
- Corpus: 134/134 expected decisions, zero false approvals among 122 unsafe inputs. External field extraction remains 10.53%; review routing is not an extraction success claim.
- Python suite: 62 tests passed, including repeated-line cumulative quantity coverage and HTTP integration. The earlier restricted-shell networking failures passed when rerun with loopback access.
- Docker and Linux CI: configured; awaiting actual GitHub run. Docker is not installed on the local machine.
- Lighthouse: local mobile navigation scored 100 performance, 100 accessibility, 100 best practices and 100 SEO. The generated HTML/JSON report records the machine and tool version. Scores do not prove complete WCAG conformance or guarantee hosted/cold-start performance.
- Public deployment: Render reports live; real signup and provider delivery succeeded. Browser account verification and invoice checks remain in progress.

Reports contain actual timings from the recorded machine. Cold starts, CPU limits and OCR version differences can change them. Corpus timestamps are fixed; the old-invoice policy may intentionally change expected routing as the fixtures age. Regenerate dated synthetic fixtures and independently review labels before a future benchmark.

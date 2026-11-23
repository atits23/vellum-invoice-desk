# Contributing

Keep invoice decisions conservative and explainable. Add a labeled fixture and regression test before changing a rule. Never use engine output as ground truth. Avoid private customer data and record provenance and license for external samples.

Run Python tests, npm tests, Playwright, and corpus evaluation. Any false approval is a release blocker. Report external-layout and per-field regressions even when decision accuracy stays high. Use isolated DATA_DIR directories, never reset a live workspace.

Do not commit credentials, user databases, verification-link logs or private uploads. PR descriptions should explain the operational trigger, resulting behavior and validation.

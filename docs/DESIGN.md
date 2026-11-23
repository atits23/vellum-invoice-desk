# Design and operating model

Vellum uses an original warm-grey editorial marketing design, system typography and code-generated gradients. No customer testimonials, certification badges or external-brand logos are invented. Reduced motion, keyboard controls, accessible labels and measured contrast are included.

The workspace makes the decision evidence visible: original document, normalized values, OCR confidence, pipeline events, rule results and review notes. Progress comes from persisted worker events, not decorative delays. Validation, matching and rule outcomes share an atomic decision phase; its time is not represented as independently benchmarked stage latency.

The financial core uses integer minor units and Decimal arithmetic. A transaction serializes duplicate checks and budget reservations. PostgreSQL uses an advisory transaction lock; SQLite uses BEGIN IMMEDIATE. Corrections rerun the rules and never create a second reservation for an already terminal approval.

Uploads are stored durably in PostgreSQL on free hosting and materialized only for parsing. A bounded subprocess handles PDF/image extraction; interrupted jobs are recovered on startup. This architecture targets a single worker and shared demonstration workspace, not multiple independently scaling job consumers.

Accounts use Argon2id, server-side session revocation and hashed expiring single-use email tokens. Role and ownership authorization is enforced in the gateway, not trusted from the UI. The private engine is loopback-only and credential-protected. Accounting records survive account deletion by design.

OCR and unknown layouts are conservatively reviewed. Item matching is an explainable synonym/lexical mechanism. There is no paid model call, embedding database or claim of general visual reasoning. Email inbox ingestion, ERP and payments remain outside the implemented scope.

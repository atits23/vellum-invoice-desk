# Security policy

Do not publish exploit details or private invoices in a public issue. Contact the repository owner through their GitHub profile to request a private reporting channel. No security email or certification is claimed.

Implemented: Argon2id, hashed expiring single-use verification/reset tokens, server-side revocable sessions, production HttpOnly/Secure/SameSite cookies, origin/CSRF checks, Zod validation, rate limits, Helmet headers, role/ownership checks, isolated parser with timeouts and Unix memory limit, atomic reservations, invoice text treated only as data.

Limits: one shared workspace and service instance, SQLite locally or PostgreSQL on the host, no SSO/MFA, malware scanning or tamper-proof external audit service. Host must provide TLS, storage, backups and ingress limits. Accounting records survive account deletion. Use fictional inputs in public demos.

Production requires HTTPS and Brevo HTTPS API or SMTP credentials. Local development logs verification links; never enable that fallback in public production. Never commit tokens or secrets.

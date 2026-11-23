# Free deployment

Use a new GitHub repository, Render Free web service and Neon Free PostgreSQL project. Do not use a paid disk, paid instance, expiring database trial or paid email plan. This project does not modify other GitHub repositories.

## Required environment

| Variable | Value |
|---|---|
| NODE_ENV | production |
| HOST | 0.0.0.0 |
| PORT | 8000 |
| PUBLIC_URL | Exact https:// service URL |
| DATABASE_URL | Neon PostgreSQL connection string; secret |
| DB_SCHEMA | vellum_accounts |
| ENGINE_DB_SCHEMA | vellum_engine |
| DATA_DIR | /tmp/vellum-data |
| BOOTSTRAP_ADMIN | Owner's verified signup email |
| BREVO_API_KEY | Brevo API key; secret, not SMTP key |
| MAIL_FROM | Verified Brevo sender email |

Render Free blocks outbound SMTP ports 25/465/587, so use Brevo over HTTPS. SMTP_URL is supported for other hosts. Never use development mail logging on a public deployment. Brevo account approval and sender verification are required; an API acceptance response alone does not prove inbox delivery.

## Deploy and verify

1. Create a Render Docker web service from the new repository, choose **Free**, and set the variables above. `render.yaml` provides the configuration. Do not enter any card or enable a paid upgrade.
2. Set the exact PUBLIC_URL and allow automatic deployment from main. Docker installs Python, Tesseract and Poppler.
3. Check `/health`, then use a fresh browser to sign up, receive/verify email and log in. The configured BOOTSTRAP_ADMIN email becomes Admin only after verification.
4. Upload a clean sample and inspect the real events/decision. Upload a duplicate and an over-budget invoice, then inspect review and exports.
5. Restart the service and confirm that accounts, runs, original documents and PO balances remain. PostgreSQL holds these; container scratch files are disposable.
6. Log out and navigate directly to `/app`; it must redirect to login. Test reset email separately.

Neon project: `vellum-invoice-desk` (`shy-morning-90418108`), created in an organization reporting plan `free`. The test schemas are separate from production schemas. The app caps stored upload bytes at 200 MB, but database indexes, accounts and audit records also consume storage. Monitor free quotas; reaching a limit should interrupt service, never trigger an intentional paid upgrade.

Use one service instance/worker. Free Render may sleep after inactivity and take time to start. Do not benchmark a cold start as warm processing latency. No live URL is claimed verified until the end-to-end production check passes.

Sources: [Render Free limitations](https://render.com/docs/free), [Brevo transactional API](https://developers.brevo.com/docs/send-a-transactional-email), [Brevo free email offering](https://www.brevo.com/products/transactional-email/).

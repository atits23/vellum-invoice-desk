# One-cent boundary demo

Use the isolated local recording workspace, not the shared live site's already-consumed PO balances. Run `scripts\start-video-demo.cmd` from E:\Zamp, then open http://localhost:8020. Every launcher invocation creates a new local database; no live data is reset. Stop the prior instance before launching another on the same port.

Login: admin@vellum.example / Vellum-Demo-Admin-2026!

Upload the five PDFs in numbered order. Do not approve the held invoices or change policy during this demonstration. The original files omit item lines, so this demonstrates header, identity, arithmetic and budget controls, not line-item matching. Tax arithmetic is checked; the application is not certifying statutory tax rates.

## Exact narration and actions

1. Show Procurement and the policy setting. Say: "Acme Cloud Services is an approved fictional vendor, identified by ACME-TAX-001. PO-1001 belongs to that vendor and has a one-thousand-dollar value. Our configured allowance is two percent, or twenty dollars. The total permitted commitment is therefore one thousand and twenty dollars."
2. Upload 01-approved-first-invoice.pdf. Say: "This first invoice is six hundred dollars. The vendor, tax ID, PO and currency match, the arithmetic is correct, and the invoice is not a duplicate. It is approved, reserving six hundred dollars. That leaves four hundred and twenty dollars including tolerance. No payment is sent."
3. Upload 02-one-cent-over-remaining.pdf. Expand the budget check. Say: "Here is the edge case. This invoice is four hundred and twenty dollars and one cent. Its vendor and purchase order are valid and its arithmetic passes. But approval would bring the cumulative commitment to one thousand and twenty dollars and one cent. That exceeds our allowance by one cent, so the system sends it to review. A valid vendor alone is not enough for approval."
4. Upload 03-reformatted-duplicate.pdf. Show duplicate check. Say: "This is a reissued copy with a different PDF and changed reference punctuation. The normalized vendor and invoice reference still match the first invoice, so it is rejected as a duplicate. Changing the filename or punctuation does not make it a new invoice." The budget also fails; explain that duplicate identity is the reason this routes to Rejected rather than Review.
5. Upload 04-blocked-vendor.pdf. Show vendor_approved. Say: "This invoice has a matching tax ID and purchase order, and the amount fits its PO. However, this vendor is blocked in our master data. The system holds it for review instead of auto-approving it."
6. Upload 05-exact-boundary-approved.pdf. Say: "Finally, this separate invoice is exactly four hundred and twenty dollars. The cumulative total is exactly one thousand and twenty dollars, which is within the inclusive boundary, so it is approved. Review and rejection did not consume the budget."

For a short video use steps 1–3, then mention the duplicate and vendor controls. For the full demonstration allow about three minutes.

## Thresholds implemented

| Control | Default / rule |
|---|---|
| PO allowance | max(2% of original PO value, absolute allowance 0.00); not the sum of both |
| Available budget | Original PO + allowance - already approved reservations |
| Boundary | Invoice total must be positive and <= available budget |
| Monetary comparisons | Integer minor units (cents); no rounding of the amount before the budget decision |
| Arithmetic | Difference <= one cent for total and supported line-item arithmetic |
| Round-off adjustment | Absolute value <= one currency unit; arithmetic must still balance |
| Vendor | Unique normalized identity, matching tax ID, approved flag = 1; tax-ID-only name variants require verification |
| PO | Same vendor/currency, OPEN and not expired; infer only one eligible candidate when reference absent |
| Duplicates | Same SHA-256 OR same vendor + normalized invoice reference, against active APPROVED/REVIEW records; rejection |
| Suspicious repeat | Same vendor/date/currency/amount but different reference compared with approved records; review until verified |
| Item description | Similarity >= 85%, using curated synonyms and lexical comparison |
| Item quantity / price | Cumulative quantity <= PO quantity; unit price <= PO unit price; matching units |
| OCR | Below 85% is flagged low confidence; all OCR requires human verification, even above 85% |
| Dates | No future invoice date; due date >= invoice date; age <= 365 days |

The one-cent-over case is a 2.001% cumulative excess. The current explanatory percentage rounds to two decimal places (2.00%), but the displayed requested/available amounts and integer-cent comparison remain exact. Explain the $420.01 versus $420.00 amounts on screen.

The 2% allowance and 85% description cutoff are explicit prototype policies, not statistically calibrated or universal legal/accounting requirements. Admins can edit the percentage and absolute budget allowances. Uploaded invoice text cannot change these rules.

`verified-results.json` records actual engine decisions. Rebuild with `python scripts/build_video_demo.py` to refresh dates and rerun verification. The launcher starts a fresh recording database; the generator's automated test uses a separate temporary database.

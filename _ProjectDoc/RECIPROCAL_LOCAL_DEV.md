# Reciprocal Features — Local Dev Notes

Use this when testing International Partners (e.g., ASCAP) flows locally.

Environment variables (add to `.env.local`):
- `PARTNER_EXPORT_DIR` — absolute or project-relative path where partner exports (CSV, statements) are written.
- `DEFAULT_ADMIN_FEE_PERCENT` — default admin fee percent for partners (e.g., `15.00`).

Conventions:
- `TIME_ZONE=Africa/Accra`
- Currency: GHS in calculations and CSV exports

Artifacts:
- Sample repertoire CSV: `zamio_backend/sample_partner_import.csv`
- Exports: written under `PARTNER_EXPORT_DIR` by cycle and partner

Admin E2E steps:
1) Create Partner PRO + ReciprocalAgreement (GH)
2) Import repertoire (CSV)
3) Close a royalty cycle
4) Generate partner export (CSV baseline)
5) Create remittance; mark Sent/Settled

See also:
- `reciprocal_info.md`
- `reciprocal_implementation.md`
- `zamio_reciprocal_doc.md`

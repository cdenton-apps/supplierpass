# SupplierPass v0.9

Process-driven Streamlit prototype for supplier compliance, document processing, supplier readiness, evidence gaps, issue logs, timeline history, demo mode, import profiles and audit exports.

## Recommended app

Use:

```text
app_v09.py
```

Older prototype files remain in the repo for reference. `app_v09.py` is the current recommended version because it adds a clear document processing workflow.

## What v0.9 improves

- Clear Document Processing screen
- Uploaded documents now require review before counting as accepted evidence
- Review decisions: Uploaded, Under Review, Accepted, Rejected / Needs replacement
- Supplier readiness recalculates after document review
- Evidence gaps now distinguish between missing, expired, expiring and needs-review documents
- Today screen tells users what to process next
- Supplier profile shows the current checklist and timeline
- Upload screen explains that upload does not equal approval
- Audit pack export

## Setup

Run locally with:

```bash
pip install -r requirements.txt
streamlit run app_v09.py
```

The app creates local folders/files:

```text
data/supplierpass.db
uploads/
```

## Streamlit Community Cloud

Use:

- Repository: `cdenton-apps/supplierpass`
- Branch: `main`
- Main file path: `app_v09.py`

## Processing documents

The intended process is:

1. Go to `Risk & Compliance > Upload Document`
2. Upload the supplier document
3. Go to `Document Processing`
4. Confirm the document type and expiry date
5. Mark it as `Accepted`
6. Supplier readiness and evidence gaps update automatically

An uploaded document that is not accepted yet will show as needing review.

## Important commercialisation note

This is a commercial-style prototype, not yet a production SaaS product.

Before selling or hosting for customers, add authentication, role-based permissions, tenant separation, secure document storage, backups, licensing controls and formal security/privacy documentation.

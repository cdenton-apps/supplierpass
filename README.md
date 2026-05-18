# SupplierPass v0.10

Stable document-workflow Streamlit prototype for supplier compliance, document upload, document processing, supplier readiness, evidence gaps, issue logs, timeline history and audit exports.

## Recommended app

Use:

```text
app_v10.py
```

`app_v10.py` is the current recommended version because it fixes the orphaned-document crash and adds a safer document reassignment workflow.

## What v0.10 improves

- Separate Upload Document and Document Processing screens
- Uploaded documents do not count as evidence until accepted
- Document Processing lets you accept, reject, review, archive or reassign documents
- Old/orphaned documents show as Unlinked document instead of crashing
- Supplier readiness recalculates after document processing
- Evidence gaps now distinguish between missing, expired, expiring and needs-review documents
- Today screen tells users what to process next
- Supplier profile shows current checklist and timeline
- Audit pack export

## Setup

Run locally with:

```bash
pip install -r requirements.txt
streamlit run app_v10.py
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
- Main file path: `app_v10.py`

## Processing documents

The intended process is:

1. Go to `Upload Document`
2. Upload the supplier document
3. Go to `Document Processing`
4. Confirm or reassign the supplier
5. Confirm the document type and expiry date
6. Mark it as `Accepted`
7. Supplier readiness and evidence gaps update automatically

An uploaded document that is not accepted yet will show as needing review.

## Important commercialisation note

This is a commercial-style prototype, not yet a production SaaS product.

Before selling or hosting for customers, add authentication, role-based permissions, tenant separation, secure document storage, backups, licensing controls and formal security/privacy documentation.

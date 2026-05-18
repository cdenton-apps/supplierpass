# SupplierPass v0.11

Stable Streamlit prototype for supplier onboarding approvals, supplier compliance, document upload, document processing, supplier readiness, evidence gaps, issue logs, timeline history and audit exports.

## Recommended app

Use:

```text
app_v11.py
```

`app_v11.py` is the current recommended version because it keeps the stable document workflow from v0.10 and adds a clear onboarding Approval Queue.

## What v0.11 improves

- Adds a dedicated `Approval Queue`
- Onboarding requests can now be submitted, approved, rejected and converted to suppliers
- Converted requests create an approved supplier record
- Request decision notes, approver name and approval timestamp are stored
- Today screen shows onboarding requests needing action
- Keeps the safer document processing workflow from v0.10
- Old/orphaned documents show as Unlinked document instead of crashing
- Audit pack export includes onboarding requests

## Setup

Run locally with:

```bash
pip install -r requirements.txt
streamlit run app_v11.py
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
- Main file path: `app_v11.py`

## Onboarding approval process

1. Go to `Onboarding`
2. Create a new supplier request
3. Tick `Submit for approval now`, or leave as draft
4. Go to `Approval Queue`
5. Select the request
6. Click `Submit for approval`, `Approve`, `Reject`, or `Convert to supplier`
7. Once converted, the supplier appears in the Supplier Register

## Document process

1. Go to `Upload Document`
2. Upload the supplier document
3. Go to `Document Processing`
4. Confirm or reassign the supplier
5. Confirm the document type and expiry date
6. Mark it as `Accepted`
7. Supplier readiness and evidence gaps update automatically

## Important commercialisation note

This is a commercial-style prototype, not yet a production SaaS product.

Before selling or hosting for customers, add authentication, role-based permissions, tenant separation, secure document storage, backups, licensing controls and formal security/privacy documentation.

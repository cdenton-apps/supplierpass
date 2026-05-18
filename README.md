# SupplierPass v0.12

Stable Streamlit prototype for status-aware supplier onboarding approvals, supplier compliance, document upload, document processing, supplier readiness, evidence gaps, timeline history and audit exports.

## Recommended app

Use:

```text
app_v12.py
```

`app_v12.py` is the current recommended version because it fixes the approval queue so actions depend on request status.

## What v0.12 improves

- Approval buttons are now status-aware
- Draft requests only show `Submit for approval`
- Awaiting Approval requests show `Approve & Create Supplier` and `Reject`
- Approval automatically creates the supplier record
- No separate confusing `Convert to supplier` step after approval
- Converted requests cannot be approved again
- Rejected requests cannot be accidentally converted
- Keeps the safer document processing workflow from v0.10/v0.11
- Old/orphaned documents show as Unlinked document instead of crashing
- Audit pack export includes onboarding requests

## Setup

Run locally with:

```bash
pip install -r requirements.txt
streamlit run app_v12.py
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
- Main file path: `app_v12.py`

## Onboarding approval process

1. Go to `Onboarding`
2. Create a new supplier request
3. Tick `Submit for approval now`, or leave as draft
4. Go to `Approval Queue`
5. If Draft, click `Submit for approval`
6. If Awaiting Approval, click `Approve & Create Supplier` or `Reject`
7. Once approved, the supplier appears automatically in the Supplier Register

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

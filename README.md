# SupplierPass v0.7

Commercial-polish Streamlit prototype for supplier compliance, role-based views, audit readiness, supplier review cycles, issue logs, timeline history, demo mode, import profiles, email templates and audit exports.

## Recommended app

Use:

```text
app_v07.py
```

Older prototype files remain in the repo for reference:

- `app.py` - original v0.1 supplier/document tracker prototype
- `app_v02.py` - approval-stage and email workflow prototype
- `app_v03.py` - combined supplier import, supplier document upload, approvals and email workflow
- `app_v04.py` - guided process version
- `app_v05.py` - commercial prototype
- `app_v06.py` - commercial-plus prototype with pre-approval and stronger business controls
- `app_v07.py` - commercial polish prototype with user-friendly dashboards and demo/sales features

## What v0.7 adds

- Today screen
- Role-based views for Management, Procurement, Quality, Finance and Admin
- Audit Readiness Score
- Value Tracker
- Supplier segmentation/readiness improvements
- Supplier Review Cycle
- Supplier Issue Log
- Supplier Timeline
- Demo Mode / load demo data
- Implementation Checklist
- Import profiles for Generic CSV, Sage 200, Sage 50, Business Central, Xero
- Email Template Library
- Can I Buy? explanation panel
- Supplier Portal Preview
- Cleaner commercial-style navigation

## Setup

Run locally with:

```bash
pip install -r requirements.txt
streamlit run app_v07.py
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
- Main file path: `app_v07.py`

## Suggested demo flow

1. Open Today
2. Load demo data from Admin if needed
3. Review Role Views
4. Import suppliers or inspect the demo register
5. Open a Supplier Profile and check Can I Buy? / Readiness
6. Add a supplier issue
7. Upload a supplier document
8. Review Evidence Gaps
9. Check Audit Readiness and Value Tracker
10. Export the audit pack

## Supplier file upload

Go to:

`Suppliers > Import`

Available import profiles:

- Generic CSV
- Sage 200 Supplier Export
- Sage 50 Supplier Export
- Business Central Vendor Export
- Xero Contacts Export

The import screen pre-maps likely columns but still lets you override every mapping.

## Important commercialisation note

This is a commercial-style prototype, not yet a production SaaS product.

Before selling or hosting for customers, add:

- authentication and user accounts
- role-based permissions
- tenant/company separation
- secure cloud file storage
- database backups
- production database server
- audit log hardening
- encrypted secrets management
- licensing/subscription controls
- terms/privacy/security documentation

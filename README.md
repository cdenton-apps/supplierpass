# SupplierPass v0.1

Internal Streamlit prototype for supplier compliance tracking and new supplier onboarding.

## What it includes

- Supplier register
- CSV supplier import
- Supplier profiles
- Category-based document requirement rules
- Document upload and expiry tracking
- Red / amber / green compliance status
- New supplier request workflow
- Chase email generation
- Chase log
- Audit log
- CSV and Excel exports

## Setup

Run locally with:

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app creates local folders/files:

```text
data/supplierpass.db
uploads/
```

## Suggested CSV import columns

```csv
SupplierCode,SupplierName,SupplierEmail,Category,Owner,ApprovalStatus,Notes
SUP001,ABC Transport Ltd,accounts@example.com,Transport,Connor,Approved,Main haulage supplier
```

## Streamlit Community Cloud

Use:

- Repository: `cdenton-apps/supplierpass`
- Branch: `main`
- Main file path: `app.py`

## Important prototype note

This is an internal prototype, not a production SaaS product.

Do not upload confidential supplier documents, bank details, live contracts, or sensitive company data to a public deployment. Use sample data until authentication, secure storage, tenant separation and proper access controls are added.

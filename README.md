# SupplierPass v0.4

Internal Streamlit prototype for supplier compliance tracking, supplier file import, supplier document management, new supplier onboarding, approval routing, and optional email sending.

## Main apps

There are currently four app entry points:

- `app.py` - original v0.1 supplier/document tracker prototype
- `app_v02.py` - approval-stage and email workflow prototype
- `app_v03.py` - combined supplier import, supplier document upload, approvals and email workflow
- `app_v04.py` - guided process version with clearer step-by-step navigation

For the next test, use `app_v04.py`.

## What v0.4 improves

- Guided process menu instead of scattered screens
- Home page showing what to do next
- Clear steps from supplier import through to reporting
- Supplier CSV upload/import
- Supplier document upload
- Required document rules by category
- Missing/expired/expiring document action list
- New supplier request process
- Approval-stage routing
- Approver email preview/logging
- Optional SMTP email sending using Streamlit secrets
- CSV and Excel exports

## Setup

Run locally with:

```bash
pip install -r requirements.txt
streamlit run app_v04.py
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
- Main file path: `app_v04.py`

## Recommended process

1. Import suppliers
2. Set document rules and approval-stage approvers
3. Upload supplier documents
4. Create new supplier requests
5. Review and approve requests
6. Chase missing or expiring documents
7. Export reports

## Supplier file upload

Go to:

`1. Import Suppliers > Import supplier file`

Suggested CSV columns:

```csv
SupplierCode,SupplierName,SupplierEmail,Category,Owner,ApprovalStatus,Notes
SUP001,ABC Transport Ltd,accounts@example.com,Transport,Connor,Approved,Main haulage supplier
```

The import screen lets you map your own column names, so the file does not have to match exactly.

## Approval-stage import

Go to:

`2. Set Rules & Approvers > Approval stages > Bulk import approval stages`

Expected columns:

```csv
Category,StageName,ApproverName,ApproverEmail,Order
Packaging,Procurement Review,Connor,connor@example.com,1
Packaging,Quality Review,Quality Manager,quality@example.com,2
Packaging,Finance Review,Finance,finance@example.com,3
```

## Email sending

By default, v0.4 previews and logs emails only. To send real emails, add SMTP secrets in Streamlit Community Cloud under:

`App > Settings > Secrets`

Example:

```toml
SMTP_HOST = "smtp.office365.com"
SMTP_PORT = 587
SMTP_USER = "supplierpass@yourcompany.co.uk"
SMTP_PASSWORD = "your-password-or-app-password"
FROM_EMAIL = "supplierpass@yourcompany.co.uk"
REPLY_TO_EMAIL = "your.name@yourcompany.co.uk"
```

Do not commit real passwords or API keys to GitHub.

Many Microsoft 365 tenants block SMTP authentication. If SMTP does not work, keep preview/log mode for the prototype and later move to Microsoft Graph, Postmark, or SendGrid.

## Important prototype note

This is an internal prototype, not a production SaaS product.

Do not upload confidential supplier documents, bank details, live contracts, or sensitive company data to a public deployment. Use sample data until authentication, secure storage, tenant separation and proper access controls are added.

# SupplierPass v0.5

Commercial-style Streamlit prototype for supplier compliance tracking, supplier document management, new supplier onboarding, approval routing, email chasing, health scoring, and audit exports.

## Recommended app

Use:

```text
app_v05.py
```

Older prototype files remain in the repo for reference:

- `app.py` - original v0.1 supplier/document tracker prototype
- `app_v02.py` - approval-stage and email workflow prototype
- `app_v03.py` - combined supplier import, supplier document upload, approvals and email workflow
- `app_v04.py` - guided process version
- `app_v05.py` - commercial prototype with improved UI and broader functionality

## What v0.5 adds

- Commercial-style Command Centre dashboard
- Cleaner product-style navigation
- Supplier health score
- Supplier risk/spend/criticality fields
- Supplier register import and filtering
- Supplier profile editing
- Required document rules by category
- Supplier document upload and expiry tracking
- Missing/expired/expiring document action list
- Supplier document chase email preview/logging
- New supplier onboarding workflow
- Approval route management by supplier category
- Approval-stage emails
- Email log
- Audit-ready Excel export
- CSV compliance export
- Safe database migrations from earlier prototype versions

## Setup

Run locally with:

```bash
pip install -r requirements.txt
streamlit run app_v05.py
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
- Main file path: `app_v05.py`

## Suggested workflow

1. Open the Command Centre
2. Import suppliers from CSV
3. Set document rules and approval routes
4. Upload supplier documents
5. Review the compliance action list
6. Create new supplier onboarding requests
7. Approve/reject supplier requests
8. Export the audit pack

## Supplier file upload

Go to:

`Suppliers > Import`

Suggested CSV columns:

```csv
SupplierCode,SupplierName,SupplierEmail,Category,Owner,ApprovalStatus,AnnualSpend,Notes
SUP001,ABC Transport Ltd,accounts@example.com,Transport,Connor,Approved,12000,Main haulage supplier
```

The import screen lets you map your own column names, so your file does not have to match exactly.

## Email sending

By default, v0.5 previews and logs emails only. To send real emails, add SMTP secrets in Streamlit Community Cloud under:

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

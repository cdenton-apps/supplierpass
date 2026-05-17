# SupplierPass v0.6

Commercial-plus Streamlit prototype for supplier compliance, pre-approval, supplier readiness, evidence gaps, document chasing, onboarding approvals, finance verification, risk rules and audit exports.

## Recommended app

Use:

```text
app_v06.py
```

Older prototype files remain in the repo for reference:

- `app.py` - original v0.1 supplier/document tracker prototype
- `app_v02.py` - approval-stage and email workflow prototype
- `app_v03.py` - combined supplier import, supplier document upload, approvals and email workflow
- `app_v04.py` - guided process version
- `app_v05.py` - commercial prototype
- `app_v06.py` - commercial-plus prototype with pre-approval and stronger business controls

## What v0.6 adds

- Pre-Approval Builder
- Company/VAT/sanctions status capture for pre-checks
- Domain/free-email warning logic
- Duplicate supplier warning
- Supplier confidence rating
- Supplier information pack email generator
- Create request or pending supplier from a pre-approval profile
- Can I Buy? supplier decision badge
- Supplier readiness score
- Evidence Gaps screen
- Industry document templates
- Finance/bank verification tracker
- Data quality checks
- Owner accountability dashboard
- Risk rules register
- Management summary
- Audit Mode and full Excel audit export

## Setup

Run locally with:

```bash
pip install -r requirements.txt
streamlit run app_v06.py
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
- Main file path: `app_v06.py`

## Suggested workflow

1. Open the Command Centre
2. Use Pre-Approval to create a checked supplier profile
3. Import or manually add suppliers
4. Apply industry document templates
5. Upload supplier documents and expiry dates
6. Review Evidence Gaps and Data Quality
7. Create and approve new supplier requests
8. Complete finance/bank verification
9. Export the audit pack

## Supplier file upload

Go to:

`Suppliers > Import`

Suggested CSV columns:

```csv
SupplierCode,SupplierName,SupplierEmail,Category,Owner,ApprovalStatus,AnnualSpend,CompanyNumber,VATNumber,Website,Notes
SUP001,ABC Transport Ltd,accounts@example.com,Transport,Connor,Approved,12000,12345678,GB123456789,https://example.com,Main haulage supplier
```

The import screen lets you map your own column names, so your file does not have to match exactly.

## Pre-approval checks

In this prototype, Companies House, VAT and sanctions checks are manually captured or simulated by the user. This lets the workflow be tested before connecting real APIs.

Later production integrations could include:

- Companies House API
- HMRC VAT validation
- OFSI sanctions data
- credit-score providers
- Microsoft Graph email
- Sage / Business Central / Xero connectors

## Email sending

By default, v0.6 previews and logs emails only. To send real emails, add SMTP secrets in Streamlit Community Cloud under:

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

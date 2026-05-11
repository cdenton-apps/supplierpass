# SupplierPass v0.2

Internal Streamlit prototype for supplier compliance tracking, new supplier onboarding, approval routing, and optional email sending.

## Main apps

There are currently two app entry points:

- `app.py` - original v0.1 supplier/document tracker prototype
- `app_v02.py` - approval-stage and email workflow prototype

For the next test, use `app_v02.py`.

## What v0.2 includes

- New supplier requests
- Configurable approval stages by supplier category
- Approver name and email per stage
- Approval route display
- Approve/reject workflow
- Automatic move to the next approval stage
- Email preview and email log
- Optional SMTP email sending using Streamlit secrets
- Convert approved request to supplier register

## Setup

Run locally with:

```bash
pip install -r requirements.txt
streamlit run app_v02.py
```

The app creates local folders/files:

```text
data/supplierpass.db
```

## Streamlit Community Cloud

Use:

- Repository: `cdenton-apps/supplierpass`
- Branch: `main`
- Main file path: `app_v02.py`

## Email sending

By default, v0.2 previews and logs emails only. To send real emails, add SMTP secrets in Streamlit Community Cloud under:

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

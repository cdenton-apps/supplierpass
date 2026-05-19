CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_code TEXT,
    supplier_name TEXT NOT NULL,
    supplier_key TEXT,
    supplier_email TEXT,
    email_key TEXT,
    category TEXT,
    owner TEXT,
    approval_status TEXT DEFAULT 'Pending',
    app_status TEXT DEFAULT 'Active',
    risk_level TEXT DEFAULT 'Medium',
    annual_spend REAL DEFAULT 0,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS supplier_documents (
    document_id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER,
    document_type TEXT,
    file_name TEXT,
    expiry_date TEXT,
    review_status TEXT DEFAULT 'Uploaded',
    reviewed_by TEXT,
    review_notes TEXT,
    notes TEXT,
    uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TEXT
);

CREATE TABLE IF NOT EXISTS new_supplier_requests (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_name TEXT NOT NULL,
    supplier_email TEXT,
    requested_by TEXT,
    category TEXT,
    reason_needed TEXT,
    expected_annual_spend REAL DEFAULT 0,
    urgency TEXT DEFAULT 'Normal',
    status TEXT DEFAULT 'Draft',
    approval_decision TEXT,
    approval_notes TEXT,
    approved_by TEXT,
    approved_at TEXT,
    converted_supplier_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS preferred_suppliers (
    preference_id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    is_preferred INTEGER DEFAULT 1,
    reason TEXT,
    set_by TEXT,
    set_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(supplier_id, category)
);

CREATE TABLE IF NOT EXISTS email_log (
    email_id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER,
    email_type TEXT,
    recipient TEXT,
    subject TEXT,
    body TEXT,
    status TEXT DEFAULT 'Drafted',
    sent_by TEXT,
    sent_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_templates (
    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_type TEXT UNIQUE,
    subject TEXT,
    body TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS po_history (
    po_id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER,
    supplier_name TEXT,
    supplier_key TEXT,
    item_code TEXT,
    item_description TEXT,
    po_number TEXT,
    po_date TEXT,
    promised_date TEXT,
    received_date TEXT,
    quantity REAL DEFAULT 0,
    unit_price REAL DEFAULT 0,
    total_value REAL DEFAULT 0,
    source_file TEXT,
    uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS supplier_prices (
    price_id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER,
    supplier_name TEXT,
    supplier_key TEXT,
    item_code TEXT,
    item_description TEXT,
    category TEXT,
    unit_price REAL DEFAULT 0,
    currency TEXT DEFAULT 'GBP',
    lead_time_days REAL,
    source_file TEXT,
    uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS erp_action_queue (
    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER,
    supplier_code TEXT,
    supplier_name TEXT,
    action_type TEXT,
    action_reason TEXT,
    old_value TEXT,
    new_value TEXT,
    status TEXT DEFAULT 'Pending Export',
    created_by TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    exported_at TEXT
);

CREATE TABLE IF NOT EXISTS recommendation_history (
    recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    requirement TEXT,
    category TEXT,
    chosen_supplier TEXT,
    recommended_supplier TEXT,
    reason TEXT,
    created_by TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sync_log (
    sync_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_name TEXT,
    source_system TEXT,
    status TEXT,
    rows_read INTEGER DEFAULT 0,
    rows_inserted INTEGER DEFAULT 0,
    rows_updated INTEGER DEFAULT 0,
    message TEXT,
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT,
    entity_id TEXT,
    action TEXT,
    old_value TEXT,
    new_value TEXT,
    changed_by TEXT,
    changed_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_suppliers_key ON suppliers(supplier_key);
CREATE INDEX IF NOT EXISTS ix_suppliers_code ON suppliers(supplier_code);
CREATE INDEX IF NOT EXISTS ix_po_supplier ON po_history(supplier_id);
CREATE INDEX IF NOT EXISTS ix_prices_supplier_item ON supplier_prices(supplier_id, item_code);
CREATE INDEX IF NOT EXISTS ix_erp_action_status ON erp_action_queue(status);

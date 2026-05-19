IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Suppliers' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.Suppliers (
        SupplierID int IDENTITY(1,1) PRIMARY KEY,
        SupplierCode nvarchar(50) NULL,
        SupplierName nvarchar(255) NOT NULL,
        SupplierKey nvarchar(255) NULL,
        SupplierEmail nvarchar(255) NULL,
        EmailKey nvarchar(255) NULL,
        Category nvarchar(100) NULL,
        Owner nvarchar(100) NULL,
        ApprovalStatus nvarchar(50) NOT NULL CONSTRAINT DF_Suppliers_ApprovalStatus DEFAULT 'Pending',
        AppStatus nvarchar(50) NOT NULL CONSTRAINT DF_Suppliers_AppStatus DEFAULT 'Active',
        RiskLevel nvarchar(50) NOT NULL CONSTRAINT DF_Suppliers_RiskLevel DEFAULT 'Medium',
        AnnualSpend decimal(18,2) NOT NULL CONSTRAINT DF_Suppliers_AnnualSpend DEFAULT 0,
        Notes nvarchar(max) NULL,
        CreatedAt datetime2 NOT NULL CONSTRAINT DF_Suppliers_CreatedAt DEFAULT sysdatetime(),
        UpdatedAt datetime2 NOT NULL CONSTRAINT DF_Suppliers_UpdatedAt DEFAULT sysdatetime()
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'SupplierDocuments' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.SupplierDocuments (
        DocumentID int IDENTITY(1,1) PRIMARY KEY,
        SupplierID int NULL,
        DocumentType nvarchar(150) NULL,
        FileName nvarchar(500) NULL,
        ExpiryDate date NULL,
        ReviewStatus nvarchar(80) NOT NULL CONSTRAINT DF_SupplierDocuments_ReviewStatus DEFAULT 'Uploaded',
        ReviewedBy nvarchar(100) NULL,
        ReviewNotes nvarchar(max) NULL,
        Notes nvarchar(max) NULL,
        UploadedAt datetime2 NOT NULL CONSTRAINT DF_SupplierDocuments_UploadedAt DEFAULT sysdatetime(),
        ReviewedAt datetime2 NULL
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'SupplierApprovalRequests' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.SupplierApprovalRequests (
        RequestID int IDENTITY(1,1) PRIMARY KEY,
        SupplierName nvarchar(255) NOT NULL,
        SupplierEmail nvarchar(255) NULL,
        RequestedBy nvarchar(100) NULL,
        Category nvarchar(100) NULL,
        ReasonNeeded nvarchar(max) NULL,
        ExpectedAnnualSpend decimal(18,2) NOT NULL CONSTRAINT DF_SupplierApprovalRequests_Spend DEFAULT 0,
        Urgency nvarchar(50) NOT NULL CONSTRAINT DF_SupplierApprovalRequests_Urgency DEFAULT 'Normal',
        Status nvarchar(50) NOT NULL CONSTRAINT DF_SupplierApprovalRequests_Status DEFAULT 'Draft',
        ApprovalDecision nvarchar(100) NULL,
        ApprovalNotes nvarchar(max) NULL,
        ApprovedBy nvarchar(100) NULL,
        ApprovedAt datetime2 NULL,
        ConvertedSupplierID int NULL,
        CreatedAt datetime2 NOT NULL CONSTRAINT DF_SupplierApprovalRequests_CreatedAt DEFAULT sysdatetime(),
        UpdatedAt datetime2 NOT NULL CONSTRAINT DF_SupplierApprovalRequests_UpdatedAt DEFAULT sysdatetime()
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'PreferredSuppliers' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.PreferredSuppliers (
        PreferenceID int IDENTITY(1,1) PRIMARY KEY,
        SupplierID int NOT NULL,
        Category nvarchar(100) NOT NULL,
        IsPreferred bit NOT NULL CONSTRAINT DF_PreferredSuppliers_IsPreferred DEFAULT 1,
        Reason nvarchar(max) NULL,
        SetBy nvarchar(100) NULL,
        SetAt datetime2 NOT NULL CONSTRAINT DF_PreferredSuppliers_SetAt DEFAULT sysdatetime(),
        CONSTRAINT UQ_PreferredSuppliers_Supplier_Category UNIQUE (SupplierID, Category)
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'EmailLog' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.EmailLog (
        EmailID int IDENTITY(1,1) PRIMARY KEY,
        SupplierID int NULL,
        EmailType nvarchar(100) NULL,
        Recipient nvarchar(255) NULL,
        Subject nvarchar(500) NULL,
        Body nvarchar(max) NULL,
        Status nvarchar(80) NOT NULL CONSTRAINT DF_EmailLog_Status DEFAULT 'Drafted',
        SentBy nvarchar(100) NULL,
        SentAt datetime2 NOT NULL CONSTRAINT DF_EmailLog_SentAt DEFAULT sysdatetime()
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'EmailTemplates' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.EmailTemplates (
        TemplateID int IDENTITY(1,1) PRIMARY KEY,
        TemplateType nvarchar(100) NOT NULL UNIQUE,
        Subject nvarchar(500) NULL,
        Body nvarchar(max) NULL,
        UpdatedAt datetime2 NOT NULL CONSTRAINT DF_EmailTemplates_UpdatedAt DEFAULT sysdatetime()
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'PurchaseOrderHistory' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.PurchaseOrderHistory (
        POID int IDENTITY(1,1) PRIMARY KEY,
        SupplierID int NULL,
        SupplierName nvarchar(255) NULL,
        SupplierKey nvarchar(255) NULL,
        ItemCode nvarchar(100) NULL,
        ItemDescription nvarchar(500) NULL,
        PONumber nvarchar(100) NULL,
        PODate date NULL,
        PromisedDate date NULL,
        ReceivedDate date NULL,
        Quantity decimal(18,4) NOT NULL CONSTRAINT DF_PurchaseOrderHistory_Quantity DEFAULT 0,
        UnitPrice decimal(18,4) NOT NULL CONSTRAINT DF_PurchaseOrderHistory_UnitPrice DEFAULT 0,
        TotalValue decimal(18,2) NOT NULL CONSTRAINT DF_PurchaseOrderHistory_TotalValue DEFAULT 0,
        SourceFile nvarchar(255) NULL,
        UploadedAt datetime2 NOT NULL CONSTRAINT DF_PurchaseOrderHistory_UploadedAt DEFAULT sysdatetime()
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'SupplierPrices' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.SupplierPrices (
        PriceID int IDENTITY(1,1) PRIMARY KEY,
        SupplierID int NULL,
        SupplierName nvarchar(255) NULL,
        SupplierKey nvarchar(255) NULL,
        ItemCode nvarchar(100) NULL,
        ItemDescription nvarchar(500) NULL,
        Category nvarchar(100) NULL,
        UnitPrice decimal(18,4) NOT NULL CONSTRAINT DF_SupplierPrices_UnitPrice DEFAULT 0,
        Currency nvarchar(10) NOT NULL CONSTRAINT DF_SupplierPrices_Currency DEFAULT 'GBP',
        LeadTimeDays decimal(18,2) NULL,
        SourceFile nvarchar(255) NULL,
        UploadedAt datetime2 NOT NULL CONSTRAINT DF_SupplierPrices_UploadedAt DEFAULT sysdatetime()
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'ERPActionQueue' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.ERPActionQueue (
        ActionID int IDENTITY(1,1) PRIMARY KEY,
        SupplierID int NULL,
        SupplierCode nvarchar(50) NULL,
        SupplierName nvarchar(255) NULL,
        ActionType nvarchar(100) NULL,
        ActionReason nvarchar(max) NULL,
        OldValue nvarchar(500) NULL,
        NewValue nvarchar(500) NULL,
        Status nvarchar(80) NOT NULL CONSTRAINT DF_ERPActionQueue_Status DEFAULT 'Pending Export',
        CreatedBy nvarchar(100) NULL,
        CreatedAt datetime2 NOT NULL CONSTRAINT DF_ERPActionQueue_CreatedAt DEFAULT sysdatetime(),
        ExportedAt datetime2 NULL
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'RecommendationHistory' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.RecommendationHistory (
        RecommendationID int IDENTITY(1,1) PRIMARY KEY,
        Requirement nvarchar(max) NULL,
        Category nvarchar(100) NULL,
        ChosenSupplier nvarchar(255) NULL,
        RecommendedSupplier nvarchar(255) NULL,
        Reason nvarchar(max) NULL,
        CreatedBy nvarchar(100) NULL,
        CreatedAt datetime2 NOT NULL CONSTRAINT DF_RecommendationHistory_CreatedAt DEFAULT sysdatetime()
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'SyncLog' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.SyncLog (
        SyncID int IDENTITY(1,1) PRIMARY KEY,
        SyncName nvarchar(100) NULL,
        SourceSystem nvarchar(100) NULL,
        Status nvarchar(50) NULL,
        RowsRead int NOT NULL CONSTRAINT DF_SyncLog_RowsRead DEFAULT 0,
        RowsInserted int NOT NULL CONSTRAINT DF_SyncLog_RowsInserted DEFAULT 0,
        RowsUpdated int NOT NULL CONSTRAINT DF_SyncLog_RowsUpdated DEFAULT 0,
        Message nvarchar(max) NULL,
        StartedAt datetime2 NOT NULL CONSTRAINT DF_SyncLog_StartedAt DEFAULT sysdatetime(),
        FinishedAt datetime2 NULL
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'AuditLog' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.AuditLog (
        AuditID int IDENTITY(1,1) PRIMARY KEY,
        EntityType nvarchar(100) NULL,
        EntityID nvarchar(100) NULL,
        Action nvarchar(100) NULL,
        OldValue nvarchar(max) NULL,
        NewValue nvarchar(max) NULL,
        ChangedBy nvarchar(100) NULL,
        ChangedAt datetime2 NOT NULL CONSTRAINT DF_AuditLog_ChangedAt DEFAULT sysdatetime()
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Suppliers_SupplierKey')
    CREATE INDEX IX_Suppliers_SupplierKey ON dbo.Suppliers(SupplierKey);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Suppliers_SupplierCode')
    CREATE INDEX IX_Suppliers_SupplierCode ON dbo.Suppliers(SupplierCode);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_PurchaseOrderHistory_SupplierID')
    CREATE INDEX IX_PurchaseOrderHistory_SupplierID ON dbo.PurchaseOrderHistory(SupplierID);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_SupplierPrices_Supplier_Item')
    CREATE INDEX IX_SupplierPrices_Supplier_Item ON dbo.SupplierPrices(SupplierID, ItemCode);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_ERPActionQueue_Status')
    CREATE INDEX IX_ERPActionQueue_Status ON dbo.ERPActionQueue(Status);
GO

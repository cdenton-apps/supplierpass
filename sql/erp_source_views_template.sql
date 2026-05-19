/*
SupplierPass ERP source view templates

Create views like these in the ERP/reporting database, or in a reporting database
that can read the ERP tables. Keep them read-only.

The Python connector expects these view names and columns:

- vw_SupplierPass_ERP_Suppliers
- vw_SupplierPass_ERP_PurchaseOrders
- vw_SupplierPass_ERP_SupplierPrices

Do not update live ERP tables directly from SupplierPass at this stage.
*/

CREATE OR ALTER VIEW dbo.vw_SupplierPass_ERP_Suppliers AS
SELECT
    CAST(NULL AS nvarchar(50)) AS SupplierCode,
    CAST(NULL AS nvarchar(255)) AS SupplierName,
    CAST(NULL AS nvarchar(255)) AS SupplierEmail,
    CAST(NULL AS nvarchar(100)) AS Category,
    CAST(NULL AS nvarchar(50)) AS IsActive,
    CAST(NULL AS nvarchar(100)) AS RawStatus,
    CAST(NULL AS datetime2) AS SourceUpdatedAt;
GO

CREATE OR ALTER VIEW dbo.vw_SupplierPass_ERP_PurchaseOrders AS
SELECT
    CAST(NULL AS nvarchar(50)) AS SupplierCode,
    CAST(NULL AS nvarchar(255)) AS SupplierName,
    CAST(NULL AS nvarchar(100)) AS ItemCode,
    CAST(NULL AS nvarchar(500)) AS ItemDescription,
    CAST(NULL AS nvarchar(100)) AS PONumber,
    CAST(NULL AS date) AS PODate,
    CAST(NULL AS date) AS PromisedDate,
    CAST(NULL AS date) AS ReceivedDate,
    CAST(NULL AS decimal(18,4)) AS Quantity,
    CAST(NULL AS decimal(18,4)) AS UnitPrice,
    CAST(NULL AS decimal(18,2)) AS TotalValue;
GO

CREATE OR ALTER VIEW dbo.vw_SupplierPass_ERP_SupplierPrices AS
SELECT
    CAST(NULL AS nvarchar(50)) AS SupplierCode,
    CAST(NULL AS nvarchar(255)) AS SupplierName,
    CAST(NULL AS nvarchar(100)) AS ItemCode,
    CAST(NULL AS nvarchar(500)) AS ItemDescription,
    CAST(NULL AS nvarchar(100)) AS Category,
    CAST(NULL AS decimal(18,4)) AS UnitPrice,
    CAST('GBP' AS nvarchar(10)) AS Currency,
    CAST(NULL AS decimal(18,2)) AS LeadTimeDays;
GO

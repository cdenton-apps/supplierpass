/*
SupplierPass Sage 200 source view starter

Purpose:
Create read-only reporting views that SupplierPass can pull from.
These views should be created in a reporting database or carefully in the Sage SQL environment by someone with the right permissions.

Important:
- These are starter templates, not guaranteed final Sage 200 table mappings.
- Do not write back to Sage tables from SupplierPass at this stage.
- Keep the SupplierPass connector read-only.
- Adjust table and column names to match your Sage 200 database and add-ons.

The connector expects these view names:

1. dbo.vw_SupplierPass_ERP_Suppliers
2. dbo.vw_SupplierPass_ERP_PurchaseOrders
3. dbo.vw_SupplierPass_ERP_SupplierPrices
*/

/*
================================================================================
1. Supplier master
================================================================================
Likely Sage 200 source area:
- PLSupplierAccount or equivalent purchase ledger supplier table
- Exact fields vary by Sage 200 version/configuration
*/

CREATE OR ALTER VIEW dbo.vw_SupplierPass_ERP_Suppliers AS
SELECT
    CAST(sa.SupplierAccountNumber AS nvarchar(50)) AS SupplierCode,
    CAST(sa.SupplierAccountName AS nvarchar(255)) AS SupplierName,
    CAST(NULL AS nvarchar(255)) AS SupplierEmail,
    CAST(NULL AS nvarchar(100)) AS Category,
    CAST(CASE WHEN ISNULL(sa.AccountIsOnHold, 0) = 1 THEN 'Inactive' ELSE 'Active' END AS nvarchar(50)) AS IsActive,
    CAST(CASE WHEN ISNULL(sa.AccountIsOnHold, 0) = 1 THEN 'On Hold' ELSE 'Active' END AS nvarchar(100)) AS RawStatus,
    CAST(NULL AS datetime2) AS SourceUpdatedAt
FROM dbo.PLSupplierAccount sa;
GO

/*
================================================================================
2. Purchase order / receipt history
================================================================================
Likely Sage 200 source area:
- POPOrderReturn / POPOrderReturnLine
- POPReceiptReturn / POPReceiptReturnLine or related receipt/despatch tables
- You may need to adapt this depending on whether you want order lines, receipt lines,
  invoice lines, or full GRN history.

This starter is intentionally conservative and may need table/field changes.
*/

CREATE OR ALTER VIEW dbo.vw_SupplierPass_ERP_PurchaseOrders AS
SELECT
    CAST(sa.SupplierAccountNumber AS nvarchar(50)) AS SupplierCode,
    CAST(sa.SupplierAccountName AS nvarchar(255)) AS SupplierName,
    CAST(pol.ItemCode AS nvarchar(100)) AS ItemCode,
    CAST(pol.ItemDescription AS nvarchar(500)) AS ItemDescription,
    CAST(po.DocumentNo AS nvarchar(100)) AS PONumber,
    CAST(po.DocumentDate AS date) AS PODate,
    CAST(pol.RequestedDeliveryDate AS date) AS PromisedDate,
    CAST(NULL AS date) AS ReceivedDate,
    CAST(pol.LineQuantity AS decimal(18,4)) AS Quantity,
    CAST(pol.UnitBuyingPrice AS decimal(18,4)) AS UnitPrice,
    CAST(pol.LineTotalValue AS decimal(18,2)) AS TotalValue
FROM dbo.POPOrderReturn po
JOIN dbo.POPOrderReturnLine pol
    ON po.POPOrderReturnID = pol.POPOrderReturnID
LEFT JOIN dbo.PLSupplierAccount sa
    ON po.SupplierID = sa.PLSupplierAccountID;
GO

/*
================================================================================
3. Supplier prices
================================================================================
Possible source options:
- Last PO price by supplier/item
- POP price book tables if used
- Invoice history if that gives better actual price history

This starter uses purchase order lines as a simple actual-price feed.
*/

CREATE OR ALTER VIEW dbo.vw_SupplierPass_ERP_SupplierPrices AS
SELECT
    CAST(sa.SupplierAccountNumber AS nvarchar(50)) AS SupplierCode,
    CAST(sa.SupplierAccountName AS nvarchar(255)) AS SupplierName,
    CAST(pol.ItemCode AS nvarchar(100)) AS ItemCode,
    CAST(pol.ItemDescription AS nvarchar(500)) AS ItemDescription,
    CAST(NULL AS nvarchar(100)) AS Category,
    CAST(pol.UnitBuyingPrice AS decimal(18,4)) AS UnitPrice,
    CAST('GBP' AS nvarchar(10)) AS Currency,
    CAST(NULL AS decimal(18,2)) AS LeadTimeDays
FROM dbo.POPOrderReturn po
JOIN dbo.POPOrderReturnLine pol
    ON po.POPOrderReturnID = pol.POPOrderReturnID
LEFT JOIN dbo.PLSupplierAccount sa
    ON po.SupplierID = sa.PLSupplierAccountID
WHERE pol.UnitBuyingPrice IS NOT NULL;
GO

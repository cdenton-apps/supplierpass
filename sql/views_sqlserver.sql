CREATE OR ALTER VIEW dbo.vwSupplierDocumentGaps AS
SELECT
    s.SupplierID,
    s.SupplierCode,
    s.SupplierName,
    s.Category,
    s.Owner,
    d.DocumentID,
    d.DocumentType,
    d.ExpiryDate,
    d.ReviewStatus,
    CASE
        WHEN d.DocumentID IS NULL THEN 'Missing'
        WHEN d.ReviewStatus IN ('Uploaded', 'Under Review') THEN 'Needs Review'
        WHEN d.ReviewStatus = 'Rejected / Needs replacement' THEN 'Rejected / Needs Replacement'
        WHEN d.ExpiryDate < CAST(GETDATE() AS date) THEN 'Expired'
        WHEN d.ExpiryDate <= DATEADD(day, 60, CAST(GETDATE() AS date)) THEN 'Expiring Soon'
        ELSE 'OK'
    END AS GapStatus,
    CASE
        WHEN d.ExpiryDate IS NULL THEN NULL
        ELSE DATEDIFF(day, CAST(GETDATE() AS date), d.ExpiryDate)
    END AS DaysLeft
FROM dbo.Suppliers s
LEFT JOIN dbo.SupplierDocuments d
    ON s.SupplierID = d.SupplierID;
GO

CREATE OR ALTER VIEW dbo.vwSupplierOTIF AS
SELECT
    SupplierID,
    SupplierName,
    COUNT(*) AS ReceiptCount,
    SUM(CASE WHEN ReceivedDate IS NOT NULL AND PromisedDate IS NOT NULL AND ReceivedDate <= PromisedDate THEN 1 ELSE 0 END) AS OnTimeCount,
    CAST(
        100.0 * SUM(CASE WHEN ReceivedDate IS NOT NULL AND PromisedDate IS NOT NULL AND ReceivedDate <= PromisedDate THEN 1 ELSE 0 END)
        / NULLIF(SUM(CASE WHEN ReceivedDate IS NOT NULL AND PromisedDate IS NOT NULL THEN 1 ELSE 0 END), 0)
        AS decimal(9,2)
    ) AS OTIFPercent,
    CAST(AVG(CASE WHEN ReceivedDate > PromisedDate THEN DATEDIFF(day, PromisedDate, ReceivedDate) ELSE 0 END) AS decimal(9,2)) AS AvgDaysLate,
    MAX(PODate) AS LastUsedDate,
    SUM(CASE WHEN PODate >= DATEADD(month, -12, CAST(GETDATE() AS date)) THEN TotalValue ELSE 0 END) AS Spend12M
FROM dbo.PurchaseOrderHistory
GROUP BY SupplierID, SupplierName;
GO

CREATE OR ALTER VIEW dbo.vwSupplierPriceComparison AS
WITH ItemMin AS (
    SELECT ItemCode, MIN(NULLIF(UnitPrice, 0)) AS MinUnitPrice
    FROM dbo.SupplierPrices
    GROUP BY ItemCode
)
SELECT
    p.SupplierID,
    p.SupplierName,
    p.Category,
    p.ItemCode,
    p.ItemDescription,
    p.UnitPrice,
    p.Currency,
    p.LeadTimeDays,
    m.MinUnitPrice,
    CASE WHEN p.UnitPrice = m.MinUnitPrice THEN 1 ELSE 0 END AS IsBestPrice,
    CAST(100.0 * m.MinUnitPrice / NULLIF(p.UnitPrice, 0) AS decimal(9,2)) AS PriceScore
FROM dbo.SupplierPrices p
LEFT JOIN ItemMin m
    ON p.ItemCode = m.ItemCode;
GO

CREATE OR ALTER VIEW dbo.vwSupplierScorecard AS
SELECT
    s.SupplierID,
    s.SupplierCode,
    s.SupplierName,
    s.Category,
    s.Owner,
    s.ApprovalStatus,
    s.AppStatus,
    s.RiskLevel,
    COALESCE(o.OTIFPercent, 50) AS OTIFPercent,
    COALESCE(o.Spend12M, 0) AS Spend12M,
    o.LastUsedDate,
    o.AvgDaysLate,
    CASE WHEN EXISTS (
        SELECT 1 FROM dbo.PreferredSuppliers p
        WHERE p.SupplierID = s.SupplierID
          AND p.Category = s.Category
          AND p.IsPreferred = 1
    ) THEN 1 ELSE 0 END AS IsPreferred,
    CASE
        WHEN s.AppStatus <> 'Active' THEN 10
        WHEN s.ApprovalStatus = 'Approved' AND s.RiskLevel = 'Low' THEN 100
        WHEN s.ApprovalStatus = 'Approved' AND s.RiskLevel = 'Medium' THEN 85
        WHEN s.ApprovalStatus = 'Approved' AND s.RiskLevel = 'High' THEN 65
        WHEN s.ApprovalStatus IN ('Pending', 'On Hold') THEN 45
        ELSE 20
    END AS ComplianceScore
FROM dbo.Suppliers s
LEFT JOIN dbo.vwSupplierOTIF o
    ON s.SupplierID = o.SupplierID;
GO

CREATE OR ALTER VIEW dbo.vwERPActionQueuePending AS
SELECT *
FROM dbo.ERPActionQueue
WHERE Status = 'Pending Export';
GO

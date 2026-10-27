<#
.SYNOPSIS
    Build lists-viewer.xlsx: a read-only Excel view of every list CSV in
    <project>/03_Working_Design/PID/02_Tag_Lists/ and <project>/00_Project_Admin/07_Project_Controls/Registers/, refreshed live from the CSV files.

.DESCRIPTION
    Uses Excel (COM) to create one Power Query per CSV. Each query reads the
    CSV as text (no type inference, so tags and sizes stay exactly as written)
    and loads it to an Excel table on its own sheet. Queries refresh when the
    workbook opens and on Data > Refresh All, so the workbook always shows the
    current CSV content. The CSVs remain the only source of truth; the
    workbook is derived output and is not committed.

    The repository root is a Power Query parameter named RepoRoot. Change it
    in Excel via Data > Get Data > Launch Power Query Editor > Manage
    Parameters if the checkout moves, then rebuild or refresh.

.PARAMETER RepoRoot
    Repository root. Default: the folder holding CLAUDE.md above this script.

.PARAMETER Output
    Workbook path. Default: <RepoRoot>\job\<project folder>\_work\lists-viewer.xlsx (gitignored)

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File harness\scripts\build_lists_workbook.ps1
#>
[CmdletBinding()]
param(
    [string]$RepoRoot,
    [string]$Output
)

$ErrorActionPreference = 'Stop'
if (-not $RepoRoot) {
    # $PSScriptRoot is not available in param defaults under PowerShell 5.1.
    $RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
    while ($RepoRoot -and -not (Test-Path (Join-Path $RepoRoot 'CLAUDE.md'))) { $RepoRoot = Split-Path -Parent $RepoRoot }
    if (-not $RepoRoot) { throw 'CLAUDE.md not found above this script; pass -RepoRoot' }
}
$RepoRoot = (Resolve-Path $RepoRoot).Path.TrimEnd('\')
# Active project folder, chosen as harness/lib/repo_paths.py does (Bob, 2026-10-26: one folder per project).
$project = $env:CPME_PROJECT
$activeFile = Join-Path $RepoRoot 'job\active-project.txt'
if (-not $project -and (Test-Path $activeFile)) { $project = (Get-Content $activeFile -TotalCount 1).Trim() }
if (-not $project) {
    $found = @(Get-ChildItem (Join-Path $RepoRoot 'job') -Directory -Filter 'Project-*')
    if ($found.Count -ne 1) { throw "job\ holds $($found.Count) project folders; set CPME_PROJECT or job\active-project.txt" }
    $project = $found[0].Name
}
$projectDir = "job\$project"
if (-not $Output) { $Output = Join-Path $RepoRoot "$projectDir\_work\lists-viewer.xlsx" }

# Folders holding list CSVs, in the order their sheets appear.
$sourceDirs = @("$projectDir\03_Working_Design\PID\02_Tag_Lists", "$projectDir\00_Project_Admin\07_Project_Controls\Registers")

$csvs = @()
foreach ($dir in $sourceDirs) {
    $full = Join-Path $RepoRoot $dir
    if (Test-Path $full) {
        $csvs += Get-ChildItem -Path $full -Filter *.csv -File | Sort-Object Name |
            ForEach-Object { [pscustomobject]@{ Dir = $dir; File = $_.Name; Path = $_.FullName } }
    }
}
if ($csvs.Count -eq 0) { throw "No CSV files found under $RepoRoot in: $($sourceDirs -join ', ')" }

if (Test-Path $Output) { Remove-Item $Output -Force }

# Excel constants
$xlSrcExternal      = 0
$xlYes              = 1
$xlCmdSql           = 2
$xlInsertDeleteCells = 1
$xlOpenXMLWorkbook  = 51

$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false
$excel.ScreenUpdating = $false

try {
    $wb = $excel.Workbooks.Add()
    while ($wb.Worksheets.Count -gt 1) { $wb.Worksheets.Item($wb.Worksheets.Count).Delete() }

    # --- RepoRoot parameter (a Power Query parameter, not a cell, so the
    #     Formula.Firewall does not block combining it with File.Contents).
    $escapedRoot = $RepoRoot.Replace('"', '""')
    $paramM = '"' + $escapedRoot + '" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]'
    [void]$wb.Queries.Add('RepoRoot', $paramM, 'Repository root folder. Edit via Manage Parameters if the checkout moves.')

    # --- README sheet
    $readme = $wb.Worksheets.Item(1)
    $readme.Name = 'README'
    $rows = @(
        @('CPME design harness — list viewer', ''),
        @('', ''),
        @('What this is', 'A read-only Excel view of the list CSVs in <project>/03_Working_Design/PID/02_Tag_Lists/ and <project>/00_Project_Admin/07_Project_Controls/Registers/. Each sheet is a Power Query table that re-reads its CSV.'),
        @('Source of truth', 'The CSV files in the repository. Do not edit data in this workbook; edit the CSV (through the normal change process) and refresh.'),
        @('Refresh', 'Queries refresh automatically when the workbook opens. To refresh while open: Data > Refresh All (Ctrl+Alt+F5).'),
        @('First open', 'If Excel shows "External Data Connections have been disabled", click Enable Content once.'),
        @('Repository root', $RepoRoot),
        @('Change root', 'Data > Get Data > Launch Power Query Editor > Manage Parameters > RepoRoot. Or rebuild with harness\scripts\build_lists_workbook.ps1.'),
        @('Rebuild', 'powershell -ExecutionPolicy Bypass -File harness\scripts\build_lists_workbook.ps1   (adds sheets for any new CSVs)'),
        @('Built', (Get-Date -Format 'yyyy-MM-dd HH:mm')),
        @('', ''),
        @('Sheet', 'Source file')
    )
    foreach ($c in $csvs) { $rows += ,@([System.IO.Path]::GetFileNameWithoutExtension($c.File), "$($c.Dir)/$($c.File)") }

    $r = 1
    foreach ($row in $rows) {
        $readme.Cells.Item($r, 1).Value2 = $row[0]
        $readme.Cells.Item($r, 2).Value2 = $row[1]
        $r++
    }
    $readme.Cells.Item(1, 1).Font.Bold = $true
    $readme.Cells.Item(1, 1).Font.Size = 14
    $readme.Cells.Item(12, 1).Font.Bold = $true
    $readme.Cells.Item(12, 2).Font.Bold = $true
    $readme.Range("A3:A$($rows.Count)").Font.Bold = $true
    $readme.Columns.Item(1).ColumnWidth = 18
    $readme.Columns.Item(2).ColumnWidth = 120
    $readme.Cells.Font.Name = 'Arial'

    # Save first so Power Query has a workbook on disk to attach to.
    $wb.SaveAs($Output, $xlOpenXMLWorkbook)

    # --- One query + sheet + table per CSV
    foreach ($c in $csvs) {
        $base      = [System.IO.Path]::GetFileNameWithoutExtension($c.File)
        $sheetName = $base.Substring(0, [Math]::Min(31, $base.Length))
        $queryName = ($base -replace '[^A-Za-z0-9_]', '_')
        $relPath   = "$($c.Dir)\$($c.File)"

        $m = @"
let
    Source = Csv.Document(File.Contents(RepoRoot & "\$relPath"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true])
in
    Headers
"@
        [void]$wb.Queries.Add($queryName, $m, "Live view of $($c.Dir)/$($c.File). All columns as text.")

        $ws = $wb.Worksheets.Add([Type]::Missing, $wb.Worksheets.Item($wb.Worksheets.Count))
        $ws.Name = $sheetName

        $conn = 'OLEDB;Provider=Microsoft.Mashup.OleDb.1;Data Source=$Workbook$;Location=' + $queryName + ';Extended Properties=""'
        $lo = $ws.ListObjects.Add($xlSrcExternal, $conn, $null, $xlYes, $ws.Range('A1'))
        $qt = $lo.QueryTable
        $qt.CommandType = $xlCmdSql
        $qt.CommandText = "SELECT * FROM [$queryName]"
        $qt.RowNumbers = $false
        $qt.FillAdjacentFormulas = $false
        $qt.PreserveFormatting = $true
        $qt.RefreshOnFileOpen = $true
        $qt.BackgroundQuery = $false
        $qt.RefreshStyle = $xlInsertDeleteCells
        $qt.SavePassword = $false
        $qt.SaveData = $true
        $qt.AdjustColumnWidth = $true
        $qt.RefreshPeriod = 0
        $qt.PreserveColumnInfo = $false
        $lo.DisplayName = "tbl_$queryName"
        $qt.Refresh($false) | Out-Null

        $ws.Cells.Font.Name = 'Arial'
        $ws.Activate()
        $excel.ActiveWindow.SplitRow = 1
        $excel.ActiveWindow.SplitColumn = 0
        $excel.ActiveWindow.FreezePanes = $true

        Write-Host ("  {0,-22} {1,5} rows  {2,3} cols  <- {3}" -f $sheetName, $lo.ListRows.Count, $lo.ListColumns.Count, $relPath)
    }

    $readme.Activate()
    $readme.Range('A1').Select() | Out-Null
    $wb.Save()
    Write-Host "Wrote $Output"
}
finally {
    if ($wb) { $wb.Close($true) }
    $excel.Quit()
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel)
    [GC]::Collect(); [GC]::WaitForPendingFinalizers()
}

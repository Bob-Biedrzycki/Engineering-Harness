<#
.SYNOPSIS
  Export every paperspace layout of a DWG to one multi-page PDF with AutoCAD LT
  Core Console, using each layout's own page setup (TR-06: the PDF is exported
  from the DWG). The DWG is not saved. Fails if the PDF is missing, empty, or
  does not have -ExpectPages pages. Never overwrites an existing PDF.

.EXAMPLE
  .\harness\cad-lib\dwg-to-pdf.ps1 -Dwg C:\...\<PID-DOC-ID>-rev<X>.dwg -Pdf C:\...\<PID-DOC-ID>-rev<X>.pdf -FirstLayout 01-PID -ExpectPages 3
  (<PID-DOC-ID> is rp.PID_DOC_ID from the project's project.yaml)
#>
param(
    [Parameter(Mandatory = $true)][string]$Dwg,
    [Parameter(Mandatory = $true)][string]$Pdf,
    [Parameter(Mandatory = $true)][string]$FirstLayout,
    [Parameter(Mandatory = $true)][int]$ExpectPages,
    [string]$WorkDir = "$env:TEMP\dwg-to-pdf",
    [string]$CadExe = 'C:\Program Files\Autodesk\AutoCAD LT 2027\accoreconsole.exe'
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $CadExe)) { throw "AutoCAD Core Console not found: $CadExe" }
$Dwg = (Resolve-Path -LiteralPath $Dwg).Path
if (Test-Path -LiteralPath $Pdf) { throw "PDF exists, refusing to overwrite: $Pdf" }
New-Item -ItemType Directory -Force $WorkDir | Out-Null
$stem = [IO.Path]::GetFileNameWithoutExtension($Pdf)
$before = (Get-FileHash -LiteralPath $Dwg -Algorithm SHA256).Hash

$cmds = @('FILEDIA', '0', 'BACKGROUNDPLOT', '0', 'TILEMODE', '0', 'CTAB', $FirstLayout,
          '-EXPORT', 'P', 'A', ('"' + $Pdf.Replace('\', '/') + '"'), '_QUIT', '_Y')  # Y = discard changes
$scr = Join-Path $WorkDir "$stem-pdf.scr"
$cmds | Set-Content -LiteralPath $scr -Encoding ascii
$log = Join-Path $WorkDir "$stem-pdf.log"
$p = Start-Process -FilePath $CadExe -ArgumentList "/i `"$Dwg`" /s `"$scr`" /l en-US" -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $log -RedirectStandardError (Join-Path $WorkDir "$stem-pdf.err")
if (-not $p.WaitForExit(600000)) { $p.Kill(); throw "Core Console did not finish the PDF export within 10 minutes" }
$logText = (Get-Content -LiteralPath $log -Raw -ErrorAction SilentlyContinue) -replace "`0", ''
if ($logText -match '\*Invalid\*|Unknown command') { throw "Core Console rejected a command; see $log" }
if (-not (Test-Path -LiteralPath $Pdf)) { throw "PDF not produced; see $log" }
if ((Get-Item -LiteralPath $Pdf).Length -lt 10000) { throw "PDF is suspiciously small; see $log" }
$text = [Text.Encoding]::GetEncoding(28591).GetString([IO.File]::ReadAllBytes($Pdf))
$pages = ([regex]::Matches($text, '/Type\s*/Page(?!s)')).Count
if ($pages -ne $ExpectPages) { throw "PDF has $pages pages, expected $ExpectPages; see $log" }
$after = (Get-FileHash -LiteralPath $Dwg -Algorithm SHA256).Hash
if ($after -ne $before) { throw "the DWG changed during PDF export; see $log" }
Write-Output "PDF: $Pdf ($pages pages)"
Write-Output "sha256: $((Get-FileHash -LiteralPath $Pdf -Algorithm SHA256).Hash.ToLower())"

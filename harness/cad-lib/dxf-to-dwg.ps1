<#
.SYNOPSIS
  Convert a DXF to DWG with AutoCAD LT Core Console, then reopen the DWG and
  export a round-trip DXF for validation. CPME standard settings: paperspace layouts
  zoomed to extents, AUDIT, SAVEAS 2018 format.

.EXAMPLE
  .\harness\cad-lib\dxf-to-dwg.ps1 -Dxf "C:\...\<PID-DOC-ID>-rev<X>-DRAFT.dxf" -Layouts 02-Notes,03-Legend,01-PID
  (<PID-DOC-ID> is rp.PID_DOC_ID from the project's project.yaml)

  Writes <stem>.dwg beside the DXF and <stem>-roundtrip.dxf in -WorkDir.
  Never overwrites an existing DWG unless -Force is given.
#>
param(
    [Parameter(Mandatory = $true)][string]$Dxf,
    [string]$Layouts = '',   # comma-separated paperspace layout names, e.g. "02-Notes,03-Legend,01-PID"
    [string]$WorkDir = "$env:TEMP\dxf-to-dwg",
    [string]$CadExe = 'C:\Program Files\Autodesk\AutoCAD LT 2027\accoreconsole.exe',
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $CadExe)) { throw "AutoCAD Core Console not found: $CadExe" }
$Dxf = (Resolve-Path -LiteralPath $Dxf).Path
$stem = [IO.Path]::GetFileNameWithoutExtension($Dxf)
$dir = [IO.Path]::GetDirectoryName($Dxf)
$dwg = Join-Path $dir "$stem.dwg"
if ((Test-Path -LiteralPath $dwg) -and -not $Force) { throw "DWG exists: $dwg (use -Force to regenerate)" }
New-Item -ItemType Directory -Force $WorkDir | Out-Null
$fwd = { param($p) $p.Replace('\', '/') }

# --- convert ---------------------------------------------------------------
$layoutList = @($Layouts.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ })
$cmds = @('FILEDIA', '0', 'BACKGROUNDPLOT', '0', 'MSLTSCALE', '1', 'WIPEOUTFRAME', '0', 'IMAGEFRAME', '0')
if ($layoutList.Count -gt 0) {
    $cmds += @('TILEMODE', '0')
    foreach ($l in $layoutList) { $cmds += @('CTAB', $l, '_PSPACE', '_ZOOM', '_E') }
}
$cmds += @('_AUDIT', '_Y', '_SAVEAS', '2018', ('"' + (& $fwd $dwg) + '"'))
if (Test-Path -LiteralPath $dwg) { $cmds += '_Y' }
$cmds += '_QUIT'
$scr = Join-Path $WorkDir "$stem-convert.scr"
$cmds | Set-Content -LiteralPath $scr -Encoding ascii
$log = Join-Path $WorkDir "$stem-convert.log"
# Wait on Core Console itself, not on its descendants: Start-Process -Wait also
# waits for lingering Autodesk helper processes and stalls for many minutes.
$p = Start-Process -FilePath $CadExe -ArgumentList "/i `"$Dxf`" /s `"$scr`" /l en-US" -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $log -RedirectStandardError (Join-Path $WorkDir "$stem-convert.err")
if (-not $p.WaitForExit(600000)) { $p.Kill(); throw "Core Console did not finish the conversion within 10 minutes" }
$logText = (Get-Content -LiteralPath $log -Raw -ErrorAction SilentlyContinue) -replace "`0", ''
if ($logText -match '\*Invalid\*|Unknown command') { throw "Core Console rejected a command; see $log" }
if (-not (Test-Path -LiteralPath $dwg)) { throw "DWG not produced; see $log" }

# --- round trip -------------------------------------------------------------
$rt = Join-Path $WorkDir "$stem-roundtrip.dxf"
if (Test-Path -LiteralPath $rt) { Remove-Item -LiteralPath $rt -Force }
$rtcmds = @('FILEDIA', '0', '_AUDIT', '_Y', '_DXFOUT', ('"' + (& $fwd $rt) + '"'), '16', '_QUIT', '_Y')
$rtscr = Join-Path $WorkDir "$stem-roundtrip.scr"
$rtcmds | Set-Content -LiteralPath $rtscr -Encoding ascii
$p = Start-Process -FilePath $CadExe -ArgumentList "/i `"$dwg`" /s `"$rtscr`" /l en-US" -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $WorkDir "$stem-roundtrip.log") -RedirectStandardError (Join-Path $WorkDir "$stem-roundtrip.err")
if (-not $p.WaitForExit(600000)) { $p.Kill(); throw "Core Console did not finish the round trip within 10 minutes" }
if (-not (Test-Path -LiteralPath $rt)) { throw "round-trip DXF not produced; see $WorkDir" }

$h = (Get-FileHash -LiteralPath $dwg -Algorithm SHA256).Hash.ToLower()
Write-Output "DWG: $dwg"
Write-Output "sha256: $h"
Write-Output "round-trip DXF: $rt"
Write-Output "logs: $WorkDir"

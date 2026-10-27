# gh_signin.ps1 - sign the GitHub CLI in once, with the 'workflow' scope, into the one gh config folder that
# every window uses (Bob, 2026-10-06). Bob runs it himself, from a normal PowerShell window at the repo root:
#
#     powershell -ExecutionPolicy Bypass -File harness\scripts\gh_signin.ps1
#
# Why: shells run by the Claude desktop app see a virtualized %APPDATA%, so gh's default config there is a
# different file from the one a normal terminal reads. Both now use $HOME\.config\gh through GH_CONFIG_DIR
# (track.py GH_CONFIG_DIR, .claude/settings.local.json env; a unit test keeps the three the same).
# The 'workflow' scope lets a push change .github/workflows/. Agents never run this or handle tokens.

$dir = Join-Path $HOME '.config\gh'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$env:GH_CONFIG_DIR = $dir
# Persist the folder at user level (Bob, 2026-10-07), so every window opened from now on, including a bare `gh`
# in Bob's own terminal, reads this one sign-in. Without it only track.py and the app's shells agreed.
[Environment]::SetEnvironmentVariable('GH_CONFIG_DIR', $dir, 'User')

$gh = (Get-Command gh -ErrorAction SilentlyContinue).Source
if (-not $gh) {
    $gh = Join-Path $HOME 'AppData\Local\Microsoft\WinGet\Packages\GitHub.cli_Microsoft.Winget.Source_8wekyb3d8bbwe\bin\gh.exe'
}
if (-not (Test-Path $gh)) {
    Write-Host 'gh is not installed. Install it with:  winget install --id GitHub.cli --scope user'
    exit 1
}

Write-Host "gh config folder: $dir"

function Use-GhForGit {
    # One identity for git too (Bob, 2026-10-07: "refine the identities"): git's credential helper for github.com
    # becomes this gh sign-in, so a `git push` typed by hand goes out as the same account track.py uses, not as
    # whatever Git Credential Manager last stored. Idempotent; writes only the github.com entry of the global config.
    # The agent's shells may not change git's global config (guarded), so this runs here, in Bob's own window.
    & $gh auth setup-git --hostname github.com
    if ($LASTEXITCODE -eq 0) { Write-Host "git now uses this gh sign-in for github.com (gh auth setup-git)." }
    else { Write-Host "WARNING: gh auth setup-git failed (exit $LASTEXITCODE); git keeps its previous credential helper." }
}

# Already signed in with the scope? Then there is nothing to do: the sign-in is a one-time event, the token stays
# in the Windows keyring, and the browser round-trip (device code, e-mail code) is never repeated for its own sake.
$json = & $gh auth status --hostname github.com --json hosts 2>$null | Out-String
if ($LASTEXITCODE -eq 0 -and $json.Trim()) {
    $accounts = @((ConvertFrom-Json $json).hosts.'github.com')
    $active = $accounts | Where-Object { $_.active } | Select-Object -First 1
    if ($active -and $active.state -eq 'success' -and (($active.scopes -split ',\s*') -contains 'workflow')) {
        Use-GhForGit
        Write-Host "OK: $($active.login) is already signed in with the 'workflow' scope. Nothing else to do."
        exit 0
    }
}

& $gh auth login --hostname github.com --git-protocol https --web --scopes workflow
if ($LASTEXITCODE -ne 0) {
    Write-Host "gh auth login did not finish (exit $LASTEXITCODE). Run this script again."
    exit 1
}

& $gh auth status --hostname github.com
$json = & $gh auth status --hostname github.com --json hosts | Out-String
$accounts = @((ConvertFrom-Json $json).hosts.'github.com')
$active = $accounts | Where-Object { $_.active } | Select-Object -First 1
if ($active -and (($active.scopes -split ',\s*') -contains 'workflow')) {
    Use-GhForGit
    Write-Host "OK: $($active.login) is signed in with the 'workflow' scope. Tell Claude it is done."
    exit 0
}
Write-Host "NOT OK: the 'workflow' scope is missing. Run this script again and approve every scope in the browser."
exit 1

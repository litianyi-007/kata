<#
.SYNOPSIS
    One-shot switch: turn the current local repo into Workflow B layout.

.DESCRIPTION
    Implements the workflow described in CHANGELOG v2.0.0 follow-up:
    - Old AK-llm-wiki (private) becomes the historical archive (push disabled here)
    - New surebeli/kata (public) becomes the daily push target via origin
    - Local main becomes the public orphan; full history moves to archive-main

    Pre-conditions:
      1. You're on branch 'main'
      2. Working tree is clean (git status --porcelain is empty)
      3. The current 'origin' remote points at the PRIVATE archive (e.g.
         https://github.com/surebeli/AK-llm-wiki.git, now set to private)
      4. The NEW public repo (default: surebeli/kata) has been CREATED on
         GitHub but is empty (no initial commit, no README)

    What this script does (in order):
      1. Pre-flight checks (branch, clean tree, remote exists)
      2. (Optional) Push current main to private remote — full history archive
      3. Create orphan branch 'public-main' from current main HEAD
      4. Verify the public repo URL is reachable
      5. Push orphan to public repo as main
      6. Rename local branches: main → archive-main, public-main → main
      7. Rename remotes: origin → private; add new origin = public
      8. Set upstream tracking for new main
      9. Disable push on the private remote (belt-and-suspenders)
      10. Report final state

.PARAMETER PublicUrl
    HTTPS URL of the NEW public repo. Default: https://github.com/surebeli/kata.git

.PARAMETER SkipPrivateBackup
    Skip step 2 (push current full-history main to private). Use if you've
    already pushed, or if you don't want an off-machine backup of the
    pre-orphan state.

.PARAMETER DryRun
    Print every git command that would run without executing.

.EXAMPLE
    .\scripts\_release-switch-to-public.ps1
    Run interactively with defaults.

.EXAMPLE
    .\scripts\_release-switch-to-public.ps1 -DryRun
    Preview without changes.

.EXAMPLE
    .\scripts\_release-switch-to-public.ps1 -SkipPrivateBackup
    Skip the private archive push (you've already done it).
#>

[CmdletBinding()]
param(
    [string]$PublicUrl = "https://github.com/surebeli/kata.git",
    [switch]$SkipPrivateBackup,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Run-Git {
    # Use $args (automatic, no named-param binding) so single-dash flags
    # like -D pass through verbatim. PowerShell parameter binding
    # otherwise swallows -X-style args when the function declares
    # ValueFromRemainingArguments.
    if ($DryRun) {
        Write-Host "  [dry-run] git $($args -join ' ')" -ForegroundColor Cyan
        return
    }
    & git @args
    if ($LASTEXITCODE -ne 0) {
        throw "git $($args -join ' ') failed (exit $LASTEXITCODE)"
    }
}

function Ok($msg)   { Write-Host "  [ok] $msg" -ForegroundColor Green }
function Step($msg) { Write-Host ""; Write-Host "[$script:stepIdx] $msg" -ForegroundColor Yellow; $script:stepIdx++ }
$script:stepIdx = 1

# --------------------------------------------------------------------
Step "Pre-flight checks"

$current = (& git rev-parse --abbrev-ref HEAD).Trim()
if ($current -ne 'main') {
    throw "Expected to be on 'main' branch; currently on '$current'. Switch with 'git checkout main'."
}
Ok "on branch 'main'"

$status = (& git status --porcelain)
if ($status) {
    throw "Working tree is not clean. Commit or stash first.`n$status"
}
Ok "working tree clean"

$remotes = (& git remote) -split "`r?`n" | Where-Object { $_ }
if ($remotes -notcontains 'origin') {
    throw "No 'origin' remote configured."
}
$originUrl = (& git remote get-url origin).Trim()
Ok "origin currently → $originUrl (will become 'private' archive)"

$branches = (& git branch --list --format='%(refname:short)') -split "`r?`n" | Where-Object { $_ }
if ($branches -contains 'archive-main') {
    throw "Local branch 'archive-main' already exists. Delete or rename it first."
}
if ($branches -contains 'public-main') {
    Write-Warning "Local 'public-main' branch exists (likely from an earlier session). It will be REPLACED."
    if (-not $DryRun) {
        Run-Git branch -D public-main
    }
    Ok "removed stale 'public-main'"
}

# --------------------------------------------------------------------
if (-not $SkipPrivateBackup) {
    Step "Pushing current main to PRIVATE remote (full-history archive)"
    Run-Git push origin main
    Ok "main pushed to private archive at $originUrl"
} else {
    Step "Skipping private backup push (per -SkipPrivateBackup)"
}

# --------------------------------------------------------------------
Step "Creating orphan branch 'public-main' from current main HEAD"
Run-Git checkout --orphan public-main
Run-Git add -A
Run-Git commit -m "Initial public release - Kata v2.0.0"
Ok "orphan commit created on 'public-main'"

# --------------------------------------------------------------------
Step "Verifying new public repo URL is reachable: $PublicUrl"
if ($DryRun) {
    Write-Host "  [dry-run] git ls-remote $PublicUrl" -ForegroundColor Cyan
} else {
    $probe = & git ls-remote $PublicUrl 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Cannot reach $PublicUrl. Create the empty public repo on GitHub first, then re-run.`n$probe"
    }
}
Ok "public repo reachable"

# --------------------------------------------------------------------
Step "Pushing orphan to public repo's main"
Run-Git push $PublicUrl public-main:main
Ok "orphan pushed to public main"

# --------------------------------------------------------------------
Step "Renaming local branches: main → archive-main, public-main → main"
Run-Git checkout main
Run-Git branch -m main archive-main
Run-Git branch -m public-main main
Ok "local 'main' is now the orphan; 'archive-main' is the old full-history line"

# --------------------------------------------------------------------
Step "Renaming remotes: origin → private; new origin = $PublicUrl"
Run-Git remote rename origin private
Run-Git remote add origin $PublicUrl
Ok "origin is now PUBLIC; old archive is 'private'"

# --------------------------------------------------------------------
Step "Setting upstream tracking for new main"
Run-Git fetch origin
Run-Git branch --set-upstream-to=origin/main main
Ok "main tracks origin/main"

# --------------------------------------------------------------------
Step "Disabling push on 'private' remote (belt-and-suspenders)"
Run-Git remote set-url --push private DISABLE
Ok "private push URL set to 'DISABLE' — accidental 'git push private main' will fail"

# --------------------------------------------------------------------
Write-Host ""
Write-Host "==== DONE ====" -ForegroundColor Green
Write-Host ""
Write-Host "Final state:" -ForegroundColor Yellow
& git branch -vv
Write-Host ""
& git remote -v
Write-Host ""
Write-Host "Going forward:" -ForegroundColor Green
Write-Host "  git push origin main       # publishes commits to surebeli/kata (public)" -ForegroundColor White
Write-Host "  git checkout archive-main  # inspect pre-rebrand history (local only)" -ForegroundColor White
Write-Host "  git switch -c wip/foo      # branch off for sensitive WIP" -ForegroundColor White
Write-Host ""
Write-Host "Disabled-push reminder:" -ForegroundColor Yellow
Write-Host "  'git push private ...' will fail until you restore the URL with:" -ForegroundColor White
Write-Host "    git remote set-url --push private https://github.com/surebeli/AK-llm-wiki.git" -ForegroundColor DarkGray

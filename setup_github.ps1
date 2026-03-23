# =============================================================================
# RNS Messenger — GitHub Repository Setup Script (PowerShell)
# Run this once from the directory CONTAINING rns-messenger\
#
# Usage:
#   .\setup_github.ps1 -GitHubUser YOUR_GITHUB_USERNAME
#
# Prerequisites:
#   1. Git:    https://git-scm.com/download/win
#   2. gh CLI: winget install GitHub.cli
#              then: gh auth login
# =============================================================================

param(
    [Parameter(Mandatory=$true)]
    [string]$GitHubUser
)

$RepoName = "rns-messenger"
$RepoDir  = Join-Path (Get-Location) $RepoName

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  RNS Messenger — GitHub Setup (PowerShell)"  -ForegroundColor Cyan
Write-Host "  User : $GitHubUser"                         -ForegroundColor Cyan
Write-Host "  Repo : $RepoName"                           -ForegroundColor Cyan
Write-Host "  Dir  : $RepoDir"                            -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Verify directory exists ──────────────────────────────────────────
if (-not (Test-Path $RepoDir)) {
    Write-Host "ERROR: Directory '$RepoDir' not found." -ForegroundColor Red
    Write-Host "Make sure you run this script from the parent folder of rns-messenger\" -ForegroundColor Red
    exit 1
}

Set-Location $RepoDir

# ── Step 2: Check prerequisites ───────────────────────────────────────────────
Write-Host "Checking prerequisites..." -ForegroundColor Yellow

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: git not found. Install from https://git-scm.com/download/win" -ForegroundColor Red
    exit 1
}
Write-Host "  git        OK" -ForegroundColor Green

$ghAvailable = $null -ne (Get-Command gh -ErrorAction SilentlyContinue)
if ($ghAvailable) {
    Write-Host "  gh CLI     OK" -ForegroundColor Green
} else {
    Write-Host "  gh CLI     NOT FOUND (manual push instructions will be shown)" -ForegroundColor Yellow
}

# ── Step 3: Initialise git ────────────────────────────────────────────────────
Write-Host ""
Write-Host "Initialising git repository..." -ForegroundColor Yellow

git init
git checkout -b main

# ── Step 4: Stage all files ───────────────────────────────────────────────────
Write-Host ""
Write-Host "Staging files..." -ForegroundColor Yellow
git add .
git status

# ── Step 5: Initial commit ────────────────────────────────────────────────────
Write-Host ""
Write-Host "Creating initial commit..." -ForegroundColor Yellow

$commitMsg = @"
Initial commit: RNS Messenger v0.1.0

- Kivy Android app with RNS/LXMF backend
- Text + image messaging over paired RNode BT Classic
- GitHub Actions workflow for APK build via Buildozer
- Screens: Contacts, Chat, Settings
- LoRa region presets, delivery ticks, RSSI/SNR display
"@

git commit -m $commitMsg

# ── Step 6: Create GitHub repo and push ───────────────────────────────────────
Write-Host ""

if ($ghAvailable) {
    Write-Host "Creating GitHub repository '$RepoName'..." -ForegroundColor Yellow

    gh repo create $RepoName `
        --public `
        --description "LXMF messenger for Android over RNode Bluetooth Classic" `
        --source=. `
        --remote=origin `
        --push

    Write-Host ""
    Write-Host "Repository created and pushed!" -ForegroundColor Green

    # ── Step 7: Create data branch for APK storage ────────────────────────
    Write-Host ""
    Write-Host "Creating 'data' branch for APK artifact storage..." -ForegroundColor Yellow
    git checkout -b data
    git commit --allow-empty -m "Initialize data branch for APK artifacts"
    git push origin data
    git checkout main

} else {
    Write-Host "gh CLI not found. Follow these manual steps:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  1. Go to https://github.com/new" -ForegroundColor White
    Write-Host "  2. Create a NEW repository named: $RepoName" -ForegroundColor White
    Write-Host "  3. Leave it empty (no README, no .gitignore)" -ForegroundColor White
    Write-Host "  4. Run these commands in this folder:" -ForegroundColor White
    Write-Host ""
    Write-Host "     git remote add origin https://github.com/$GitHubUser/$RepoName.git" -ForegroundColor Cyan
    Write-Host "     git push -u origin main" -ForegroundColor Cyan
    Write-Host ""
}

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "==============================================" -ForegroundColor Green
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  Repository : https://github.com/$GitHubUser/$RepoName" -ForegroundColor White
Write-Host "  Actions    : https://github.com/$GitHubUser/$RepoName/actions" -ForegroundColor White
Write-Host ""
Write-Host "  The GitHub Actions workflow will build your APK" -ForegroundColor White
Write-Host "  automatically on every push to main." -ForegroundColor White
Write-Host ""
Write-Host "  To download the APK:" -ForegroundColor White
Write-Host "  Actions -> latest run -> Artifacts -> rns-messenger-debug-apk" -ForegroundColor White
Write-Host ""
Write-Host "  To create a release with download link:" -ForegroundColor Cyan
Write-Host "  git tag v0.1.0" -ForegroundColor Cyan
Write-Host "  git push origin v0.1.0" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Green

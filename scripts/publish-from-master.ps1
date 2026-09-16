param(
  [string]$Version = "2.1.0"
)

$ErrorActionPreference = "Stop"
$repo = "flaigueglia85/FL-Entertainment"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$buildPayloadScript = Join-Path $PSScriptRoot "build-payload.ps1"
$buildBootstrapScript = Join-Path $PSScriptRoot "build-bootstrap.ps1"
$publishScript = Join-Path $PSScriptRoot "publish-release.ps1"

Write-Host "============================================================"
Write-Host " FL-Entertainment - Publish from Windows master"
Write-Host "============================================================"
Write-Host "Versione: $Version"
Write-Host "Kodi master: $env:APPDATA\Kodi"
Write-Host ""

if (!(Get-Command git -ErrorAction SilentlyContinue)) { throw "git non trovato nel PATH." }

if (!(Get-Command gh -ErrorAction SilentlyContinue)) {
  Write-Host "GitHub CLI non trovato. Provo installazione con winget..." -ForegroundColor Yellow
  if (!(Get-Command winget -ErrorAction SilentlyContinue)) { throw "gh non installato e winget non disponibile." }
  winget install --id GitHub.cli -e --source winget --accept-package-agreements --accept-source-agreements
  $env:Path += ";$env:ProgramFiles\GitHub CLI"
}

$authOk = $false
try {
  gh auth status --hostname github.com *> $null
  if ($LASTEXITCODE -eq 0) { $authOk = $true }
} catch {}
if (!$authOk) {
  gh auth login --hostname github.com --git-protocol https --web
  if ($LASTEXITCODE -ne 0) { throw "Autenticazione GitHub CLI fallita." }
}

Write-Host ""
Write-Host "[1/4] Build payload custom-only dal Kodi Windows master..."
& powershell -NoProfile -ExecutionPolicy Bypass -File $buildPayloadScript -Version $Version
if ($LASTEXITCODE -ne 0) { throw "Build payload fallita." }

Write-Host ""
Write-Host "[2/4] Build bootstrap FL-Entertainment..."
& powershell -NoProfile -ExecutionPolicy Bypass -File $buildBootstrapScript -Version $Version
if ($LASTEXITCODE -ne 0) { throw "Build bootstrap fallita." }

Write-Host ""
Write-Host "[3/4] Pubblicazione GitHub Release + payload + bootstrap..."
& powershell -NoProfile -ExecutionPolicy Bypass -File $publishScript -Version $Version
if ($LASTEXITCODE -ne 0) { throw "Pubblicazione release fallita." }

Write-Host ""
Write-Host "[4/4] Verifica release e manifest..."
$tag = "v$Version"
gh release view $tag --repo $repo --json tagName,assets,url | Out-Host
if ($LASTEXITCODE -ne 0) { throw "Verifica release fallita." }

Write-Host ""
Write-Host "FL-Entertainment $tag pubblicato."
Write-Host "La release contiene sia payload sia bootstrap installabile."

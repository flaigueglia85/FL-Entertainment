param(
  [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"
$repo = "flaigueglia85/FL-Entertainment"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$buildScript = Join-Path $PSScriptRoot "build-payload.ps1"
$publishScript = Join-Path $PSScriptRoot "publish-release.ps1"

Write-Host "============================================================"
Write-Host " FL-Entertainment - Publish from Windows master"
Write-Host "============================================================"
Write-Host "Versione: $Version"
Write-Host "Kodi master: $env:APPDATA\Kodi"
Write-Host ""

if (!(Get-Command git -ErrorAction SilentlyContinue)) {
  throw "git non trovato nel PATH."
}

if (!(Get-Command gh -ErrorAction SilentlyContinue)) {
  Write-Host "GitHub CLI non trovato. Provo installazione con winget..." -ForegroundColor Yellow
  if (!(Get-Command winget -ErrorAction SilentlyContinue)) {
    throw "gh non installato e winget non disponibile. Installa GitHub CLI manualmente."
  }
  winget install --id GitHub.cli -e --source winget --accept-package-agreements --accept-source-agreements
  $env:Path += ";$env:ProgramFiles\GitHub CLI"
}

$authOk = $false
try {
  gh auth status --hostname github.com *> $null
  if ($LASTEXITCODE -eq 0) { $authOk = $true }
} catch {}
if (!$authOk) {
  Write-Host ""
  Write-Host "Devi autenticare GitHub CLI una sola volta." -ForegroundColor Yellow
  Write-Host "Si apre ora il login gh auth login..."
  gh auth login --hostname github.com --git-protocol https --web
  if ($LASTEXITCODE -ne 0) { throw "Autenticazione GitHub CLI fallita." }
}

Write-Host ""
Write-Host "[1/3] Build payload dal Kodi Windows master..."
& powershell -NoProfile -ExecutionPolicy Bypass -File $buildScript -Version $Version
if ($LASTEXITCODE -ne 0) { throw "Build payload fallita." }

Write-Host ""
Write-Host "[2/3] Pubblicazione GitHub Release + asset..."
& powershell -NoProfile -ExecutionPolicy Bypass -File $publishScript -Version $Version
if ($LASTEXITCODE -ne 0) { throw "Pubblicazione release fallita." }

Write-Host ""
Write-Host "[3/3] Verifica release e manifest..."
$tag = "v$Version"
gh release view $tag --repo $repo --json tagName,assets,url | Out-Host
if ($LASTEXITCODE -ne 0) { throw "Verifica release fallita." }

Write-Host ""
Write-Host "Payload pubblicato. Il bootstrap puo' ora installare/aggiornare FL-Entertainment."

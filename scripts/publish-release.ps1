param(
  [Parameter(Mandatory=$true)][string]$Version
)

$ErrorActionPreference = "Stop"
$repo = "flaigueglia85/FL-Entertainment"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$payload = Join-Path $root "dist\FL-Entertainment-payload-$Version.zip"

if (!(Get-Command gh -ErrorAction SilentlyContinue)) {
  throw "GitHub CLI (gh) non trovato. Installa gh e fai 'gh auth login'."
}
if (!(Test-Path $payload)) {
  throw "Payload non trovato: $payload. Esegui prima build-payload.ps1 -Version $Version"
}

$tag = "v$Version"
$assetName = Split-Path $payload -Leaf

# Crea la release o aggiorna quella esistente.
$exists = $false
try { gh release view $tag --repo $repo *> $null; $exists = $true } catch {}
if (-not $exists) {
  gh release create $tag $payload --repo $repo --title "FL-Entertainment $tag" --notes "Payload FL-Entertainment $tag"
} else {
  gh release upload $tag $payload --repo $repo --clobber
}

$manifest = @{
  version = $Version
  payload_url = "https://github.com/$repo/releases/download/$tag/$assetName"
  bootstrap_min_version = "1.0.2"
} | ConvertTo-Json

$manifestPath = Join-Path $root "manifest.json"
Set-Content -Path $manifestPath -Value $manifest -Encoding UTF8

git -C $root add manifest.json
git -C $root commit -m "Publish FL-Entertainment $tag"
git -C $root push origin main

Write-Host "Pubblicato $tag"
Write-Host "Manifest aggiornato: $manifestPath"

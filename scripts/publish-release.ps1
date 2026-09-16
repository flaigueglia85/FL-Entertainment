param(
  [Parameter(Mandatory=$true)][string]$Version
)

$ErrorActionPreference = "Stop"
$repo = "flaigueglia85/FL-Entertainment"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$payload = Join-Path $root "dist\FL-Entertainment-payload-$Version.zip"

if (!(Get-Command gh -ErrorAction SilentlyContinue)) {
  throw "GitHub CLI (gh) non trovato."
}
if (!(Get-Command git -ErrorAction SilentlyContinue)) {
  throw "git non trovato."
}
if (!(Test-Path $payload)) {
  throw "Payload non trovato: $payload. Esegui prima build-payload.ps1 -Version $Version"
}

$tag = "v$Version"
$assetName = Split-Path $payload -Leaf

# Allinea la working copy PRIMA di modificare manifest.json.
# In questo modo git pull --rebase non viene bloccato da modifiche locali create dallo script stesso.
& git -C $root pull --rebase origin main
if ($LASTEXITCODE -ne 0) { throw "git pull --rebase fallito." }

# PowerShell 5.1 converte stderr dei programmi nativi in NativeCommandError quando
# ErrorActionPreference=Stop. Usiamo cmd.exe solo per il probe silenzioso della release.
$probe = "gh release view $tag --repo $repo >nul 2>nul"
& cmd.exe /d /c $probe
$exists = ($LASTEXITCODE -eq 0)

if (-not $exists) {
  Write-Host "Release $tag non presente: la creo..."
  & gh release create $tag $payload --repo $repo --title "FL-Entertainment $tag" --notes "Payload FL-Entertainment $tag"
  if ($LASTEXITCODE -ne 0) { throw "Creazione GitHub Release $tag fallita." }
} else {
  Write-Host "Release $tag esistente: aggiorno asset..."
  & gh release upload $tag $payload --repo $repo --clobber
  if ($LASTEXITCODE -ne 0) { throw "Upload asset release $tag fallito." }
}

$manifestObject = [ordered]@{
  version = $Version
  payload_url = "https://github.com/$repo/releases/download/$tag/$assetName"
  bootstrap_min_version = "1.0.2"
}
$manifest = $manifestObject | ConvertTo-Json
$manifestPath = Join-Path $root "manifest.json"
[IO.File]::WriteAllText($manifestPath, $manifest + [Environment]::NewLine, (New-Object Text.UTF8Encoding($false)))

& git -C $root add manifest.json
& git -C $root diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
  & git -C $root commit -m "Publish FL-Entertainment $tag"
  if ($LASTEXITCODE -ne 0) { throw "Commit manifest fallito." }
  & git -C $root push origin main
  if ($LASTEXITCODE -ne 0) { throw "Push manifest fallito." }
} else {
  Write-Host "Manifest gia' aggiornato: nessun commit necessario."
}

Write-Host "Pubblicato $tag"
Write-Host "Asset: https://github.com/$repo/releases/download/$tag/$assetName"
Write-Host "Manifest aggiornato: $manifestPath"

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

# Create or update the GitHub Release. Native command exit codes are checked explicitly.
gh release view $tag --repo $repo *> $null
$exists = ($LASTEXITCODE -eq 0)

if (-not $exists) {
  gh release create $tag $payload --repo $repo --title "FL-Entertainment $tag" --notes "Payload FL-Entertainment $tag"
  if ($LASTEXITCODE -ne 0) { throw "Creazione GitHub Release $tag fallita." }
} else {
  gh release upload $tag $payload --repo $repo --clobber
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

# Keep local main current before committing the manifest.
git -C $root pull --rebase origin main
if ($LASTEXITCODE -ne 0) { throw "git pull --rebase fallito." }

git -C $root add manifest.json
git -C $root diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
  git -C $root commit -m "Publish FL-Entertainment $tag"
  if ($LASTEXITCODE -ne 0) { throw "Commit manifest fallito." }
  git -C $root push origin main
  if ($LASTEXITCODE -ne 0) { throw "Push manifest fallito." }
} else {
  Write-Host "Manifest gia' aggiornato: nessun commit necessario."
}

Write-Host "Pubblicato $tag"
Write-Host "Asset: https://github.com/$repo/releases/download/$tag/$assetName"
Write-Host "Manifest aggiornato: $manifestPath"

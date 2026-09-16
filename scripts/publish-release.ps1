param(
  [Parameter(Mandatory=$true)][string]$Version
)

$ErrorActionPreference = "Stop"
$repo = "flaigueglia85/FL-Entertainment"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$payload = Join-Path $root "dist\FL-Entertainment-payload-$Version.zip"
$bootstrap = Join-Path $root "dist\plugin.program.flentertainment.bootstrap-$Version.zip"

if (!(Get-Command gh -ErrorAction SilentlyContinue)) { throw "GitHub CLI (gh) non trovato." }
if (!(Get-Command git -ErrorAction SilentlyContinue)) { throw "git non trovato." }
if (!(Test-Path $payload)) { throw "Payload non trovato: $payload" }
if (!(Test-Path $bootstrap)) { throw "Bootstrap non trovato: $bootstrap" }

$tag = "v$Version"
$payloadName = Split-Path $payload -Leaf
$bootstrapName = Split-Path $bootstrap -Leaf

& git -C $root pull --rebase origin main
if ($LASTEXITCODE -ne 0) { throw "git pull --rebase fallito." }

$probe = "gh release view $tag --repo $repo >nul 2>nul"
& cmd.exe /d /c $probe
$exists = ($LASTEXITCODE -eq 0)

if (-not $exists) {
  Write-Host "Release $tag non presente: la creo..."
  & gh release create $tag $payload $bootstrap --repo $repo --title "FL-Entertainment $tag" --notes "FL-Entertainment $tag - payload configurazione + bootstrap installabile"
  if ($LASTEXITCODE -ne 0) { throw "Creazione GitHub Release $tag fallita." }
} else {
  Write-Host "Release $tag esistente: aggiorno payload + bootstrap..."
  & gh release upload $tag $payload $bootstrap --repo $repo --clobber
  if ($LASTEXITCODE -ne 0) { throw "Upload asset release $tag fallito." }
}

$manifestObject = [ordered]@{
  version = $Version
  payload_url = "https://github.com/$repo/releases/download/$tag/$payloadName"
  bootstrap_url = "https://github.com/$repo/releases/download/$tag/$bootstrapName"
  bootstrap_min_version = $Version
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
Write-Host "Payload: https://github.com/$repo/releases/download/$tag/$payloadName"
Write-Host "Bootstrap: https://github.com/$repo/releases/download/$tag/$bootstrapName"
Write-Host "Manifest aggiornato: $manifestPath"

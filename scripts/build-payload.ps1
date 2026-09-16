param(
  [string]$Version = "1.0.0",
  [string]$KodiRoot = "$env:APPDATA\Kodi",
  [string]$OutDir = "$PSScriptRoot\..\dist"
)

$ErrorActionPreference = "Stop"

$addonsRoot = Join-Path $KodiRoot "addons"
$addonDataRoot = Join-Path $KodiRoot "userdata\addon_data"
$stage = Join-Path $env:TEMP "FL-Entertainment-payload-$Version"
$outZip = Join-Path $OutDir "FL-Entertainment-payload-$Version.zip"

if (!(Test-Path $addonsRoot)) { throw "Kodi master non trovato: $KodiRoot" }
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path (Join-Path $stage "addons") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $stage "userdata\addon_data") | Out-Null
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$rootAddons = @(
  "skin.arctic.fuse.3",
  "script.skinvariables",
  "plugin.video.themoviedb.helper",
  "plugin.video.s4me",
  "plugin.video.s4me.bridge",
  "repository.jurialmunkey"
)

$skipPrefixes = @("inputstream.","pvr.","vfs.","game.","audiodecoder.","visualization.")
$resolved = New-Object System.Collections.Generic.HashSet[string]
$q = New-Object System.Collections.Generic.Queue[string]
$rootAddons | ForEach-Object { $q.Enqueue($_) }

function Is-Skipped([string]$id) {
  foreach ($p in $skipPrefixes) { if ($id.StartsWith($p,[System.StringComparison]::OrdinalIgnoreCase)) { return $true } }
  return $false
}

while ($q.Count -gt 0) {
  $id = $q.Dequeue()
  if ($id.StartsWith("xbmc.")) { continue }
  if (Is-Skipped $id) { continue }
  if ($resolved.Contains($id)) { continue }
  $dir = Join-Path $addonsRoot $id
  $xmlPath = Join-Path $dir "addon.xml"
  if (!(Test-Path $xmlPath)) { continue }
  [void]$resolved.Add($id)
  [xml]$xml = Get-Content $xmlPath -Raw
  foreach ($imp in @($xml.addon.requires.import)) {
    $dep = [string]$imp.addon
    if ($dep -and !$dep.StartsWith("xbmc.")) { $q.Enqueue($dep) }
  }
}

foreach ($id in $resolved) {
  Copy-Item (Join-Path $addonsRoot $id) (Join-Path $stage "addons\$id") -Recurse -Force
}

# Master UX/configuration
foreach ($id in @("skin.arctic.fuse.3","script.skinvariables","plugin.video.s4me")) {
  $src = Join-Path $addonDataRoot $id
  if (Test-Path $src) { Copy-Item $src (Join-Path $stage "userdata\addon_data\$id") -Recurse -Force }
}

# TMDb Helper: settings + custom players only; avoid caches/databases.
$tmdbSrc = Join-Path $addonDataRoot "plugin.video.themoviedb.helper"
$tmdbDst = Join-Path $stage "userdata\addon_data\plugin.video.themoviedb.helper"
if (Test-Path $tmdbSrc) {
  New-Item -ItemType Directory -Force -Path $tmdbDst | Out-Null
  foreach ($name in @("settings.xml","players")) {
    $src = Join-Path $tmdbSrc $name
    if (Test-Path $src) { Copy-Item $src $tmdbDst -Recurse -Force }
  }
}

# Do not ship local caches, Kodi DBs, thumbnails or platform-specific binary addons.
if (Test-Path $outZip) { Remove-Item $outZip -Force }
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $outZip -CompressionLevel Optimal

Write-Host "Creato: $outZip"
Write-Host "Addon inclusi: $($resolved.Count)"

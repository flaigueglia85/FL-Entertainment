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
  foreach ($p in $skipPrefixes) {
    if ($id.StartsWith($p,[System.StringComparison]::OrdinalIgnoreCase)) { return $true }
  }
  return $false
}

function Copy-SanitizedSettings([string]$source, [string]$destination) {
  if (!(Test-Path $source)) { return }
  [xml]$xml = Get-Content -LiteralPath $source -Raw

  # Public payload: never publish account/session/API credentials from the Windows master.
  # Keep normal behaviour/preferences while blanking values whose ids look credential-like.
  $sensitive = '(?i)(token|secret|password|passwd|api[_-]?key|apikey|refresh|oauth|auth[_-]?code|session|cookie|email|username|user[_-]?name)'
  foreach ($node in @($xml.SelectNodes('//setting'))) {
    $id = [string]$node.id
    if ($id -match $sensitive) {
      if ($node.HasAttribute('value')) { $node.SetAttribute('value','') }
      $node.InnerText = ''
    }
  }

  $dir = Split-Path -Parent $destination
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  $xml.Save($destination)
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

# UI master configuration: safe to distribute as-is.
foreach ($id in @("skin.arctic.fuse.3","script.skinvariables")) {
  $src = Join-Path $addonDataRoot $id
  if (Test-Path $src) {
    Copy-Item $src (Join-Path $stage "userdata\addon_data\$id") -Recurse -Force
  }
}

# Stream4Me: distribute preferences only. Do NOT publish cookies, databases, history or sessions.
$s4meSrc = Join-Path $addonDataRoot "plugin.video.s4me"
$s4meDst = Join-Path $stage "userdata\addon_data\plugin.video.s4me"
if (Test-Path $s4meSrc) {
  New-Item -ItemType Directory -Force -Path $s4meDst | Out-Null
  Copy-SanitizedSettings (Join-Path $s4meSrc "settings.xml") (Join-Path $s4meDst "settings.xml")
}

# TMDb Helper: custom players + sanitized behavioural settings only; no caches/databases/tokens.
$tmdbSrc = Join-Path $addonDataRoot "plugin.video.themoviedb.helper"
$tmdbDst = Join-Path $stage "userdata\addon_data\plugin.video.themoviedb.helper"
if (Test-Path $tmdbSrc) {
  New-Item -ItemType Directory -Force -Path $tmdbDst | Out-Null
  Copy-SanitizedSettings (Join-Path $tmdbSrc "settings.xml") (Join-Path $tmdbDst "settings.xml")
  $players = Join-Path $tmdbSrc "players"
  if (Test-Path $players) { Copy-Item $players $tmdbDst -Recurse -Force }
}

# Remove development/runtime junk that should never enter the public payload.
Get-ChildItem $stage -Recurse -Force -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -in @('.git','.gitignore','__pycache__') } |
  Sort-Object FullName -Descending |
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

if (Test-Path $outZip) { Remove-Item $outZip -Force }
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $outZip -CompressionLevel Optimal

Write-Host "Creato: $outZip"
Write-Host "Addon inclusi: $($resolved.Count)"
Write-Host "Credenziali/sessioni locali: escluse o azzerate"

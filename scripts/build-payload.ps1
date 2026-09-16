param(
  [string]$Version = "2.0.0",
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

function Copy-SanitizedSettings([string]$source, [string]$destination) {
  if (!(Test-Path $source)) { return }
  [xml]$xml = Get-Content -LiteralPath $source -Raw
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

# SOLO componenti custom FL-Entertainment.
# Arctic Fuse, SkinVariables, TMDb Helper e relative dipendenze vengono installati da Kodi tramite repo.

# 1) Bridge custom Stream4Me
$bridge = Join-Path $addonsRoot "plugin.video.s4me.bridge"
if (!(Test-Path (Join-Path $bridge "addon.xml"))) {
  throw "Bridge non trovato nel master: $bridge"
}
Copy-Item $bridge (Join-Path $stage "addons\plugin.video.s4me.bridge") -Recurse -Force

# 2) Configurazione UI Arctic Fuse
$skinData = Join-Path $addonDataRoot "skin.arctic.fuse.3"
if (Test-Path $skinData) {
  Copy-Item $skinData (Join-Path $stage "userdata\addon_data\skin.arctic.fuse.3") -Recurse -Force
}

# 3) Configurazione Skin Variables / menu-widget generati
$svData = Join-Path $addonDataRoot "script.skinvariables"
if (Test-Path $svData) {
  Copy-Item $svData (Join-Path $stage "userdata\addon_data\script.skinvariables") -Recurse -Force
}

# 4) TMDb Helper: solo preferenze sicure + custom players. Niente token/account/cache DB.
$tmdbSrc = Join-Path $addonDataRoot "plugin.video.themoviedb.helper"
$tmdbDst = Join-Path $stage "userdata\addon_data\plugin.video.themoviedb.helper"
if (Test-Path $tmdbSrc) {
  New-Item -ItemType Directory -Force -Path $tmdbDst | Out-Null
  Copy-SanitizedSettings (Join-Path $tmdbSrc "settings.xml") (Join-Path $tmdbDst "settings.xml")
  $players = Join-Path $tmdbSrc "players"
  if (Test-Path $players) { Copy-Item $players $tmdbDst -Recurse -Force }
}

# Stream4Me NON viene copiato dal master: il bootstrap installa la stable ufficiale.
# Unica impostazione forzata: channel_language=ita.

Get-ChildItem $stage -Recurse -Force -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -in @('.git','.gitignore','__pycache__') } |
  Sort-Object FullName -Descending |
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

if (Test-Path $outZip) { Remove-Item $outZip -Force }
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $outZip -CompressionLevel Optimal

$sizeMB = [Math]::Round((Get-Item $outZip).Length / 1MB, 2)
Write-Host "Creato: $outZip"
Write-Host "Payload custom-only: $sizeMB MB"
Write-Host "Contiene: UI config + TMDb config + bridge custom"
Write-Host "NON contiene: Arctic/TMDb/S4Me/dependency package"

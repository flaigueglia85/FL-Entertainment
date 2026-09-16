param(
  [string]$Version = "2.0.1",
  [string]$KodiRoot = "$env:APPDATA\Kodi",
  [string]$OutDir = "$PSScriptRoot\..\dist"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

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
# Addon ufficiali e dipendenze vengono installati dal bootstrap.

# 1) Bridge custom Stream4Me
$bridge = Join-Path $addonsRoot "plugin.video.s4me.bridge"
if (!(Test-Path (Join-Path $bridge "addon.xml"))) {
  throw "Bridge non trovato nel master: $bridge"
}
Copy-Item $bridge (Join-Path $stage "addons\plugin.video.s4me.bridge") -Recurse -Force

# 2) Configurazione completa Arctic Fuse 3
$skinData = Join-Path $addonDataRoot "skin.arctic.fuse.3"
if (!(Test-Path $skinData)) {
  throw "Configurazione Arctic Fuse non trovata nel master: $skinData"
}
Copy-Item $skinData (Join-Path $stage "userdata\addon_data\skin.arctic.fuse.3") -Recurse -Force

# 3) SkinVariables: menu/widget generati e relativa configurazione
$svData = Join-Path $addonDataRoot "script.skinvariables"
if (Test-Path $svData) {
  Copy-Item $svData (Join-Path $stage "userdata\addon_data\script.skinvariables") -Recurse -Force
}

# 4) TMDb Helper: preferenze sicure + custom players
$tmdbSrc = Join-Path $addonDataRoot "plugin.video.themoviedb.helper"
$tmdbDst = Join-Path $stage "userdata\addon_data\plugin.video.themoviedb.helper"
if (Test-Path $tmdbSrc) {
  New-Item -ItemType Directory -Force -Path $tmdbDst | Out-Null
  Copy-SanitizedSettings (Join-Path $tmdbSrc "settings.xml") (Join-Path $tmdbDst "settings.xml")
  $players = Join-Path $tmdbSrc "players"
  if (Test-Path $players) { Copy-Item $players $tmdbDst -Recurse -Force }
}

Get-ChildItem $stage -Recurse -Force -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -in @('.git','.gitignore','__pycache__') } |
  Sort-Object FullName -Descending |
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# IMPORTANT: niente Compress-Archive. Su Windows può produrre entry ZIP con backslash,
# che su Android/Linux diventano nomi letterali e impediscono al bootstrap di trovare
# userdata/ e addons/. Creiamo ogni entry a mano usando sempre '/'.
if (Test-Path $outZip) { Remove-Item $outZip -Force }
$fs = [System.IO.File]::Open($outZip, [System.IO.FileMode]::CreateNew)
$zip = New-Object System.IO.Compression.ZipArchive($fs, [System.IO.Compression.ZipArchiveMode]::Create, $false)
try {
  $files = Get-ChildItem -LiteralPath $stage -Recurse -File
  foreach ($file in $files) {
    $relative = $file.FullName.Substring($stage.Length).TrimStart('\','/')
    $entryName = ($relative -replace '\\','/')
    $entry = $zip.CreateEntry($entryName, [System.IO.Compression.CompressionLevel]::Optimal)
    $entryStream = $entry.Open()
    $input = [System.IO.File]::OpenRead($file.FullName)
    try { $input.CopyTo($entryStream) }
    finally {
      $input.Dispose()
      $entryStream.Dispose()
    }
  }
}
finally {
  $zip.Dispose()
  $fs.Dispose()
}

# Validazione reale del payload.
$verify = [System.IO.Compression.ZipFile]::OpenRead($outZip)
try {
  $names = @($verify.Entries | ForEach-Object { $_.FullName })
  $requiredSkinPrefix = "userdata/addon_data/skin.arctic.fuse.3/"
  $hasSkin = @($names | Where-Object { $_.StartsWith($requiredSkinPrefix) }).Count -gt 0
  if (!$hasSkin) { throw "Payload non valido: configurazione Arctic Fuse assente." }

  $hasBridge = $names -contains "addons/plugin.video.s4me.bridge/addon.xml"
  if (!$hasBridge) { throw "Payload non valido: bridge Stream4Me assente." }

  $bad = @($names | Where-Object { $_ -match '\\' })
  if ($bad.Count -gt 0) { throw "Payload non portabile: contiene backslash: $($bad -join ', ')" }
}
finally {
  $verify.Dispose()
}

Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue

$sizeMB = [Math]::Round((Get-Item $outZip).Length / 1MB, 2)
Write-Host "Creato: $outZip"
Write-Host "Payload custom-only: $sizeMB MB"
Write-Host "Arctic config: OK"
Write-Host "Bridge: OK"
Write-Host "Path ZIP portabili: OK (solo /)"

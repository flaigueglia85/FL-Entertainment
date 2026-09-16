param(
  [string]$Version = "2.0.0",
  [string]$KodiRoot = "$env:APPDATA\Kodi",
  [string]$OutDir = "$PSScriptRoot\..\dist"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$addonsRoot = Join-Path $KodiRoot "addons"
$userdataRoot = Join-Path $KodiRoot "userdata"
$addonDataRoot = Join-Path $userdataRoot "addon_data"
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
# Gli addon ufficiali NON vengono distribuiti qui: il bootstrap li installa dai repository ufficiali.

# 1) Bridge custom Stream4Me
$bridge = Join-Path $addonsRoot "plugin.video.s4me.bridge"
if (!(Test-Path (Join-Path $bridge "addon.xml"))) {
  throw "Bridge non trovato nel master: $bridge"
}
Copy-Item $bridge (Join-Path $stage "addons\plugin.video.s4me.bridge") -Recurse -Force

# 2) Arctic Fuse 3: i menu/widget personalizzati NON sono necessariamente in userdata/addon_data.
# AF3 + SkinVariables generano file runtime direttamente nella cartella 1080i della skin.
$skinRoot = Join-Path $addonsRoot "skin.arctic.fuse.3"
$skin1080 = Join-Path $skinRoot "1080i"
$skinStage1080 = Join-Path $stage "addons\skin.arctic.fuse.3\1080i"
$generatedPatterns = @(
  "script-skinvariables-generator-includes*.xml",
  "script-skinvariables-skinusers.xml",
  "script-skinshortcuts-includes.xml"
)
$generatedCount = 0
if (Test-Path $skin1080) {
  New-Item -ItemType Directory -Force -Path $skinStage1080 | Out-Null
  foreach ($pattern in $generatedPatterns) {
    foreach ($file in @(Get-ChildItem -LiteralPath $skin1080 -Filter $pattern -File -ErrorAction SilentlyContinue)) {
      Copy-Item $file.FullName (Join-Path $skinStage1080 $file.Name) -Force
      $generatedCount++
    }
  }
}

# Se esiste anche addon_data della skin, includilo; non e' obbligatorio.
$skinData = Join-Path $addonDataRoot "skin.arctic.fuse.3"
if (Test-Path $skinData) {
  Copy-Item $skinData (Join-Path $stage "userdata\addon_data\skin.arctic.fuse.3") -Recurse -Force
}

# 3) SkinVariables: qui possono esserci altri dati di configurazione/generazione.
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

# Validazione: bridge obbligatorio; per AF3 accettiamo generated XML e/o SkinVariables data.
$hasBridge = Test-Path (Join-Path $stage "addons\plugin.video.s4me.bridge\addon.xml")
$hasSkinGenerated = $generatedCount -gt 0
$hasSkinVariablesData = Test-Path (Join-Path $stage "userdata\addon_data\script.skinvariables")
if (!$hasBridge) { throw "Payload non valido: bridge assente." }
if (!$hasSkinGenerated -and !$hasSkinVariablesData) {
  throw "Payload non valido: non trovo configurazione AF3 ne' nei generated XML della skin ne' in script.skinvariables."
}

# ZIP portabile: entry create manualmente con slash (/), non Compress-Archive.
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

# Verifica reale ZIP.
$verify = [System.IO.Compression.ZipFile]::OpenRead($outZip)
try {
  $names = @($verify.Entries | ForEach-Object { $_.FullName })
  $withBackslash = @($names | Where-Object { $_ -match '\\' })
  if ($withBackslash.Count -gt 0) { throw "ZIP non portabile: contiene backslash." }
  if ($names -notcontains "addons/plugin.video.s4me.bridge/addon.xml") { throw "ZIP non valida: bridge non presente." }
}
finally {
  $verify.Dispose()
  Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
}

$sizeMB = [Math]::Round((Get-Item $outZip).Length / 1MB, 2)
Write-Host "Creato: $outZip"
Write-Host "Payload custom-only: $sizeMB MB"
Write-Host "AF3 generated XML trovati: $generatedCount"
Write-Host "SkinVariables addon_data: $hasSkinVariablesData"
Write-Host "Bridge: OK"
Write-Host "Path ZIP portabili: OK (solo /)"

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

# Scrive lo ZIP usando path LOGICI, non calcolati dai path fisici Windows.
# In questo modo le entry sono sempre addons/... o userdata/... e usano sempre '/'.
function Add-ZipTree {
  param(
    [System.IO.Compression.ZipArchive]$Zip,
    [string]$PhysicalDir,
    [string]$LogicalPrefix
  )

  foreach ($item in @(Get-ChildItem -LiteralPath $PhysicalDir -Force)) {
    $logical = if ([string]::IsNullOrEmpty($LogicalPrefix)) {
      $item.Name
    } else {
      "$LogicalPrefix/$($item.Name)"
    }

    if ($item.PSIsContainer) {
      Add-ZipTree -Zip $Zip -PhysicalDir $item.FullName -LogicalPrefix $logical
    }
    else {
      $entry = $Zip.CreateEntry($logical, [System.IO.Compression.CompressionLevel]::Optimal)
      $entryStream = $entry.Open()
      $input = [System.IO.File]::OpenRead($item.FullName)
      try { $input.CopyTo($entryStream) }
      finally {
        $input.Dispose()
        $entryStream.Dispose()
      }
    }
  }
}

# SOLO componenti custom FL-Entertainment.
# Gli addon ufficiali NON vengono distribuiti qui: il bootstrap li installa dai repository ufficiali.

# 1) Bridge custom Stream4Me
$bridge = Join-Path $addonsRoot "plugin.video.s4me.bridge"
if (!(Test-Path (Join-Path $bridge "addon.xml"))) {
  throw "Bridge non trovato nel master: $bridge"
}
Copy-Item $bridge (Join-Path $stage "addons\plugin.video.s4me.bridge") -Recurse -Force

# 2) Arctic Fuse 3: menu/widget generati runtime nella 1080i della skin.
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

# 3) SkinVariables.
$svData = Join-Path $addonDataRoot "script.skinvariables"
if (Test-Path $svData) {
  Copy-Item $svData (Join-Path $stage "userdata\addon_data\script.skinvariables") -Recurse -Force
}

# 4) TMDb Helper: solo preferenze sicure + custom players.
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

$hasBridge = Test-Path (Join-Path $stage "addons\plugin.video.s4me.bridge\addon.xml")
$hasSkinGenerated = $generatedCount -gt 0
$hasSkinVariablesData = Test-Path (Join-Path $stage "userdata\addon_data\script.skinvariables")
if (!$hasBridge) { throw "Payload non valido: bridge assente nello staging." }
if (!$hasSkinGenerated -and !$hasSkinVariablesData) {
  throw "Payload non valido: non trovo configurazione AF3 ne' nei generated XML della skin ne' in script.skinvariables."
}

# ZIP portabile: NON calcoliamo piu' alcun path relativo dal filesystem Windows.
if (Test-Path $outZip) { Remove-Item $outZip -Force }
$fs = [System.IO.File]::Open($outZip, [System.IO.FileMode]::CreateNew)
$zip = New-Object System.IO.Compression.ZipArchive($fs, [System.IO.Compression.ZipArchiveMode]::Create, $false)
try {
  Add-ZipTree -Zip $zip -PhysicalDir (Join-Path $stage "addons") -LogicalPrefix "addons"
  Add-ZipTree -Zip $zip -PhysicalDir (Join-Path $stage "userdata") -LogicalPrefix "userdata"
}
finally {
  $zip.Dispose()
  $fs.Dispose()
}

# Verifica reale ZIP.
$verify = [System.IO.Compression.ZipFile]::OpenRead($outZip)
try {
  $names = @($verify.Entries | ForEach-Object { $_.FullName })
  $withBackslash = @($names | Where-Object { $_.Contains([string][char]92) })
  if ($withBackslash.Count -gt 0) {
    throw "ZIP non portabile: contiene backslash: $($withBackslash -join ', ')"
  }

  $foreign = @($names | Where-Object { $_ -and -not ($_.StartsWith('addons/') -or $_.StartsWith('userdata/')) })
  if ($foreign.Count -gt 0) {
    throw "ZIP non valida: entry fuori root logiche: $($foreign -join ', ')"
  }

  if ($names -notcontains "addons/plugin.video.s4me.bridge/addon.xml") {
    $preview = (($names | Select-Object -First 20) -join ', ')
    throw "ZIP non valida: bridge non presente. Entries: $preview"
  }
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
Write-Host "Path ZIP portabili: OK (solo addons/ e userdata/)"

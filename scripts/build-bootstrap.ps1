param(
  [string]$Version = "2.0.0"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.IO.Compression.FileSystem

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$src = Join-Path $root "bootstrap\plugin.program.flentertainment.bootstrap"
$outDir = Join-Path $root "dist"
$outZip = Join-Path $outDir "plugin.program.flentertainment.bootstrap-$Version.zip"
$stage = Join-Path $env:TEMP "FL-Entertainment-bootstrap-$Version"
$addonId = "plugin.program.flentertainment.bootstrap"
$stageAddon = Join-Path $stage $addonId

if (!(Test-Path $src)) { throw "Bootstrap source non trovato: $src" }
if (!(Test-Path (Join-Path $src "addon.xml"))) { throw "addon.xml mancante nel bootstrap source." }

New-Item -ItemType Directory -Force -Path $outDir | Out-Null
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $stageAddon | Out-Null

# Copia il contenuto del source dentro una sola cartella addon di primo livello.
# Kodi richiede: plugin.program.flentertainment.bootstrap/addon.xml
Copy-Item (Join-Path $src "*") $stageAddon -Recurse -Force

if (Test-Path $outZip) { Remove-Item $outZip -Force }
[System.IO.Compression.ZipFile]::CreateFromDirectory($stage, $outZip, [System.IO.Compression.CompressionLevel]::Optimal, $false)

# Verifica struttura ZIP prima di consegnarla a Kodi.
$zip = [System.IO.Compression.ZipFile]::OpenRead($outZip)
try {
  # ZipArchive su Windows può restituire nomi con backslash: normalizziamo a slash.
  $names = @($zip.Entries | ForEach-Object { $_.FullName.Replace('\','/') })
  $required = "$addonId/addon.xml"
  if ($names -notcontains $required) {
    $preview = (($names | Select-Object -First 10) -join ', ')
    throw "ZIP non valida: manca $required. Prime entries: $preview"
  }
  $foreignTop = @($names | Where-Object { $_ -and -not $_.StartsWith("$addonId/") })
  if ($foreignTop.Count -gt 0) {
    throw "ZIP non valida: file fuori dalla cartella addon: $($foreignTop -join ', ')"
  }
}
finally {
  $zip.Dispose()
  Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Creato: $outZip"
Write-Host "Struttura Kodi OK: $addonId/addon.xml"

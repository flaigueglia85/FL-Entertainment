param(
  [string]$Version = "2.0.0"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$src = Join-Path $root "bootstrap\plugin.program.flentertainment.bootstrap"
$outDir = Join-Path $root "dist"
$outZip = Join-Path $outDir "plugin.program.flentertainment.bootstrap-$Version.zip"
$addonId = "plugin.program.flentertainment.bootstrap"

if (!(Test-Path $src)) { throw "Bootstrap source non trovato: $src" }
if (!(Test-Path (Join-Path $src "addon.xml"))) { throw "addon.xml mancante nel bootstrap source." }

New-Item -ItemType Directory -Force -Path $outDir | Out-Null
if (Test-Path $outZip) { Remove-Item $outZip -Force }

# IMPORTANT: non usare CreateFromDirectory su Windows.
# Può scrivere nomi entry con backslash (\), che Kodi su Android può considerare struttura non valida.
# Creiamo ogni entry a mano usando SEMPRE slash (/).
$fs = [System.IO.File]::Open($outZip, [System.IO.FileMode]::CreateNew)
$zip = New-Object System.IO.Compression.ZipArchive($fs, [System.IO.Compression.ZipArchiveMode]::Create, $false)
try {
  $files = Get-ChildItem -LiteralPath $src -Recurse -File
  foreach ($file in $files) {
    $relative = $file.FullName.Substring($src.Length).TrimStart('\','/')
    $entryName = ($addonId + '/' + ($relative -replace '\\','/'))
    $entry = $zip.CreateEntry($entryName, [System.IO.Compression.CompressionLevel]::Optimal)
    $entryStream = $entry.Open()
    $input = [System.IO.File]::OpenRead($file.FullName)
    try {
      $input.CopyTo($entryStream)
    }
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

# Verifica reale: nessuna entry deve contenere backslash e addon.xml deve stare nel path Kodi atteso.
$verify = [System.IO.Compression.ZipFile]::OpenRead($outZip)
try {
  $names = @($verify.Entries | ForEach-Object { $_.FullName })
  $required = "$addonId/addon.xml"

  if ($names -notcontains $required) {
    $preview = (($names | Select-Object -First 10) -join ', ')
    throw "ZIP non valida: manca $required. Prime entries: $preview"
  }

  $withBackslash = @($names | Where-Object { $_ -match '\\' })
  if ($withBackslash.Count -gt 0) {
    throw "ZIP non portabile: contiene path con backslash: $($withBackslash -join ', ')"
  }

  $foreignTop = @($names | Where-Object { $_ -and -not $_.StartsWith("$addonId/") })
  if ($foreignTop.Count -gt 0) {
    throw "ZIP non valida: file fuori dalla cartella addon: $($foreignTop -join ', ')"
  }
}
finally {
  $verify.Dispose()
}

Write-Host "Creato: $outZip"
Write-Host "Struttura Kodi OK: $addonId/addon.xml"
Write-Host "Path ZIP portabili OK: usa solo /"

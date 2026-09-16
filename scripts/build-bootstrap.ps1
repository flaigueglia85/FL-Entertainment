param(
  [string]$Version = "2.1.3"
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

$fs = [System.IO.File]::Open($outZip, [System.IO.FileMode]::CreateNew)
$zip = New-Object System.IO.Compression.ZipArchive($fs, [System.IO.Compression.ZipArchiveMode]::Create, $false)
try {
  foreach ($file in Get-ChildItem -LiteralPath $src -Recurse -File) {
    $srcFull = [System.IO.Path]::GetFullPath($src).TrimEnd([char]92,[char]47)
    $fileFull = [System.IO.Path]::GetFullPath($file.FullName)
    if (!$fileFull.StartsWith($srcFull, [System.StringComparison]::OrdinalIgnoreCase)) {
      throw "File fuori source bootstrap: $fileFull"
    }
    $relative = $fileFull.Substring($srcFull.Length).TrimStart([char]92,[char]47)
    $relative = $relative.Replace([char]92, [char]47)
    $entryName = "$addonId/$relative"
    $entry = $zip.CreateEntry($entryName, [System.IO.Compression.CompressionLevel]::Optimal)
    $entryStream = $entry.Open()
    $input = [System.IO.File]::OpenRead($fileFull)
    try { $input.CopyTo($entryStream) }
    finally { $input.Dispose(); $entryStream.Dispose() }
  }
}
finally {
  $zip.Dispose()
  $fs.Dispose()
}

$verify = [System.IO.Compression.ZipFile]::OpenRead($outZip)
try {
  $names = @($verify.Entries | ForEach-Object { $_.FullName })
  $required = "$addonId/addon.xml"
  if ($names -notcontains $required) {
    throw "ZIP non valida: manca $required. Entries: $(($names | Select-Object -First 15) -join ', ')"
  }
  $bad = @($names | Where-Object { $_.Contains([string][char]92) -or $_.Contains('../') -or -not $_.StartsWith("$addonId/") })
  if ($bad.Count -gt 0) {
    throw "ZIP bootstrap non portabile: $($bad -join ', ')"
  }
}
finally { $verify.Dispose() }

Write-Host "Creato: $outZip"
Write-Host "Struttura Kodi OK: $addonId/addon.xml"
Write-Host "Path ZIP portabili OK"

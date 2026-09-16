param(
  [string]$Version = "1.0.3"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$src = Join-Path $root "bootstrap\plugin.program.flentertainment.bootstrap"
$outDir = Join-Path $root "dist"
$outZip = Join-Path $outDir "plugin.program.flentertainment.bootstrap-$Version.zip"

if (!(Test-Path $src)) { throw "Bootstrap source non trovato: $src" }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
if (Test-Path $outZip) { Remove-Item $outZip -Force }

Compress-Archive -Path $src -DestinationPath $outZip -CompressionLevel Optimal
Write-Host "Creato: $outZip"

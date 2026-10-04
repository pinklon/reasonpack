param([switch]$InstallWSL)
$ErrorActionPreference = 'Stop'
Write-Host 'ReasonPack Windows bootstrap (WSL)' -ForegroundColor Cyan
$wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
if (-not $wsl) { if ($InstallWSL) { wsl.exe --install -d Ubuntu; exit $LASTEXITCODE }; Write-Host 'WSL is not installed. Re-run elevated with: .\install-windows-wsl.ps1 -InstallWSL' -ForegroundColor Yellow; exit 20 }
$here = Split-Path -Parent $PSScriptRoot
$linuxPath = (wsl.exe wslpath -a $here).Trim()
wsl.exe bash -lc "cd '$linuxPath' && ./install/install-wsl.sh"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host 'PASS: ReasonPack installed inside WSL.' -ForegroundColor Green

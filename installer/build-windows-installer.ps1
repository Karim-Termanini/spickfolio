# Build spickFolio-Setup.exe — graphical Windows installer (bundles Python runtime via PyInstaller).
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Version = (Get-Content VERSION -Raw).Trim()
$env:SPICKFOLIO_VERSION = $Version

Write-Host "==> spickFolio $Version - Windows installer build"

python -m pip install -q -r requirements-packaging.txt
python installer/render_assets.py

Write-Host "==> PyInstaller bundle"
pyinstaller --noconfirm spickfolio.spec
if (-not (Test-Path "dist\spickFolio.exe")) {
    throw "dist\spickFolio.exe was not created"
}

$IsccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
)
$Iscc = $IsccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Iscc) {
    throw "Inno Setup 6 not found. Install from https://jrsoftware.org/isinfo.php or: choco install innosetup"
}

Write-Host "==> Inno Setup"
& $Iscc "/DMyAppVersion=$Version" "installer\windows\spickfolio.iss"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$Setup = "dist\spickFolio-Setup-$Version.exe"
Write-Host ""
Write-Host "Built:"
Write-Host "  dist\spickFolio.exe"
Write-Host "  $Setup"

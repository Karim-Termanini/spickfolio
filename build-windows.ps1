# Build spickFolio.exe only. For the graphical setup wizard use installer\build-windows-installer.ps1
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
python -m pip install -q -r requirements-packaging.txt
pyinstaller --noconfirm spickfolio.spec
Write-Host "Built: dist\spickFolio.exe"

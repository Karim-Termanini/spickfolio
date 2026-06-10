# Start the local server and open spickFolio in a browser window (Windows).
param(
    [switch]$Stop,
    [switch]$ServerOnly
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

if ($Stop) {
    python -m spick_folio.launcher --stop
    exit $LASTEXITCODE
}

if ($ServerOnly) {
    python server.py
    exit $LASTEXITCODE
}

python -m spick_folio.launcher @args
exit $LASTEXITCODE

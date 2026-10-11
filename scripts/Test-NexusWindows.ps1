param([string]$Python = ".venv\Scripts\python.exe", [switch]$OfflineAttested)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try {
    if ([Environment]::OSVersion.Platform -ne 'Win32NT') { throw 'Windows required' }
    $repo = Split-Path $PSScriptRoot -Parent
    Set-Location -LiteralPath $repo
    $argsList = @('-m', 'nexus.machine_check')
    if ($OfflineAttested) { $argsList += '--offline-attested' }
    & $Python @argsList
    exit $LASTEXITCODE
} catch {
    [Console]::Error.WriteLine('Nexus check could not start. No private error details were logged.')
    exit 1
}

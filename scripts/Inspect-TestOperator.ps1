$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try {
    if ([Environment]::OSVersion.Platform -ne 'Win32NT') { throw 'Windows required' }
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    $standard = -not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    @{ standard_user = [bool]$standard } | ConvertTo-Json -Compress
    if (-not $standard) { exit 1 }
} catch {
    [Console]::Error.WriteLine('Owned machine check requires an unelevated Windows process.')
    exit 1
}

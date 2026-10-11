param([Parameter(Mandatory=$true)][int]$ProcessId)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try {
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort 8788)
    $safe = $listeners.Count -eq 1
    foreach ($listener in $listeners) {
        if ($listener.OwningProcess -ne $ProcessId -or $listener.LocalAddress -ne '127.0.0.1') { $safe = $false }
    }
    @{ owned_loopback_only = [bool]$safe } | ConvertTo-Json -Compress
    if (-not $safe) { exit 1 }
} catch {
    [Console]::Error.WriteLine('Owned test listener check refused or failed.')
    exit 1
}

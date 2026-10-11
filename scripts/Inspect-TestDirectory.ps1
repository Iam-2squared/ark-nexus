param([Parameter(Mandatory=$true)][string]$Directory, [switch]$Protect)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try {
    $repo = Split-Path $PSScriptRoot -Parent
    $base = [IO.Path]::GetFullPath((Join-Path $repo 'tmp\windows-evidence')) + '\'
    $path = [IO.Path]::GetFullPath($Directory)
    if (-not $path.StartsWith($base, [StringComparison]::OrdinalIgnoreCase)) { throw 'Scope' }
    $relative = $path.Substring($base.Length)
    if ($relative.Split('\')[0] -notmatch '^[0-9a-f]{32}$') { throw 'Owned directory required' }
    $item = Get-Item -LiteralPath $path -Force
    $cursor = $item
    while ($null -ne $cursor) {
        if (($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Link' }
        $cursor = $cursor.Parent
        if ($item -is [IO.FileInfo] -and $null -eq $cursor) { $cursor = $item.Directory; $item = $cursor }
    }
    $current = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $allowed = @($current.Value, 'S-1-5-18', 'S-1-5-32-544')
    $acl = Get-Acl -LiteralPath $path
    if ($allowed -notcontains $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value) { throw 'Owner' }
    if ($Protect) {
        if ($relative -notmatch '^[0-9a-f]{32}$' -or -not (Test-Path -LiteralPath $path -PathType Container)) { throw 'Scope' }
        if (@(Get-ChildItem -LiteralPath $path -Force).Count -ne 0) { throw 'New empty directory required' }
        $acl = New-Object Security.AccessControl.DirectorySecurity
        $acl.SetOwner($current)
        $acl.SetAccessRuleProtection($true, $false)
        foreach ($sid in $allowed) {
            $identity = New-Object Security.Principal.SecurityIdentifier($sid)
            $rule = New-Object Security.AccessControl.FileSystemAccessRule(
                $identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
            $acl.AddAccessRule($rule)
        }
        Set-Acl -LiteralPath $path -AclObject $acl
        $acl = Get-Acl -LiteralPath $path
    }
    $rules = @($acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
    $safe = $rules.Count -gt 0
    $required = @{}
    foreach ($rule in $rules) {
        if ($allowed -notcontains $rule.IdentityReference.Value -or $rule.AccessControlType -ne 'Allow') { $safe = $false }
        if (($rule.FileSystemRights -band [Security.AccessControl.FileSystemRights]::FullControl) -eq [Security.AccessControl.FileSystemRights]::FullControl) {
            $required[$rule.IdentityReference.Value] = $true
        }
    }
    foreach ($sid in $allowed) { if (-not $required.ContainsKey($sid)) { $safe = $false } }
    @{ allowlist_only = [bool]$safe; owner_allowed = $true; protected_root = [bool]$acl.AreAccessRulesProtected } | ConvertTo-Json -Compress
    if (-not $safe) { exit 1 }
} catch {
    [Console]::Error.WriteLine('Owned test directory ACL check refused or failed.')
    exit 1
}

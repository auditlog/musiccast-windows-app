# Read-only detection. Endpoint renaming must not trigger a driver reinstallation.
param([switch]$FunctionsOnly)
$ErrorActionPreference = 'Stop'
function Get-BridgeCableState {
    try {
        $devices = @(Get-CimInstance -ClassName Win32_PnPEntity -Filter "PNPClass = 'MEDIA'")
        $cable = @($devices | Where-Object {
            $_.Name -eq 'VB-Audio Virtual Cable' -or
            $_.Service -match '^(vbaudio_cable(?:64)?(?:_win\d+|_2003)?|vbaudiovacwdm|vbaudiovacmme)$'
        })
        if ($cable.Count -eq 0) { return 20 }
        if (@($cable | Where-Object { $_.ConfigManagerErrorCode -eq 0 }).Count -gt 0) { return 0 }
        if (@($cable | Where-Object { $_.ConfigManagerErrorCode -eq 14 }).Count -gt 0) { return 11 }
        return 10 # Present with a problem, not proof of a required restart.
    } catch {
        return 30 # Detection failed. Do not assume that the driver is absent.
    }
}
if (-not $FunctionsOnly) { exit (Get-BridgeCableState) }

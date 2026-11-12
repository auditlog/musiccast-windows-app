# Runs during the Windows build. Fixtures replace CIM; no physical device is changed.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'check-cable.ps1') -FunctionsOnly
$script:Devices = @()
$script:FailCim = $false
function Get-CimInstance {
    param($ClassName, $Filter)
    if ($ClassName -ne 'Win32_PnPEntity' -or $Filter -ne "PNPClass = 'MEDIA'") {
        throw 'Unexpected device query'
    }
    if ($script:FailCim) { throw 'Synthetic CIM failure' }
    return $script:Devices
}
function Assert-State($Expected, $Fixtures) {
    $script:Devices = $Fixtures
    $actual = Get-BridgeCableState
    if ($actual -ne $Expected) { throw "Expected state $Expected; got $actual" }
}
Assert-State 20 @()
Assert-State 0 @([pscustomobject]@{
    Name = 'VB-Audio Virtual Cable'; Service = 'vbaudio_cable64_win7'; ConfigManagerErrorCode = 0
})
Assert-State 0 @([pscustomobject]@{
    Name = 'Renamed controller'; Service = 'VBAudioVACMME'; ConfigManagerErrorCode = 0
})
Assert-State 11 @([pscustomobject]@{
    Name = 'VB-Audio Virtual Cable'; Service = 'vbaudio_cable64_win7'; ConfigManagerErrorCode = 14
})
foreach ($code in @(22, 28, 31)) {
    Assert-State 10 @([pscustomobject]@{
        Name = 'VB-Audio Virtual Cable'; Service = 'vbaudio_cable64_win7'; ConfigManagerErrorCode = $code
    })
}
Assert-State 20 @([pscustomobject]@{
    Name = 'VB-Audio Cable A'; Service = 'vbaudio_cablea64_win7'; ConfigManagerErrorCode = 0
})
Assert-State 20 @([pscustomobject]@{
    Name = 'VB-Audio Hi-Fi Cable'; Service = 'vbaudio_hficable64'; ConfigManagerErrorCode = 0
})
$script:FailCim = $true
if ((Get-BridgeCableState) -ne 30) { throw 'CIM failure treated as missing device' }
Write-Output 'VB-CABLE detection fixtures passed; no device was changed.'

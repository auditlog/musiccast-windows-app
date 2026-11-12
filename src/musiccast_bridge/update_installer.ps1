param(
    [Parameter(Mandatory=$true)][string]$Installer,
    [Parameter(Mandatory=$true)][int]$ParentProcessId,
    [Parameter(Mandatory=$true)][string]$InstallDirectory,
    [Parameter(Mandatory=$true)][ValidateSet('polish','english')][string]$Language,
    [Parameter(Mandatory=$true)][string]$ReadyFile
)
$ErrorActionPreference = 'Stop'
# Arguments arrive as data through -File, never as evaluated PowerShell text.
if (-not (Test-Path -LiteralPath $Installer -PathType Leaf)) { exit 1 }
$parentProcess = [System.Diagnostics.Process]::GetProcessById($ParentProcessId)
[System.IO.File]::WriteAllText($ReadyFile, 'ready')
try {
    # The app's normal shutdown stops AirPlay and restores the Windows route.
    if (-not $parentProcess.WaitForExit(120000)) { exit 2 }
} finally {
    $parentProcess.Dispose()
    Remove-Item -LiteralPath $ReadyFile -ErrorAction SilentlyContinue
}
# Reuse the existing installation, without touching the shared VB-CABLE driver.
# Keep the normal installation wizard and its final application-launch checkbox.
$arguments = @('/SP-', '/NORESTART', '/TYPE=app', '/COMPONENTS=app',
               "/LANG=$Language", ('/DIR="' + $InstallDirectory + '"'))
Start-Process -FilePath $Installer -ArgumentList $arguments

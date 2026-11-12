; Build with scripts/build_installer.py (Inno Setup 6.3+).
#include "..\build\installer\generated.iss"

[Setup]
AppId={{CE44C1A5-55CC-4301-9BDD-F5D61FC8C902}
AppName=MusicCast Bridge
AppVersion={#BridgeVersion}
VersionInfoVersion={#BridgeVersion}
VersionInfoProductVersion={#BridgeVersion}
DefaultDirName={localappdata}\Programs\MusicCastBridge
DefaultGroupName=MusicCast Bridge
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0
OutputDir=..\dist\installer
OutputBaseFilename=MusicCastBridge-{#BridgeVersion}-Setup-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=yes
UninstallDisplayIcon={app}\MusicCastBridge.exe
AppMutex=Local\MusicCastBridge.App
CloseApplications=no
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"; LicenseFile: "{#StagePath}\license-en.txt"; InfoBeforeFile: "{#StagePath}\info-en.txt"
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"; LicenseFile: "{#StagePath}\license-pl.txt"; InfoBeforeFile: "{#StagePath}\info-pl.txt"

[CustomMessages]
polish.FullInstall=Aplikacja i VB-CABLE
english.FullInstall=Application and VB-CABLE
polish.AppOnly=Sama aplikacja
english.AppOnly=Application only
polish.CustomInstall=Wybór składników
english.CustomInstall=Custom installation
polish.CableComponent=VB-CABLE: odsłuch tylko na Yamasze
english.CableComponent=VB-CABLE: listen on Yamaha only
polish.DesktopShortcut=Utwórz skrót na pulpicie
english.DesktopShortcut=Create a desktop shortcut
polish.UninstallApp=Odinstaluj MusicCast Bridge
english.UninstallApp=Uninstall MusicCast Bridge
polish.LaunchApp=Uruchom MusicCast Bridge
english.LaunchApp=Launch MusicCast Bridge
polish.CableProblem=VB-CABLE jest wykryty, ale Windows zgłasza problem urządzenia. Sprawdź sterownik w Menedżerze urządzeń lub wybierz samą aplikację. Wspólny sterownik nie będzie automatycznie przeinstalowany.
english.CableProblem=VB-CABLE is present, but Windows reports a device problem. Check Device Manager or choose Application only. The shared driver will not be reinstalled automatically.
polish.CableUnknown=Nie można sprawdzić, czy VB-CABLE jest zainstalowany. Wróć do wyboru składników i wybierz samą aplikację albo ponów próbę.
english.CableUnknown=Could not determine whether VB-CABLE is installed. Return to component selection and choose Application only, or try again.
polish.CableLaunchFailed=Nie uruchomiono instalacji VB-CABLE: %1. Możesz ponowić próbę lub wybrać samą aplikację.
english.CableLaunchFailed=VB-CABLE installation could not start: %1. Try again or choose Application only.
polish.CableUnconfirmed=Instalator VB-CABLE zakończył pracę (kod %1), ale nie potwierdzono obecności sterownika. Uruchom ponownie Windows i spróbuj jeszcze raz lub wybierz samą aplikację. Status wykrywania: %2.
english.CableUnconfirmed=The VB-CABLE installer exited (code %1), but the driver was not confirmed. Restart Windows and try again, or choose Application only. Detection status: %2.

[Types]
Name: "full"; Description: "{cm:FullInstall}"
Name: "app"; Description: "{cm:AppOnly}"
Name: "custom"; Description: "{cm:CustomInstall}"; Flags: iscustom

[Components]
Name: "app"; Description: "MusicCast Bridge"; Types: full app custom; Flags: fixed
Name: "cable"; Description: "{cm:CableComponent}"; Types: full

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopShortcut}"; Flags: unchecked

[Files]
; Temporary dependencies first: avoid unpacking the whole app before checking the driver.
Source: "check-cable.ps1"; DestDir: "{tmp}"; Flags: dontcopy
Source: "{#CableRootPath}\*"; DestDir: "{tmp}\vbcable"; Flags: dontcopy recursesubdirs createallsubdirs
Source: "{#AppBundlePath}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#StagePath}\VB-CABLE-NOTICE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#StagePath}\vbcable-package.json"; DestDir: "{app}"; Flags: ignoreversion

[INI]
Filename: "{app}\install.ini"; Section: "General"; Key: "LanguageSelection"; String: "{code:LanguageSelection}"
Filename: "{app}\install.ini"; Section: "General"; Key: "Language"; String: "{language}"
Filename: "{app}\install.ini"; Section: "Audio"; Key: "PreferCable"; String: "{code:CablePreference}"

[InstallDelete]
Type: files; Name: "{group}\Odinstaluj MusicCast Bridge.lnk"
Type: files; Name: "{group}\Uninstall MusicCast Bridge.lnk"

[Icons]
Name: "{group}\MusicCast Bridge"; Filename: "{app}\MusicCastBridge.exe"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallApp}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\MusicCast Bridge"; Filename: "{app}\MusicCastBridge.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\MusicCastBridge.exe"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent; Check: CanLaunchApp

[UninstallDelete]
Type: files; Name: "{app}\install.ini"

[Code]
var
  CableRestartRequired: Boolean;

function SelectionTick: LongWord;
  external 'GetTickCount@kernel32.dll stdcall';

function LanguageSelection(Param: String): String;
begin
  Result := GetDateTimeString('yyyymmddhhnnss', '-', ':') + '-' + IntToStr(SelectionTick);
end;

function CablePreference(Param: String): String;
begin
  if WizardIsComponentSelected('cable') then Result := '1'
  else Result := '0';
end;

function CableState: Integer;
var
  ExitCode: Integer;
begin
  ExtractTemporaryFile('check-cable.ps1');
  if Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
    ExpandConstant('{tmp}\check-cable.ps1') + '"', '', SW_HIDE,
    ewWaitUntilTerminated, ExitCode) then Result := ExitCode
  else Result := 30;
  Log('VB-CABLE detection status: ' + IntToStr(Result));
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  State, DriverExit: Integer;
begin
  Result := '';
  if not WizardIsComponentSelected('cable') then Exit;
  State := CableState;
  if State = 0 then Exit;
  if State = 11 then begin
    CableRestartRequired := True;
    Log('VB-CABLE already present and needs restart. Skipping shared driver.');
    Exit;
  end;
  if State = 10 then begin
    Result := CustomMessage('CableProblem');
    Exit;
  end;
  if State <> 20 then begin
    Result := CustomMessage('CableUnknown');
    Exit;
  end;
  ExtractTemporaryFiles('{tmp}\vbcable\*');
  if not ShellExec('runas', ExpandConstant('{tmp}\vbcable\VBCABLE_Setup_x64.exe'),
    '-i -h', ExpandConstant('{tmp}\vbcable'), SW_SHOWNORMAL,
    ewWaitUntilTerminated, DriverExit) then begin
    Result := FmtMessage(CustomMessage('CableLaunchFailed'), [SysErrorMessage(DriverExit)]);
    Exit;
  end;
  Log('VB-CABLE installer exit code: ' + IntToStr(DriverExit));
  { Do not assume undocumented vendor exit codes mean success. Verify the device. }
  State := CableState;
  if (State = 0) or (State = 11) then begin
    CableRestartRequired := True;
  end else begin
    Result := FmtMessage(CustomMessage('CableUnconfirmed'), [IntToStr(DriverExit), IntToStr(State)]);
  end;
end;

function NeedRestart: Boolean;
begin
  Result := CableRestartRequired;
end;

function CanLaunchApp: Boolean;
begin
  Result := not CableRestartRequired;
end;

{ The shared driver, LocalAppData settings and Credential Manager entries are
  intentionally not registered for removal with this application. }


; NeoRecorder Setup Script for Inno Setup
; Download Inno Setup from https://jrsoftware.org/isdl.php
; Compile with: iscc setup_script.iss

#define MyAppName "NeoRecorder"
#define MyAppVersion "1.4.0"
#define MyAppPublisher "DimSimd"
#define MyAppURL "https://github.com/DimSimd2020/NeoRecorder"
#define MyAppExeName "NeoRecorder.exe"

[Setup]
AppId={{D37FCE9A-8C35-4A9B-92AA-442E48B585D4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=LICENSE
OutputDir=setup
OutputBaseFilename=NeoRecorder_Setup_v{#MyAppVersion}
SetupIconFile=app_icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
DisableWelcomePage=no
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; Main executable
Source: "dist\NeoRecorder.exe"; DestDir: "{app}"; Flags: ignoreversion

; FFmpeg binary (critical for app functionality)
Source: "ffmpeg.exe"; DestDir: "{app}"; Flags: ignoreversion; Check: FileExists('ffmpeg.exe')

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
Type: dirifempty; Name: "{userappdata}\NeoRecorder"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
  
  // Check for minimum Windows version (Windows 10)
  if not IsWin64 then
  begin
    MsgBox('NeoRecorder requires 64-bit Windows 10 or later.', mbError, MB_OK);
    Result := False;
  end;
  
  // Check if FFmpeg exists
  if not FileExists(ExpandConstant('{src}\ffmpeg.exe')) then
  begin
    MsgBox('FFmpeg.exe not found in the installer directory. Please download FFmpeg from https://ffmpeg.org/download.html and place it in the same folder as this installer.', mbError, MB_OK);
    Result := False;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Create Videos\NeoRecorder folder for user
    ForceDirectories(ExpandConstant('{userdocs}\..\Videos\NeoRecorder'));
  end;
end;


; NeoRecorder Setup Script for Inno Setup
; Download Inno Setup from https://jrsoftware.org/isdl.php
; Compile with: iscc setup_script.iss

#define MyAppName "NeoRecorder"
#define MyAppVersion "1.4.7"
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
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; Main executable
Source: "dist\NeoRecorder.exe"; DestDir: "{app}"; Flags: ignoreversion

; FFmpeg will be downloaded during installation
; If bundled ffmpeg exists, use it
Source: "ffmpeg.exe"; DestDir: "{app}"; Flags: ignoreversion external skipifsourcedoesntexist

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
var
  DownloadPage: TDownloadWizardPage;

const
  FFMPEG_URL = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip';
  FFMPEG_ZIP = 'ffmpeg.zip';

function OnDownloadProgress(const Url, FileName: String; const Progress, ProgressMax: Int64): Boolean;
begin
  if Progress = ProgressMax then
    Log(Format('Successfully downloaded file to {tmp}: %s', [FileName]));
  Result := True;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  
  // Check for minimum Windows version (Windows 10 64-bit)
  if not IsWin64 then
  begin
    MsgBox('NeoRecorder requires 64-bit Windows 10 or later.', mbError, MB_OK);
    Result := False;
  end;
end;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage(SetupMessage(msgWizardPreparing), SetupMessage(msgPreparingDesc), @OnDownloadProgress);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  ResultCode: Integer;
  TempDir: String;
  FFmpegExe: String;
begin
  Result := True;
  
  if CurPageID = wpReady then
  begin
    // Check if FFmpeg already exists in app dir or bundled
    FFmpegExe := ExpandConstant('{app}\ffmpeg.exe');
    
    // If FFmpeg not bundled with installer, download it
    if not FileExists(ExpandConstant('{src}\ffmpeg.exe')) then
    begin
      DownloadPage.Clear;
      DownloadPage.Add(FFMPEG_URL, FFMPEG_ZIP, '');
      DownloadPage.Show;
      
      try
        try
          DownloadPage.Download;
          
          // Extract ffmpeg.exe from ZIP
          TempDir := ExpandConstant('{tmp}');
          
          // Use PowerShell to extract
          Exec('powershell.exe', 
            '-NoProfile -ExecutionPolicy Bypass -Command "' +
            '$zip = ''' + TempDir + '\' + FFMPEG_ZIP + '''; ' +
            '$dest = ''' + TempDir + '\ffmpeg_extract''; ' +
            'Expand-Archive -Path $zip -DestinationPath $dest -Force; ' +
            '$ffmpeg = Get-ChildItem -Path $dest -Recurse -Filter ''ffmpeg.exe'' | Select-Object -First 1; ' +
            'if ($ffmpeg) { Copy-Item $ffmpeg.FullName -Destination ''' + TempDir + '\ffmpeg.exe'' -Force }"',
            '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
          
          Result := True;
        except
          if DownloadPage.AbortedByUser then
            Log('Download aborted by user.')
          else
            MsgBox('Failed to download FFmpeg. Please check your internet connection.', mbError, MB_OK);
          Result := False;
        end;
      finally
        DownloadPage.Hide;
      end;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  TempFFmpeg: String;
  DestFFmpeg: String;
begin
  if CurStep = ssPostInstall then
  begin
    // Create Videos\NeoRecorder folder for user
    ForceDirectories(ExpandConstant('{userdocs}\..\Videos\NeoRecorder'));
    ForceDirectories(ExpandConstant('{userdocs}\..\Videos\NeoRecorder\Screenshots'));
    
    // Copy downloaded FFmpeg to app directory
    TempFFmpeg := ExpandConstant('{tmp}\ffmpeg.exe');
    DestFFmpeg := ExpandConstant('{app}\ffmpeg.exe');
    
    if FileExists(TempFFmpeg) and not FileExists(DestFFmpeg) then
    begin
      FileCopy(TempFFmpeg, DestFFmpeg, False);
      Log('FFmpeg copied from temp to app directory');
    end;
  end;
end;

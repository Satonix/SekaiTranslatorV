#define MyAppName "SekaiTranslatorV"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Satonix"
#define MyAppExeName "SekaiTranslatorV.exe"

[Setup]
AppId={{A9E6C8C9-0D6C-4E4F-9F8B-2B9B9C5D8B11}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=installer_output
OutputBaseFilename=SekaiTranslatorV_Setup_{#MyAppVersion}
SetupIconFile=sekai-ui\assets\app_icon.ico
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "release\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\SekaiTranslatorV"; Filename: "{app}\SekaiTranslatorV.exe"
Name: "{commondesktop}\SekaiTranslatorV"; Filename: "{app}\SekaiTranslatorV.exe"

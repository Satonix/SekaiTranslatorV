; ==========================================
; SekaiTranslatorV - Inno Setup Script
; ==========================================

#define MyAppName "SekaiTranslatorV"
#define MyAppPublisher "Satonix"
#define MyAppExeName "SekaiTranslatorV.exe"

; Se o CI passar /DAPP_VER=0.1.2 usa essa versão.
; Se não passar (build manual), usa fallback.
#if Defined(APP_VER)
  #define MyAppVersion APP_VER
#else
  #define MyAppVersion "0.1.0"
#endif


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
WizardStyle=modern

UninstallDisplayIcon={app}\{#MyAppExeName}
DisableDirPage=no
DisableProgramGroupPage=yes


[Files]
; Copia tudo da pasta release (gerada pelo CI ou build local)
Source: "release\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion


[Icons]
Name: "{group}\SekaiTranslatorV"; Filename: "{app}\{#MyAppExeName}"
Name: "{commondesktop}\SekaiTranslatorV"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon


[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; Flags: unchecked


[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Executar SekaiTranslatorV"; Flags: nowait postinstall skipifsilent

#ifndef MyAppVersion
  #define MyAppVersion "0.2.0-preview"
#endif

#define MyAppName "Field Tech Copilot"
#define MyAppExeName "FieldTechCopilot.exe"
#define MyModelName "Qwen3-1.7B-Q8_0.gguf"

[Setup]
AppId={{42E17A50-0C04-47CB-94C5-A580BE43A969}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=Field Tech Copilot
AppPublisherURL=https://github.com/ben4mn/field-tech-copilot
AppSupportURL=https://github.com/ben4mn/field-tech-copilot/issues
AppUpdatesURL=https://github.com/ben4mn/field-tech-copilot/releases
DefaultDirName={localappdata}\Programs\FieldTechCopilot
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19045
OutputDir=..\..\dist\installer
OutputBaseFilename=FieldTechCopilot-FieldKit-Lite-{#MyAppVersion}-Windows-x64-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
AppMutex=FieldTechCopilotDesktop-8D4D48B8-9518-4BA1-A44B-2243D7D97E63
UninstallDisplayIcon={app}\{#MyAppExeName}
InfoAfterFile=..\..\THIRD_PARTY_NOTICES.md

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\..\dist\FieldTechCopilot\*"; DestDir: "{app}"; Excludes: "models\*"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\dist\FieldTechCopilot\models\{#MyModelName}"; DestDir: "{app}\models"; Flags: ignoreversion nocompression

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

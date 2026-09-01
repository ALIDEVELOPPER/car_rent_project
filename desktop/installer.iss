; Script Inno Setup : construit un installateur Windows classique (raccourcis,
; entrée de désinstallation) à partir du build PyInstaller déjà produit dans
; desktop/dist/AgenceLocation/. Compiler avec : iscc desktop/installer.iss
; (depuis la racine du dépôt, ou avec le chemin absolu du .iss).
;
; Installation par utilisateur (pas besoin des droits admin) : cohérent avec
; le fait que les données (base, uploads, clé secrète) vivent déjà dans
; %APPDATA%\AgenceLocation, géré par backend/app/paths.py.

#define AppName "Krilia"
#define AppExeName "AgenceLocation.exe"
#define AppVersion "1.0.0"
#define AppPublisher "Krilia"
#define SourceDir "dist\AgenceLocation"

[Setup]
AppId={{8F1B7C9A-6E1D-4C3A-9B2E-3A1D2F4E5C6B}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=KriliaSetup
SetupIconFile=..\frontend\assets\logo\icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExeName}

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis supplémentaires :"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Désinstaller {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Lancer {#AppName}"; Flags: nowait postinstall skipifsilent

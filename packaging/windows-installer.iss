; The Windows installer of the full build (D-070), compiled by Inno Setup 6 in
; the release workflow:
;
;   ISCC /DAppVersion=0.6.3 /DSourceDir=<onedir folder> /DOutputDir=out
;        /DOutputBase=transcript-normalizer-0.6.3-windows-full-setup
;        packaging\windows-installer.iss
;
; Per-user by default, so no administrator is needed; the first page offers
; "install for all users" instead. The "choose install location" page is shown.
; The uninstaller removes the program folder and nothing else: the user's
; files (runs/, packs/, the Settings folder) are not in it, and are kept.

#ifndef AppVersion
  #error Pass /DAppVersion=<version>
#endif
#ifndef SourceDir
  #error Pass /DSourceDir=<the onedir folder>
#endif
#ifndef OutputDir
  #define OutputDir "out"
#endif
#ifndef OutputBase
  #define OutputBase "transcript-normalizer-" + AppVersion + "-windows-full-setup"
#endif

#define AppName "transcript-normalizer"
#define AppExe "transcript-normalizer.exe"

[Setup]
; The same id in every version, so a new version installs over the old one.
AppId={{2DD75E0D-6338-4495-A611-3BCA9103FFB8}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=transcript-normalizer
AppPublisherURL=https://github.com/Tatiwel/transcript-normalizer
AppSupportURL=https://github.com/Tatiwel/transcript-normalizer/issues
; {autopf} is %LOCALAPPDATA%\Programs for one user, Program Files for all.
DefaultDirName={autopf}\{#AppName}
DisableDirPage=no
UsePreviousAppDir=yes
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBase}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#AppName} {#AppVersion}
UninstallDisplayIcon={app}\{#AppExe}
CloseApplications=yes

[Messages]
; The uninstaller's last words: what it did not remove.
UninstalledAll=%1 was removed from your computer.%n%nYour files were kept: runs/ and packs/ (in Documents\transcript-normalizer, or the folder you chose in Settings) and the Settings folder. Delete them yourself if you no longer want them.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; A new version replaces the program folder: the old version's libraries go.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Only what the installer put there, and the folder itself once it is empty.
Type: dirifempty; Name: "{app}"

; Inno Setup script — builds spickFolio-Setup.exe (graphical installer, no terminal).
; Compile: ISCC.exe installer\windows\spickfolio.iss

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

[Setup]
AppId={{A7B3C9D1-4E2F-5A6B-8C9D-0E1F2A3B4C5D}
AppName=spickFolio
AppVersion={#MyAppVersion}
AppPublisher=Karim-Termanini
AppPublisherURL=https://github.com/Karim-Termanini/spickfolio
AppSupportURL=https://github.com/Karim-Termanini/spickfolio/issues
AppUpdatesURL=https://github.com/Karim-Termanini/spickfolio/releases
DefaultDirName={autopf}\spickFolio
DefaultGroupName=spickFolio
DisableProgramGroupPage=yes
OutputDir=..\..\dist
OutputBaseFilename=spickFolio-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
SetupIconFile=spickfolio.ico
UninstallDisplayIcon={app}\spickFolio.exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\spickFolio.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\spickFolio"; Filename: "{app}\spickFolio.exe"; Comment: "Statistics cheat sheet and dataset browser"
Name: "{autodesktop}\spickFolio"; Filename: "{app}\spickFolio.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\spickFolio.exe"; Description: "{cm:LaunchProgram,spickFolio}"; Flags: nowait postinstall skipifsilent

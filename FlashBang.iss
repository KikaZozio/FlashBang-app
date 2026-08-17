; Script Inno Setup : transforme dist\FlashBang\ (produit par
; build_installateur.bat, mode --onedir) en un vrai installateur Windows avec
; assistant graphique (aucune ligne de commande necessaire, ni pour toi ni
; pour la personne qui installe).
;
; Pour compiler ce script, il faut Inno Setup (gratuit) :
; https://jrsoftware.org/isdl.php -- installe-le une fois, puis
; build_installateur.bat s'en sert automatiquement a chaque construction.

#define MyAppName "Flash Bang"
; Lu depuis la variable d'environnement FLASHBANG_VERSION, positionnee par
; build_installateur.bat a partir de src\version.py (SOURCE UNIQUE DE
; VERITE) - evite d'avoir a recopier le numero de version a la main a deux
; endroits differents (et donc d'oublier de le faire quelque part). Si la
; variable est absente (compilation manuelle du .iss sans passer par le
; script), on retombe sur "0.0.0-dev" pour que ce soit visible que quelque
; chose ne s'est pas passe comme prevu.
#define MyAppVersion GetEnv("FLASHBANG_VERSION")
#if MyAppVersion == ""
  #define MyAppVersion "0.0.0-dev"
#endif
#define MyAppExeName "FlashBang.exe"

[Setup]
AppId={{6F1B2C6E-6B0B-4B7A-9C7E-1A2B3C4D5E6F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Flash Bang
; IMPORTANT : {localappdata} (et non {autopf}) - {autopf} resout vers
; "Program Files" si l'installateur tourne en administrateur, mais vers
; AppData\Local\Programs sinon -> DEUX emplacements differents possibles
; selon si Windows/l'antivirus demande une elevation ce jour-la. Comme les
; donnees (sauvegarde.json) vivent A COTE de l'exe installe, un changement
; d'emplacement d'une installation a l'autre les rendrait invisibles a l'app
; (pas supprimees, juste "ailleurs") - exactement le genre de probleme deja
; rencontre. {localappdata} est TOUJOURS le meme chemin, peu importe les
; droits d'execution de l'installateur -> un seul emplacement, stable, sans
; avoir besoin d'etre administrateur non plus.
DefaultDirName={localappdata}\FlashBang
DefaultGroupName=Flash Bang
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer_output
OutputBaseFilename=FlashBang_Installateur
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=icone_FlashBang.ico
WizardStyle=modern
; Mise a jour propre : Windows detecte tout seul (via Restart Manager) si
; FlashBang.exe est encore ouvert au moment d'installer par-dessus une
; version existante, et propose de le fermer avant de continuer -> plus de
; "vieux fichier verrouille" laisse en place silencieusement (c'est ce qui
; a empeche la nouvelle icone d'apparaitre la derniere fois).
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis supplémentaires :"

[Files]
; Tout le contenu de dist\FlashBang\ (l'exe + les bibliotheques dont il a
; besoin, produits par PyInstaller en mode --onedir). Ce dossier ne contient
; JAMAIS "data" (flashcards, images, fichier de sauvegarde) : ce sous-dossier
; n'existe pas au moment de la construction, l'app le cree elle-meme au
; premier lancement, a cote de l'exe installe. L'installateur ne peut donc
; pas y toucher, ni a l'installation ni a la mise a jour ni a la
; desinstallation. Ne JAMAIS ajouter une ligne "Source: data\*" ici.
Source: "dist\FlashBang\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Flash Bang"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Désinstaller Flash Bang"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Flash Bang"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Lancer Flash Bang maintenant"; Flags: nowait postinstall skipifsilent

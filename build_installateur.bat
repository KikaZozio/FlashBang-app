@echo off
setlocal enabledelayedexpansion

echo ================================================================
echo   Construction de l'INSTALLATEUR Flash Bang (FlashBang_Installateur.exe)
echo ================================================================
echo.
echo Ce script fait tout en une fois : construit l'application PUIS
echo l'emballe dans un installateur avec assistant graphique (raccourcis,
echo desinstalleur...), que tes amis pourront installer sans jamais ouvrir
echo d'invite de commande.
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installe ou pas dans le PATH.
    echo Installe Python depuis https://python.org ^(coche "Add python.exe to PATH"^) puis reessaie.
    if not defined CI pause
    exit /b 1
)

rem Si l'ancienne version de l'app tourne encore, PyInstaller ne peut pas
rem ecraser dist\FlashBang.exe (fichier verrouille) et la construction
rem continue quand meme sans forcement le signaler clairement -> c'est ce
rem qui a empeche la nouvelle icone d'apparaitre la derniere fois. On le
rem verifie donc tout de suite, avant meme de commencer.
tasklist /fi "imagename eq FlashBang.exe" 2>nul | find /i "FlashBang.exe" >nul
if not errorlevel 1 (
    echo [ERREUR] Flash Bang est actuellement ouvert. Ferme l'application
    echo d'abord, sinon la nouvelle version ne pourra pas remplacer l'ancienne.
    if not defined CI pause
    exit /b 1
)
tasklist /fi "imagename eq FlashBang_Installateur.exe" 2>nul | find /i "FlashBang_Installateur.exe" >nul
if not errorlevel 1 (
    echo [ERREUR] Une fenetre de l'installateur Flash Bang est encore ouverte.
    echo Ferme-la d'abord, puis relance ce script.
    if not defined CI pause
    exit /b 1
)

echo [1/4] Installation des dependances...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 (
    echo [ERREUR] L'installation des dependances a echoue.
    if not defined CI pause
    exit /b 1
)

echo.
echo [2/4] Nettoyage des anciennes constructions...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist FlashBang.spec del FlashBang.spec

rem Le fichier .exe de l'installateur precedent est souvent verrouille
rem quelques secondes par l'antivirus (Windows Defender scanne tout nouvel
rem .exe automatiquement) meme si rien ne l'a "ouvert" a proprement parler.
rem On reessaie donc plusieurs fois avant de conclure a un vrai blocage.
set TENTATIVES=0
:nettoyage_installer_output
if exist installer_output rmdir /s /q installer_output >nul 2>nul
if not exist installer_output goto nettoyage_ok
set /a TENTATIVES+=1
if !TENTATIVES! LSS 6 (
    echo   ^(dossier "installer_output" verrouille, nouvel essai dans 3 secondes...^)
    ping -n 4 127.0.0.1 >nul
    goto nettoyage_installer_output
)

echo.
echo [ERREUR] Impossible de nettoyer le dossier "installer_output" : un
echo fichier a l'interieur reste verrouille. Causes les plus frequentes :
echo  - FlashBang.exe ou FlashBang_Installateur.exe encore ouvert quelque
echo    part ^(verifie le Gestionnaire des taches^)
echo  - une fenetre de l'explorateur Windows ouverte sur ce dossier
echo  - l'antivirus qui scanne encore le fichier ^(reessaie dans une minute^)
echo  - si le projet est dans un dossier synchronise par OneDrive : mets la
echo    synchronisation en pause le temps de la construction
echo Ferme tout ca, puis relance ce script.
if not defined CI pause
exit /b 1

:nettoyage_ok

echo.
echo [3/4] Construction de l'executable (patiente, ca peut prendre quelques minutes)...
rem --onedir (et non --onefile) : --onefile doit se re-extraire entierement
rem dans un dossier temporaire A CHAQUE lancement, ce qui rend l'app lente a
rem demarrer en permanence (pas juste la premiere fois). --onedir cree un
rem dossier avec l'exe + ses dependances, lance directement sans extraction
rem repetee -> demarrage rapide a chaque fois. L'installateur emballe ce
rem dossier entier, donc rien ne change pour la personne qui installe.
rem --add-data embarque katex.min.js/css + les polices (assets\katex) : c'est
rem ce qui permet le vrai rendu KaTeX (QWebEngineView) sans connexion
rem internet. PyInstaller detecte tout seul l'import de QtWebEngineWidgets
rem dans le code et embarque le moteur web complet (processus, ressources,
rem traductions) grace a son hook officiel PyQt6-WebEngine.
python -m PyInstaller --noconfirm --onedir --windowed --name FlashBang --collect-data matplotlib ^
    --exclude-module PyQt5 --exclude-module PySide2 --exclude-module PySide6 ^
    --add-data "src\assets\katex;assets\katex" ^
    --icon icone_FlashBang.ico ^
    src\main.py
if not exist dist\FlashBang\FlashBang.exe (
    echo [ERREUR] L'executable n'a pas ete cree. Regarde les messages ci-dessus.
    if not defined CI pause
    exit /b 1
)

echo.
echo [4/4] Fabrication de l'installateur avec Inno Setup...

rem Recupere le numero de version depuis src\version.py (source unique de
rem verite) et le transmet a Inno Setup via une variable d'environnement -
rem voir FlashBang.iss. Ainsi, un seul endroit a modifier avant de publier
rem une nouvelle version.
for /f "delims=" %%V in ('python -c "import sys; sys.path.insert(0, 'src'); import version; print(version.VERSION)"') do set FLASHBANG_VERSION=%%V
if not defined FLASHBANG_VERSION (
    echo [ERREUR] Impossible de lire le numero de version depuis src\version.py.
    if not defined CI pause
    exit /b 1
)
echo  Version detectee : %FLASHBANG_VERSION%

set ISCC=
where ISCC.exe >nul 2>nul
if not errorlevel 1 set ISCC=ISCC.exe

rem Inno Setup propose 2 modes d'installation qui changent son emplacement :
rem "pour tout le monde" (Program Files) ou "juste pour moi" (AppData) ; son
rem numero de version change aussi le nom du dossier ("Inno Setup 6",
rem "Inno Setup 7"...) -> on cherche avec un joker (*) dans les 3 emplacements
rem possibles plutot que de viser un numero de version precis.
if not defined ISCC (
    for /d %%D in ("%ProgramFiles(x86)%\Inno Setup*") do if exist "%%D\ISCC.exe" set ISCC="%%D\ISCC.exe"
)
if not defined ISCC (
    for /d %%D in ("%ProgramFiles%\Inno Setup*") do if exist "%%D\ISCC.exe" set ISCC="%%D\ISCC.exe"
)
if not defined ISCC (
    for /d %%D in ("%LocalAppData%\Programs\Inno Setup*") do if exist "%%D\ISCC.exe" set ISCC="%%D\ISCC.exe"
)

if not defined ISCC (
    echo.
    echo ================================================================
    echo  Inno Setup reste introuvable, meme apres avoir cherche aux
    echo  emplacements habituels. Deux options :
    echo.
    echo  1^) Verifie que tu as bien installe "Inno Setup 6" ^(pas juste
    echo     telecharge^) depuis https://jrsoftware.org/isdl.php
    echo.
    echo  2^) Si tu sais ou "ISCC.exe" se trouve sur ton PC ^(cherche
    echo     "ISCC.exe" dans l'explorateur Windows^), dis-le a Claude pour
    echo     qu'il ajoute le bon chemin dans build_installateur.bat.
    echo ================================================================
    if not defined CI pause
    exit /b 1
)

echo  Inno Setup trouve : %ISCC%

%ISCC% FlashBang.iss
if errorlevel 1 (
    echo [ERREUR] La fabrication de l'installateur a echoue. Regarde les messages ci-dessus.
    if not defined CI pause
    exit /b 1
)

echo.
if exist installer_output\FlashBang_Installateur.exe (
    echo ================================================================
    echo  Termine ! Ton installateur est ici :
    echo  installer_output\FlashBang_Installateur.exe
    echo.
    echo  Envoie CE fichier a tes amis : ils double-cliquent dessus, suivent
    echo  l'assistant ^(Suivant, Suivant, Installer^), et Flash Bang se
    echo  retrouve dans leur menu Demarrer ^(et sur le Bureau si coche^),
    echo  avec un vrai desinstalleur. Aucune invite de commande necessaire.
    echo ================================================================
) else (
    echo [ERREUR] L'installateur n'a pas ete cree. Regarde les messages ci-dessus.
)

if not defined CI pause

@echo off
setlocal

echo ===============================================
echo   Construction de Flash Bang en executable (.exe)
echo ===============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installe ou pas dans le PATH.
    echo Installe Python depuis https://python.org (coche "Add python.exe to PATH"^) puis reessaie.
    pause
    exit /b 1
)

rem Si l'ancienne version de l'app tourne encore, PyInstaller ne peut pas
rem ecraser dist\FlashBang.exe (fichier verrouille) sans forcement le
rem signaler clairement -> on le verifie tout de suite.
tasklist /fi "imagename eq FlashBang.exe" 2>nul | find /i "FlashBang.exe" >nul
if not errorlevel 1 (
    echo [ERREUR] Flash Bang est actuellement ouvert. Ferme l'application
    echo d'abord, sinon la nouvelle version ne pourra pas remplacer l'ancienne.
    pause
    exit /b 1
)

echo [1/3] Installation des dependances...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 (
    echo [ERREUR] L'installation des dependances a echoue.
    pause
    exit /b 1
)

echo.
echo [2/3] Nettoyage des anciennes constructions...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist FlashBang.spec del FlashBang.spec

echo.
echo [3/3] Construction de l'executable (patiente, ca peut prendre quelques minutes)...
rem --onedir (et non --onefile) : --onefile doit se re-extraire entierement
rem dans un dossier temporaire A CHAQUE lancement, ce qui rend l'app lente a
rem demarrer en permanence (pas juste la premiere fois). --onedir demarre
rem directement, sans extraction repetee.
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

echo.
if exist dist\FlashBang\FlashBang.exe (
    echo ===============================================
    echo  Termine ! Ton application est ici :
    echo  dist\FlashBang\
    echo.
    echo  C'est maintenant un DOSSIER ^(pas un seul fichier^) : compresse-le
    echo  en .zip avant de l'envoyer a tes amis. Ils n'ont rien a installer :
    echo  ils decompressent le .zip et double-cliquent sur FlashBang.exe a
    echo  l'interieur ^(en gardant tous les fichiers du dossier ensemble^).
    echo ===============================================
) else (
    echo [ERREUR] L'executable n'a pas ete cree. Regarde les messages ci-dessus.
)

pause

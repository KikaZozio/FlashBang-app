#!/usr/bin/env bash
# Construit Flash Bang en app macOS (.app) puis en .dmg pret a distribuer.
# A LANCER SUR UN MAC (impossible depuis Windows/Linux).
set -e

echo "==============================================="
echo "  Construction de Flash Bang en .dmg (macOS)"
echo "==============================================="
echo

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERREUR] python3 n'est pas installe."
    echo "Installe-le depuis https://python.org (ou via Homebrew : brew install python3) puis reessaie."
    exit 1
fi

# Si l'ancienne version de l'app tourne encore, on ne peut pas ecraser le
# bundle .app proprement.
if pgrep -f "dist/FlashBang.app/Contents/MacOS/FlashBang" >/dev/null 2>&1; then
    echo "[ERREUR] Flash Bang est actuellement ouvert. Ferme l'application"
    echo "d'abord, sinon la nouvelle version ne pourra pas remplacer l'ancienne."
    exit 1
fi

echo "[1/6] Preparation de l'environnement Python (venv_macos)..."
# un venv isole evite les erreurs "externally-managed-environment" que pip
# peut renvoyer sur les installations Python recentes.
if [ ! -d venv_macos ]; then
    python3 -m venv venv_macos
fi
# shellcheck disable=SC1091
source venv_macos/bin/activate

echo
echo "[2/6] Installation des dependances..."
pip install --upgrade pip -q
pip install -r requirements.txt pyinstaller -q

echo
echo "[3/6] Nettoyage des anciennes constructions..."
rm -rf build dist FlashBang.spec dmg_source installateur_macos icone.iconset icone_FlashBang.icns

echo
echo "[4/6] Fabrication de l'icone macOS (.icns) a partir de icone_FlashBang.png..."
mkdir -p icone.iconset
sips -z 16 16     icone_FlashBang.png --out icone.iconset/icon_16x16.png     >/dev/null
sips -z 32 32     icone_FlashBang.png --out icone.iconset/icon_16x16@2x.png >/dev/null
sips -z 32 32     icone_FlashBang.png --out icone.iconset/icon_32x32.png     >/dev/null
sips -z 64 64     icone_FlashBang.png --out icone.iconset/icon_32x32@2x.png >/dev/null
sips -z 128 128   icone_FlashBang.png --out icone.iconset/icon_128x128.png   >/dev/null
sips -z 256 256   icone_FlashBang.png --out icone.iconset/icon_128x128@2x.png >/dev/null
sips -z 256 256   icone_FlashBang.png --out icone.iconset/icon_256x256.png   >/dev/null
sips -z 512 512   icone_FlashBang.png --out icone.iconset/icon_256x256@2x.png >/dev/null
sips -z 512 512   icone_FlashBang.png --out icone.iconset/icon_512x512.png   >/dev/null
sips -z 1024 1024 icone_FlashBang.png --out icone.iconset/icon_512x512@2x.png >/dev/null
iconutil -c icns icone.iconset -o icone_FlashBang.icns

echo
echo "[5/6] Construction de l'app (patiente, ca peut prendre quelques minutes)..."
# Pas de --onedir/--onefile ici : --windowed sur macOS produit directement un
# vrai bundle .app (equivalent macOS du --onedir Windows/Linux : demarre
# directement, pas de re-extraction a chaque lancement).
# --add-data embarque katex.min.js/css + les polices (assets/katex) : c'est
# ce qui permet le vrai rendu KaTeX (QWebEngineView) sans connexion internet.
pyinstaller --noconfirm --windowed --name FlashBang --collect-data matplotlib \
    --exclude-module PyQt5 --exclude-module PySide2 --exclude-module PySide6 \
    --add-data "src/assets/katex:assets/katex" \
    --icon icone_FlashBang.icns \
    src/main.py

if [ ! -d "dist/FlashBang.app" ]; then
    echo "[ERREUR] L'app n'a pas ete creee. Regarde les messages ci-dessus."
    exit 1
fi

echo
echo "[6/6] Fabrication du .dmg..."
# Nom du fichier final : FlashBang_macOS_1.1.0.dmg (meme numero de version
# que src/version.py, source unique de verite - voir aussi FlashBang.iss)
VERSION=$(python3 -c "import sys; sys.path.insert(0, 'src'); import version; print(version.VERSION)")
NOM_DMG="FlashBang_macOS_${VERSION}.dmg"
mkdir -p dmg_source installateur_macos
cp -r "dist/FlashBang.app" dmg_source/
ln -s /Applications dmg_source/Applications
hdiutil create -volname "Flash Bang" -srcfolder dmg_source -ov -format UDZO "installateur_macos/${NOM_DMG}"

deactivate

echo
if [ -f "installateur_macos/${NOM_DMG}" ]; then
    echo "==============================================="
    echo " Termine ! Ton .dmg est ici :"
    echo " installateur_macos/${NOM_DMG}"
    echo
    echo " Envoie ce SEUL fichier a tes amis sous macOS. Ils double-cliquent"
    echo " dessus puis glissent FlashBang.app dans le dossier Applications."
    echo
    echo " Au premier lancement, macOS affichera un avertissement ('app non"
    echo " identifiee' ou 'endommagee') car l'app n'est pas signee numeriquement"
    echo " (signature Apple payante, pas necessaire entre amis). Il faut alors :"
    echo " clic droit sur FlashBang.app -> Ouvrir -> confirmer 'Ouvrir quand"
    echo " meme' (au lieu d'un double-clic classique), une seule fois."
    echo "==============================================="
else
    echo "[ERREUR] La fabrication du .dmg a echoue. Regarde les messages ci-dessus."
    exit 1
fi

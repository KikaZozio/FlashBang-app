#!/usr/bin/env bash
# Construit Flash Bang en AppImage (Linux) : un seul fichier executable qui
# fonctionne sur (quasiment) toutes les distributions, sans installation ni
# droits admin - un peu comme le portable Windows mais universel et en un
# seul fichier.
set -e

echo "==============================================="
echo "  Construction de Flash Bang en AppImage (Linux)"
echo "==============================================="
echo

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERREUR] python3 n'est pas installe."
    echo "Installe-le via ton gestionnaire de paquets (ex: sudo apt install python3 python3-venv python3-pip) puis reessaie."
    exit 1
fi

# Si l'ancienne version de l'app tourne encore, on ne peut pas ecraser
# dist/FlashBang/FlashBang (fichier verrouille par le noyau) proprement.
if pgrep -f "dist/FlashBang/FlashBang" >/dev/null 2>&1; then
    echo "[ERREUR] Flash Bang est actuellement ouvert. Ferme l'application"
    echo "d'abord, sinon la nouvelle version ne pourra pas remplacer l'ancienne."
    exit 1
fi

echo "[1/6] Preparation de l'environnement Python (venv_linux)..."
# un venv isole evite les erreurs "externally-managed-environment" que pip
# renvoie sur les distributions recentes (Ubuntu 23+, Debian 12+, etc.)
if [ ! -d venv_linux ]; then
    python3 -m venv venv_linux
fi
# shellcheck disable=SC1091
source venv_linux/bin/activate

echo
echo "[2/6] Installation des dependances..."
pip install --upgrade pip -q
pip install -r requirements.txt pyinstaller -q

echo
echo "[3/6] Nettoyage des anciennes constructions..."
rm -rf build dist FlashBang.spec AppDir installateur_linux

echo
echo "[4/6] Verification de la police d'emoji embarquee..."
# Contrairement a Windows (Segoe UI Emoji preinstallee), une distribution
# Linux fraiche n'a souvent AUCUNE police d'emoji -> les boutons de l'app
# (🔀, 📤, ✓...) s'afficheraient comme des cases vides. On embarque donc
# Noto Color Emoji directement dans l'AppImage (telechargee une seule fois,
# mise en cache dans src/assets/fonts/ pour les prochaines fois) : plus
# personne n'a besoin d'installer quoi que ce soit chez lui.
POLICE_EMOJI="src/assets/fonts/NotoColorEmoji.ttf"
if [ ! -f "$POLICE_EMOJI" ]; then
    echo "Telechargement de Noto Color Emoji (une seule fois, ~10 Mo)..."
    mkdir -p src/assets/fonts
    if ! curl -L -o "$POLICE_EMOJI" "https://raw.githubusercontent.com/googlefonts/noto-emoji/main/fonts/NotoColorEmoji.ttf"; then
        echo "[ATTENTION] Le telechargement de la police d'emoji a echoue (verifie ta connexion"
        echo "internet). L'AppImage sera quand meme construite, mais sans police d'emoji"
        echo "embarquee : sur une distribution sans police d'emoji installee, les boutons"
        echo "afficheront des cases vides a la place des emojis."
        rm -f "$POLICE_EMOJI"
    fi
fi

echo
echo "[5/6] Construction de l'executable (patiente, ca peut prendre quelques minutes)..."
# --onedir (et non --onefile) : meme raison que sur Windows, --onefile doit
# se re-extraire entierement dans un dossier temporaire A CHAQUE lancement.
# assets/katex (katex.min.js/css + polices) est toujours embarque : c'est ce
# qui permet le vrai rendu KaTeX (QWebEngineView) sans connexion internet.
# ATTENTION (limite connue, pas corrigee ici) : QtWebEngine (moteur Chromium)
# s'appuie sur des bibliotheques systeme deja presentes sur la plupart des
# distributions de bureau modernes (libnss3, libasound2, libXcomposite...)
# mais absentes de certaines distributions minimalistes/serveurs -> si un
# ami a un ecran blanc/noir a la place d'une flashcard contenant une formule,
# c'est probablement ca (l'app entiere reste utilisable, seul le rendu KaTeX
# serait affecte grace au repli automatique sur l'ancien rendu mathtext).
ARGS_DONNEES_EXTRA=(--add-data "src/assets/katex:assets/katex")
if [ -f "$POLICE_EMOJI" ]; then
    ARGS_DONNEES_EXTRA+=(--add-data "${POLICE_EMOJI}:assets/fonts")
fi
pyinstaller --noconfirm --onedir --windowed --name FlashBang --collect-data matplotlib \
    --exclude-module PyQt5 --exclude-module PySide2 --exclude-module PySide6 \
    "${ARGS_DONNEES_EXTRA[@]}" \
    src/main.py

if [ ! -f dist/FlashBang/FlashBang ]; then
    echo "[ERREUR] L'executable n'a pas ete cree. Regarde les messages ci-dessus."
    exit 1
fi

echo
echo "[6/6] Fabrication de l'AppImage..."

# Structure attendue par appimagetool : un AppDir avec le contenu de l'app,
# un .desktop, une icone au meme nom que "Icon=" dans le .desktop, et un
# AppRun executable qui lance le bon binaire.
mkdir -p AppDir/usr/bin
cp -r dist/FlashBang/* AppDir/usr/bin/
cp icone_FlashBang.png AppDir/flashbang.png

cat > AppDir/flashbang.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=Flash Bang
Comment=Application de flashcards et repetition espacee
Exec=FlashBang
Icon=flashbang
Categories=Education;
Terminal=false
EOF

cat > AppDir/AppRun << 'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
exec "${HERE}/usr/bin/FlashBang" "$@"
EOF
chmod +x AppDir/AppRun

# appimagetool est lui-meme distribue en AppImage : on le telecharge une
# seule fois (mis en cache a cote de ce script pour les prochaines fois).
APPIMAGETOOL="./appimagetool-x86_64.AppImage"
if [ ! -f "$APPIMAGETOOL" ]; then
    echo "Telechargement d'appimagetool (une seule fois, ~10 Mo)..."
    if ! curl -L -o "$APPIMAGETOOL" "https://github.com/AppImage/appimagetool/releases/latest/download/appimagetool-x86_64.AppImage"; then
        echo "[ERREUR] Le telechargement d'appimagetool a echoue (verifie ta connexion internet)."
        exit 1
    fi
    chmod +x "$APPIMAGETOOL"
fi

mkdir -p installateur_linux
# --appimage-extract-and-run : evite d'avoir besoin de FUSE installe sur la
# machine qui construit l'app (certaines machines/serveurs ne l'ont pas) ;
# l'AppImage produite, elle, n'a pas besoin de FUSE pour etre CONSTRUITE,
# seulement potentiellement pour etre EXECUTEE plus tard (et la plupart des
# distributions recentes savent s'en passer aussi, voir le message final).
ARCH=x86_64 "$APPIMAGETOOL" --appimage-extract-and-run AppDir installateur_linux/FlashBang-x86_64.AppImage

deactivate

echo
if [ -f installateur_linux/FlashBang-x86_64.AppImage ]; then
    chmod +x installateur_linux/FlashBang-x86_64.AppImage
    echo "==============================================="
    echo " Termine ! Ton AppImage est ici :"
    echo " installateur_linux/FlashBang-x86_64.AppImage"
    echo
    echo " Envoie ce SEUL fichier a tes amis sous Linux. Ils doivent juste le"
    echo " rendre executable (clic droit -> Proprietes -> Autorisations ->"
    echo " 'Autoriser l'execution du fichier comme un programme', ou en ligne"
    echo " de commande : chmod +x FlashBang-x86_64.AppImage) puis double-cliquer"
    echo " dessus. Rien a installer, pas besoin des droits admin."
    echo "==============================================="
else
    echo "[ERREUR] La fabrication de l'AppImage a echoue. Regarde les messages ci-dessus."
    exit 1
fi

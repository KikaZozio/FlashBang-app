import sys
from pathlib import Path

from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import QApplication

import lists
from ui import styles
from ui.main_window import MainWindow


def _charger_police_emoji_secours():
    """Charge, si presente, une police d'emoji embarquee dans l'app
    (assets/fonts/NotoColorEmoji.ttf) et l'ajoute en secours a la police
    globale (voir styles.FONT_FAMILL_SYSTEME).

    Sur Windows/macOS, le systeme a deja une police d'emoji (Segoe UI Emoji /
    Apple Color Emoji) : cette police n'est embarquee QUE dans le build Linux
    (voir build_appimage.sh), donc ce fichier est absent des autres builds -
    dans ce cas on ne fait rien, la police systeme suffit.
    """
    if getattr(sys, "frozen", False):
        # PyInstaller (onedir) : sys._MEIPASS pointe vers le dossier de
        # ressources embarquees, stable (pas re-extrait a chaque lancement)
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    else:
        base = Path(__file__).resolve().parent

    chemin_police = base / "assets" / "fonts" / "NotoColorEmoji.ttf"
    if not chemin_police.exists():
        return

    id_police = QFontDatabase.addApplicationFont(str(chemin_police))
    familles = QFontDatabase.applicationFontFamilies(id_police)
    if familles:
        styles.FONT_FAMILY = f"{styles.FONT_FAMILL_SYSTEME}, {familles[0]}, sans-serif"


def main():
    lists.charger()

    app = QApplication(sys.argv)
    _charger_police_emoji_secours()
    fenetre = MainWindow()
    fenetre.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

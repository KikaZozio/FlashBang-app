"""
Palette et feuille de style globale : fond doux (pas de blanc pur), bordures
fines et discretes, accents de couleur doux, cartes arrondies avec une legere
ombre plutot que des bordures dures.

Gere aussi le mode sombre : les constantes de couleur ci-dessous (BG_MAIN,
TEXT_PRIMARY, etc.) sont volontairement des variables de MODULE mutables.
Les autres fichiers font `from ui import styles` puis lisent `styles.BG_MAIN`
etc. a chaque utilisation (pas d'import direct de la valeur) : quand
`definir_theme()` reassigne ces variables, tous les widgets qui se redessinent
ensuite recuperent automatiquement les nouvelles couleurs.
"""

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QGraphicsDropShadowEffect

# FONT_FAMILL_SYSTEME : la police "normale" du texte. FONT_FAMILY (utilisee
# dans la feuille de style globale) en derive - separee ainsi pour que main.py
# puisse y inserer une police d'emoji de secours (embarquee dans l'app, voir
# _charger_police_emoji_secours) SANS toucher a la police de texte normale.
# Necessaire sur Linux : contrairement a Windows (Segoe UI Emoji preinstallee),
# une distribution fraiche n'a souvent aucune police d'emoji -> les boutons
# afficheraient des cases vides sans cette police de secours.
FONT_FAMILL_SYSTEME = "Segoe UI, -apple-system"
FONT_FAMILY = f"{FONT_FAMILL_SYSTEME}, sans-serif"

# ---------------------------------------------------------------------------
# Palettes
# ---------------------------------------------------------------------------

PALETTE_CLAIR = {
    "bg_main": "#F7F6F3",       # pas de blanc pur : moins agressif pour les yeux
    "bg_sidebar": "#F0EFEC",
    "bg_card": "#FFFFFF",
    "bg_card_hover": "#ECEBE7",
    "bg_input": "#EDECE8",
    "border": "#E3E1DC",
    "border_strong": "#D4D2CC",
    "text_primary": "#37352F",
    "text_secondary": "#8B8A85",
    "text_on_accent": "#FFFFFF",
    "accent": "#6C5CE7",
    "accent_hover": "#5B4BD6",
    "accent_soft": "#EAE5FB",
    "succes": "#2E9E5B",
    "succes_soft": "#DDF3E4",
    "echec": "#C7453A",
    "echec_soft": "#F8E1DE",
    "badges": [
        ("#F1E4D6", "#96550B"),
        ("#DCE9F5", "#1B5E9E"),
        ("#DCEEE0", "#1F7A44"),
        ("#EEE1F5", "#7A369E"),
        ("#F5DEE0", "#A3323F"),
        ("#F5EBD1", "#94720B"),
    ],
}

PALETTE_SOMBRE = {
    "bg_main": "#1E1F22",
    "bg_sidebar": "#191A1C",
    "bg_card": "#26272B",
    "bg_card_hover": "#2E2F34",
    "bg_input": "#2B2C30",
    "border": "#34353A",
    "border_strong": "#41424A",
    "text_primary": "#E4E3DF",
    "text_secondary": "#9A9A96",
    "text_on_accent": "#FFFFFF",
    "accent": "#8B7CF6",
    "accent_hover": "#9D8FF7",
    "accent_soft": "#332D57",
    "succes": "#4CBE7C",
    "succes_soft": "#1E3A2A",
    "echec": "#E17364",
    "echec_soft": "#402522",
    "badges": [
        ("#43331F", "#E0A85C"),
        ("#1E3547", "#7CB4E6"),
        ("#1F3A28", "#7ED19B"),
        ("#372A44", "#C99CE8"),
        ("#402226", "#E39098"),
        ("#3E3520", "#E0C25C"),
    ],
}

mode_actuel = "clair"


def _appliquer(palette):
    global BG_MAIN, BG_SIDEBAR, BG_CARD, BG_CARD_HOVER, BG_INPUT
    global BORDER, BORDER_STRONG
    global TEXT_PRIMARY, TEXT_SECONDARY, TEXT_ON_ACCENT
    global ACCENT, ACCENT_HOVER, ACCENT_SOFT
    global SUCCES, SUCCES_SOFT, ECHEC, ECHEC_SOFT, BADGES

    BG_MAIN = palette["bg_main"]
    BG_SIDEBAR = palette["bg_sidebar"]
    BG_CARD = palette["bg_card"]
    BG_CARD_HOVER = palette["bg_card_hover"]
    BG_INPUT = palette["bg_input"]
    BORDER = palette["border"]
    BORDER_STRONG = palette["border_strong"]
    TEXT_PRIMARY = palette["text_primary"]
    TEXT_SECONDARY = palette["text_secondary"]
    TEXT_ON_ACCENT = palette["text_on_accent"]
    ACCENT = palette["accent"]
    ACCENT_HOVER = palette["accent_hover"]
    ACCENT_SOFT = palette["accent_soft"]
    SUCCES = palette["succes"]
    SUCCES_SOFT = palette["succes_soft"]
    ECHEC = palette["echec"]
    ECHEC_SOFT = palette["echec_soft"]
    BADGES = palette["badges"]


def definir_theme(mode):
    """mode : "clair" ou "sombre". Reassigne la palette et renvoie la nouvelle QSS."""
    global mode_actuel
    mode_actuel = mode
    _appliquer(PALETTE_SOMBRE if mode == "sombre" else PALETTE_CLAIR)
    return generer_qss()


def basculer_theme():
    return definir_theme("sombre" if mode_actuel == "clair" else "clair")


_appliquer(PALETTE_CLAIR)  # theme par defaut au chargement du module


def badge_pour(nom, liste_noms):
    """Renvoie (couleur_fond, couleur_texte) stable pour un nom donne, selon sa
    position dans une liste de reference (ex. la liste des matieres)."""
    if nom in liste_noms:
        index = liste_noms.index(nom) % len(BADGES)
    else:
        index = hash(nom) % len(BADGES)
    return BADGES[index]


def ombre_carte(rayon=18, decalage_y=4, opacite=45):
    effet = QGraphicsDropShadowEffect()
    effet.setBlurRadius(rayon)
    effet.setOffset(0, decalage_y)
    couleur = QColor(0, 0, 0)
    couleur.setAlpha(opacite)
    effet.setColor(couleur)
    return effet


def generer_qss():
    return f"""
* {{
    font-family: {FONT_FAMILY};
    color: {TEXT_PRIMARY};
}}

QMainWindow, QWidget#page, QDialog {{
    background-color: {BG_MAIN};
}}

QWidget#sidebar {{
    background-color: {BG_SIDEBAR};
    border-right: 1px solid {BORDER};
}}

QLabel#titre_app {{
    font-size: 17px;
    font-weight: 600;
}}

QLabel#titre_page {{
    font-size: 26px;
    font-weight: 700;
}}

QLabel#sous_titre {{
    font-size: 13px;
    color: {TEXT_SECONDARY};
}}

QLabel#section_sidebar {{
    font-size: 11px;
    font-weight: 600;
    color: {TEXT_SECONDARY};
    letter-spacing: 1px;
    padding: 6px 14px 2px 14px;
}}

QPushButton#lien_sidebar {{
    text-align: left;
    padding: 7px 14px;
    border-radius: 6px;
    border: none;
    background: transparent;
    font-size: 13px;
}}
QPushButton#lien_sidebar:hover {{
    background-color: {BG_CARD_HOVER};
}}

QPushButton#bouton_icone {{
    background-color: {BG_MAIN};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    padding: 0px;
    font-size: 13px;
}}
QPushButton#bouton_icone:hover {{
    background-color: {ACCENT_SOFT};
    color: {ACCENT};
    border-color: {ACCENT};
}}

QPushButton#lien_sidebar:checked {{
    background-color: {ACCENT_SOFT};
    color: {ACCENT};
    font-weight: 600;
}}

QFrame#carte {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#carte:hover {{
    background-color: {BG_CARD_HOVER};
}}

QFrame#carte_revision {{
    background-color: {BG_CARD};
    border: 2px solid {ACCENT};
    border-radius: 16px;
}}

QWidget#cellule_jour {{
    background-color: {BG_CARD};
}}
QWidget#cellule_jour:hover {{
    background-color: {BG_CARD_HOVER};
}}

QPushButton#bouton_accent {{
    background-color: {ACCENT};
    color: {TEXT_ON_ACCENT};
    border: none;
    border-radius: 8px;
    padding: 9px 18px;
    font-weight: 600;
    font-size: 13px;
}}
QPushButton#bouton_accent:hover {{
    background-color: {ACCENT_HOVER};
}}

QPushButton#bouton_secondaire {{
    background-color: {BG_MAIN};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_STRONG};
    border-radius: 8px;
    padding: 9px 18px;
    font-size: 13px;
}}
QPushButton#bouton_secondaire:hover {{
    background-color: {BG_CARD_HOVER};
}}

QPushButton#bouton_succes {{
    background-color: {SUCCES_SOFT};
    color: {SUCCES};
    border: none;
    border-radius: 8px;
    padding: 10px 22px;
    font-weight: 600;
}}
QPushButton#bouton_succes:hover {{
    background-color: {SUCCES};
    color: white;
}}

QPushButton#bouton_echec {{
    background-color: {ECHEC_SOFT};
    color: {ECHEC};
    border: none;
    border-radius: 8px;
    padding: 10px 22px;
    font-weight: 600;
}}
QPushButton#bouton_echec:hover {{
    background-color: {ECHEC};
    color: white;
}}

QLineEdit, QTextEdit, QComboBox {{
    background-color: {BG_INPUT};
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 7px 10px;
    font-size: 13px;
}}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border: 1px solid {ACCENT};
    background-color: {BG_CARD};
}}

QScrollArea {{
    border: none;
    background: transparent;
}}

QToolTip {{
    background-color: {TEXT_PRIMARY};
    color: {BG_MAIN};
    border: none;
    padding: 4px 8px;
    border-radius: 4px;
}}
"""

"""
Widget de rendu d'un cote de flashcard : une liste de blocs {"type": "texte" |
"katex" | "image", "contenu": ...} affiches ensemble.

Un bloc "texte" peut contenir des formules INLINE, ecrites entre $...$ (ex.
"la formule du glucose est $C_6H_{12}O_6$") : chaque formule est rendue en
image et inseree au fil du texte, comme en Markdown. Le type "katex"
separe existe encore pour compatibilite avec d'anciennes flashcards.

Rendu 100% natif Qt (QLabel/QPixmap), PAS de QWebEngineView : apres plusieurs
bugs recurrents et difficiles a corriger avec QWebEngineView (contenu qui
n'apparaissait qu'apres redimensionnement, contenu de l'affichage precedent
qui restait visible un instant), on a abandonne le rendu web pour un rendu Qt
pur et synchrone, qui ne souffre d'aucun de ces problemes de timing/repaint.

Les formules sont rendues via matplotlib (mathtext), qui gere un sous-ensemble
de LaTeX suffisant pour des formules simples (indices, exposants, fractions,
lettres grecques...). Ce n'est pas un moteur KaTeX complet, mais ca fonctionne
pour l'usage vise et reste 100% local/hors-ligne. Les images generees sont
mises en cache sur disque (evite de re-render la meme formule a chaque fois).
"""

import hashlib
import html as html_echappement
import io
import re

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel

import lists
from ui import styles

try:
    import matplotlib
    matplotlib.rcParams["savefig.transparent"] = True  # sinon math_to_image() produit un fond blanc opaque
    from matplotlib import mathtext
    from matplotlib.font_manager import FontProperties
    from PIL import Image, ImageColor, ImageDraw
    _MATHTEXT_DISPONIBLE = True
except ImportError:
    _MATHTEXT_DISPONIBLE = False

MOTIF_FORMULE_INLINE = re.compile(r"\$([^$]+)\$")

# Commandes ou mathtext (contrairement a un vrai moteur LaTeX/KaTeX) EXIGE des
# accolades autour de chaque argument, meme s'il tient en un seul caractere.
# Verifie a la main contre mathtext (matplotlib) : \frac/\dfrac/\tfrac/\binom
# prennent 2 arguments obligatoires, \sqrt (apres un eventuel indice [n]) et
# \overline en prennent 1. Les commandes d'accent a un argument (\hat, \vec,
# \bar, \dot, \ddot, \tilde, \breve, \grave, \acute, \widehat, \widetilde,
# \overrightarrow...) acceptent deja un argument bare sans probleme dans
# mathtext, elles n'ont donc pas besoin d'etre reparees ici.
MOTIF_COMMANDE_DEUX_ARGS = re.compile(r"\\(?:d|t)?frac|\\binom|\\overset|\\underset")
MOTIF_COMMANDE_UN_ARG = re.compile(r"\\overline")
MOTIF_COMMANDE_RACINE = re.compile(r"\\sqrt")
MOTIF_INDICE_RACINE = re.compile(r"\[[^\[\]]*\]")

# \stackrel{dessus}{dessous} n'existe pas dans mathtext, mais \overset (memes
# arguments, dans le meme ordre) fait exactement la meme chose et LUI est
# supporte -> simple synonyme, pas besoin de le re-implementer.
#
# \displaystyle/\textstyle/\scriptstyle/\scriptscriptstyle et \limits/
# \nolimits n'existent pas non plus dans mathtext : contrairement aux
# commandes ci-dessus, ce ne sont pas des symboles a afficher mais de purs
# "interrupteurs" de mise en forme (agrandir \sum, placer les indices en
# dessous plutot qu'a cote...) qui n'ont pas d'equivalent ici. mathtext rend
# deja les grands operateurs (\sum, \int, \lim...) dans un style proche du
# "displaystyle" par defaut, donc le resultat le plus proche qu'on puisse
# obtenir est simplement de les IGNORER plutot que de faire planter tout le
# rendu -> c'est tres frequent dans une formule copiee depuis KaTeX/ChatGPT/
# un manuel, sans que la personne s'en rende forcement compte.
MOTIF_COMMANDES_IGNOREES = re.compile(
    # pas "\b" : "_" (tres frequent juste apres \limits, ex. \sum\limits_{i})
    # est un caractere de mot pour Python et casserait la frontiere -> on
    # verifie explicitement qu'on n'est pas au milieu d'un nom de commande
    # plus long (une commande TeX ne contient que des lettres)
    r"\\(?:displaystyle|textstyle|scriptscriptstyle|scriptstyle|limits|nolimits)(?![a-zA-Z])\s*"
)


def _convertir_alias(formule):
    formule = formule.replace(r"\stackrel", r"\overset")
    formule = MOTIF_COMMANDES_IGNOREES.sub("", formule)
    return formule


# \underline et les environnements matrix/pmatrix/bmatrix/vmatrix/Vmatrix/
# cases n'existent pas DU TOUT dans mathtext (contrairement a \overline ou
# \binom, ce n'est pas juste une histoire d'accolades manquantes). On les
# intercepte donc AVANT de passer quoi que ce soit a mathtext, et on les
# construit nous-memes en composant plusieurs images (une par cellule /
# morceau de texte) avec Pillow.
MOTIF_ENV_MATRICE = re.compile(r"\\begin\{(matrix|pmatrix|bmatrix|vmatrix|Vmatrix|cases)\}")

# (delimiteur de gauche, delimiteur de droite) pour chaque environnement,
# exprimes comme des symboles mathtext valides (voir _rendre_glyphe_dimensionne)
DELIMITEURS_ENV = {
    "matrix": (None, None),
    "pmatrix": ("(", ")"),
    "bmatrix": ("[", "]"),
    "vmatrix": ("|", "|"),
    "Vmatrix": (r"\|", r"\|"),
    "cases": (r"\{", None),
}


def _lire_argument_tex(texte, i):
    """Lit UN argument TeX a partir de l'indice i (apres avoir saute les
    espaces) : soit un groupe {...} (avec accolades imbriquees), soit un seul
    token (une commande \\nom ou un unique caractere). Renvoie (argument,
    indice_juste_apres). C'est ce raccourci ("un seul caractere = un argument
    valide sans accolades") qu'un vrai moteur LaTeX/KaTeX accepte nativement
    pour \\frac, mais que mathtext (le sous-ensemble utilise ici) ne comprend
    pas -> d'ou le besoin de le repérer et d'ajouter les accolades nous-memes
    avant de passer la formule a mathtext."""
    n = len(texte)
    while i < n and texte[i] == " ":
        i += 1
    if i >= n:
        return "", i
    if texte[i] == "{":
        profondeur = 1
        j = i + 1
        while j < n and profondeur > 0:
            if texte[j] == "{":
                profondeur += 1
            elif texte[j] == "}":
                profondeur -= 1
            j += 1
        return texte[i + 1:j - 1], j
    if texte[i] == "\\":
        j = i + 1
        while j < n and texte[j].isalpha():
            j += 1
        if j == i + 1 and j < n:
            j += 1  # commande d'un seul caractere non-alpha (ex. \, \%)
        return texte[i:j], j
    return texte[i], i + 1


def _ajouter_accolades_manquantes(formule):
    """Repare les commandes ecrites sans accolades autour d'un argument d'un
    seul caractere (ex. \\frac mV, \\sqrt x, \\overline AB), comme le permet
    du vrai LaTeX/KaTeX, en ajoutant les accolades que mathtext exige pour les
    comprendre (\\frac{m}{V}, \\sqrt{x}, \\overline{AB}). Sans ca, une formule
    tapee "a la KaTeX" echoue silencieusement et s'affiche telle quelle au
    lieu d'etre rendue."""
    resultat = []
    i = 0
    n = len(formule)
    while i < n:
        correspondance = MOTIF_COMMANDE_DEUX_ARGS.match(formule, i)
        if correspondance:
            resultat.append(correspondance.group())
            i = correspondance.end()
            premier, i = _lire_argument_tex(formule, i)
            second, i = _lire_argument_tex(formule, i)
            resultat.append("{" + _ajouter_accolades_manquantes(premier) + "}")
            resultat.append("{" + _ajouter_accolades_manquantes(second) + "}")
            continue

        correspondance = MOTIF_COMMANDE_UN_ARG.match(formule, i)
        if correspondance:
            resultat.append(correspondance.group())
            i = correspondance.end()
            argument, i = _lire_argument_tex(formule, i)
            resultat.append("{" + _ajouter_accolades_manquantes(argument) + "}")
            continue

        correspondance = MOTIF_COMMANDE_RACINE.match(formule, i)
        if correspondance:
            resultat.append(correspondance.group())
            i = correspondance.end()
            # \sqrt[n]{...} : l'indice optionnel entre crochets, s'il est la,
            # est recopie tel quel avant de traiter l'argument obligatoire
            indice = MOTIF_INDICE_RACINE.match(formule, i)
            if indice:
                resultat.append(indice.group())
                i = indice.end()
            argument, i = _lire_argument_tex(formule, i)
            resultat.append("{" + _ajouter_accolades_manquantes(argument) + "}")
            continue

        resultat.append(formule[i])
        i += 1
    return "".join(resultat)


# on reutilise lists.DOSSIER_DATA (et pas un chemin recalcule ici a partir de
# __file__) pour etre sur que ce cache reste au meme endroit que le reste des
# donnees, y compris une fois l'app empaquetee en .exe
CACHE_KATEX = lists.DOSSIER_DATA / "katex_cache"
CACHE_KATEX.mkdir(parents=True, exist_ok=True)


def _couleur_texte_rgba():
    r, g, b = ImageColor.getrgb(styles.TEXT_PRIMARY)
    return (r, g, b, 255)


def _rendre_image_mathtext(texte, taille_police):
    """Rend une expression mathtext PURE (sans \\underline ni environnement
    matrice, mathtext ne les comprend pas) en objet Pillow (fond transparent).
    Renvoie None si le texte est vide ou si le rendu echoue."""
    if not texte.strip():
        return None
    try:
        tampon = io.BytesIO()
        mathtext.math_to_image(
            f"${texte}$", tampon,
            dpi=200,
            prop=FontProperties(size=taille_police),
            color=styles.TEXT_PRIMARY,
            format="png",
        )
        tampon.seek(0)
        return Image.open(tampon).convert("RGBA")
    except Exception:
        return None


def _rendre_glyphe_dimensionne(caractere_mathtext, hauteur_cible_px, taille_police_base):
    """Rend un delimiteur ( ) [ ] | \\| \\{ a une taille choisie pour que sa
    hauteur se rapproche de `hauteur_cible_px` : mathtext ne sait pas "etirer"
    un delimiteur autour d'un contenu de taille arbitraire (pas de \\left/
    \\right autour d'une image composee a la main), donc on simule l'effet en
    re-rendant carrement le caractere a une plus grande taille de police."""
    if not caractere_mathtext:
        return None
    image_base = _rendre_image_mathtext(caractere_mathtext, taille_police_base)
    if image_base is None or image_base.height == 0:
        return image_base
    echelle = hauteur_cible_px / image_base.height
    taille_ajustee = max(6, min(400, round(taille_police_base * echelle)))
    return _rendre_image_mathtext(caractere_mathtext, taille_ajustee) or image_base


def _parser_grille_matrice(contenu):
    """Coupe le contenu d'un \\begin{...}...\\end{...} en une grille de
    cellules brutes (pas encore rendues) : les lignes sont separees par \\\\,
    les colonnes par &."""
    grille = []
    for ligne_brute in re.split(r"\\\\", contenu):
        ligne_brute = ligne_brute.strip()
        if not ligne_brute:
            continue
        grille.append([cellule.strip() for cellule in ligne_brute.split("&")])
    return grille


def _rendre_image_matrice(nom_env, contenu, taille_police):
    """Rend un environnement matrix/pmatrix/bmatrix/vmatrix/Vmatrix/cases en
    UNE image Pillow : chaque cellule est rendue independamment par mathtext,
    puis on les assemble nous-memes en grille (mathtext n'a pas d'equivalent
    de \\begin{array} ou du & d'alignement), avec les delimiteurs appropries
    "etires" a la hauteur totale de la grille."""
    grille_brute = _parser_grille_matrice(contenu)
    if not grille_brute:
        return None

    grille_images = [
        [_rendre_image_mathtext(cellule, taille_police) for cellule in ligne]
        for ligne in grille_brute
    ]

    nb_colonnes = max(len(ligne) for ligne in grille_images)
    marge_x = round(taille_police * 0.6)
    marge_y = round(taille_police * 0.35)

    largeurs_colonnes = [0] * nb_colonnes
    hauteurs_lignes = [0] * len(grille_images)
    for i, ligne in enumerate(grille_images):
        for j, image in enumerate(ligne):
            if image is not None:
                largeurs_colonnes[j] = max(largeurs_colonnes[j], image.width)
                hauteurs_lignes[i] = max(hauteurs_lignes[i], image.height)

    largeur_grille = sum(largeurs_colonnes) + marge_x * (nb_colonnes + 1)
    hauteur_grille = sum(hauteurs_lignes) + marge_y * (len(grille_images) + 1)
    if largeur_grille <= 0 or hauteur_grille <= 0:
        return None

    gauche, droite = DELIMITEURS_ENV.get(nom_env, (None, None))
    aligner_a_gauche = (nom_env == "cases")  # plus naturel pour une definition par cas

    image_gauche = _rendre_glyphe_dimensionne(gauche, hauteur_grille, taille_police)
    image_droite = _rendre_glyphe_dimensionne(droite, hauteur_grille, taille_police)
    marge_delimiteur = round(taille_police * 0.25)

    largeur_totale = largeur_grille
    if image_gauche:
        largeur_totale += image_gauche.width + marge_delimiteur
    if image_droite:
        largeur_totale += image_droite.width + marge_delimiteur
    hauteur_totale = hauteur_grille

    canevas = Image.new("RGBA", (largeur_totale, hauteur_totale), (0, 0, 0, 0))

    x = 0
    if image_gauche:
        canevas.alpha_composite(image_gauche, (0, (hauteur_totale - image_gauche.height) // 2))
        x += image_gauche.width + marge_delimiteur

    y = marge_y
    for i, ligne in enumerate(grille_images):
        colonne_x = x + marge_x
        for j in range(nb_colonnes):
            largeur_colonne = largeurs_colonnes[j]
            image = ligne[j] if j < len(ligne) else None
            if image is not None:
                decalage_x = 0 if aligner_a_gauche else (largeur_colonne - image.width) // 2
                decalage_y = (hauteurs_lignes[i] - image.height) // 2
                canevas.alpha_composite(image, (colonne_x + decalage_x, y + decalage_y))
            colonne_x += largeur_colonne + marge_x
        y += hauteurs_lignes[i] + marge_y

    if image_droite:
        canevas.alpha_composite(image_droite, (largeur_totale - image_droite.width, (hauteur_totale - image_droite.height) // 2))

    return canevas


def _rendre_image_souligne(argument, taille_police):
    """Rend \\underline{argument} : mathtext ne connait pas \\underline du
    tout (contrairement a \\overline), donc on rend l'interieur normalement
    puis on trace nous-memes un trait sous l'image obtenue."""
    image_interieure = _composer_image_formule(argument, taille_police)
    if image_interieure is None:
        return None
    epaisseur = max(1, round(taille_police * 0.06))
    marge_bas = max(2, round(taille_police * 0.14))
    canevas = Image.new(
        "RGBA",
        (image_interieure.width, image_interieure.height + marge_bas + epaisseur),
        (0, 0, 0, 0),
    )
    canevas.alpha_composite(image_interieure, (0, 0))
    y_trait = image_interieure.height + marge_bas
    ImageDraw.Draw(canevas).line(
        [(0, y_trait), (image_interieure.width, y_trait)],
        fill=_couleur_texte_rgba(), width=epaisseur,
    )
    return canevas


def _decouper_en_segments(formule, taille_police):
    """Coupe `formule` (deja normalisee par _ajouter_accolades_manquantes /
    _convertir_alias) en morceaux ordonnes, et rend chacun en image Pillow :
    du mathtext "normal" separe par les portions \\underline{...} et
    \\begin{env}...\\end{env}, que mathtext ne sait pas rendre lui-meme."""
    images = []
    tampon = []
    i = 0
    n = len(formule)

    def vider_tampon():
        texte = "".join(tampon)
        tampon.clear()
        if texte.strip():
            images.append(_rendre_image_mathtext(texte, taille_police))

    while i < n:
        correspondance_env = MOTIF_ENV_MATRICE.match(formule, i)
        if correspondance_env:
            nom_env = correspondance_env.group(1)
            fin = formule.find(f"\\end{{{nom_env}}}", correspondance_env.end())
            if fin == -1:
                # pas de \end correspondant trouve : on laisse tel quel, tant
                # pis, plutot que de planter ou de perdre du contenu
                tampon.append(formule[i])
                i += 1
                continue
            vider_tampon()
            contenu = formule[correspondance_env.end():fin]
            images.append(_rendre_image_matrice(nom_env, contenu, taille_police))
            i = fin + len(f"\\end{{{nom_env}}}")
            continue

        if formule.startswith(r"\underline", i):
            argument, j = _lire_argument_tex(formule, i + len(r"\underline"))
            vider_tampon()
            images.append(_rendre_image_souligne(argument, taille_police))
            i = j
            continue

        tampon.append(formule[i])
        i += 1

    vider_tampon()
    return [image for image in images if image is not None]


def _composer_image_formule(formule, taille_police):
    """Rend une formule complete (potentiellement melangeant mathtext normal,
    \\underline et des environnements matrice) en UNE SEULE image Pillow,
    les morceaux colles horizontalement et centres verticalement les uns par
    rapport aux autres."""
    segments = _decouper_en_segments(formule, taille_police)
    if not segments:
        return None
    if len(segments) == 1:
        return segments[0]

    # mathtext recadre chaque morceau pile sur son encre (y compris les
    # espaces en debut/fin, qui disparaissent du cadrage) : sans un petit
    # espace ajoute nous-memes ici, deux morceaux colles bord a bord (ex.
    # autour d'un \underline{...} au milieu d'une phrase) se retrouveraient
    # visuellement accoles l'un a l'autre sans le moindre espace.
    espacement = max(4, round(taille_police * 0.4))
    hauteur_max = max(image.height for image in segments)
    largeur_totale = sum(image.width for image in segments) + espacement * (len(segments) - 1)
    canevas = Image.new("RGBA", (largeur_totale, hauteur_max), (0, 0, 0, 0))
    x = 0
    for indice, image in enumerate(segments):
        if indice > 0:
            x += espacement
        canevas.alpha_composite(image, (x, (hauteur_max - image.height) // 2))
        x += image.width
    return canevas


def _rendre_katex_fichier(formule, taille_police):
    """Rend une formule en PNG (mis en cache sur disque par formule/taille/
    couleur), renvoie le chemin du fichier ou None si le rendu echoue."""
    if not _MATHTEXT_DISPONIBLE or not formule.strip():
        return None

    formule = _ajouter_accolades_manquantes(_convertir_alias(formule))

    cle = hashlib.md5(
        f"{formule}|{taille_police}|{styles.TEXT_PRIMARY}".encode("utf-8")
    ).hexdigest()
    chemin = CACHE_KATEX / f"{cle}.png"

    if chemin.exists():
        return str(chemin)

    try:
        image = _composer_image_formule(formule, taille_police)
        if image is None:
            return None
        image.save(chemin)
        return str(chemin)
    except Exception:
        return None


def _html_depuis_texte(texte, taille_police):
    """Transforme un texte contenant des $formules$ en HTML riche pour QLabel,
    avec chaque formule remplacee par une image inline."""
    morceaux = []
    position = 0

    for correspondance in MOTIF_FORMULE_INLINE.finditer(texte):
        avant = texte[position:correspondance.start()]
        if avant:
            morceaux.append(html_echappement.escape(avant).replace("\n", "<br>"))

        formule = correspondance.group(1)
        chemin_image = _rendre_katex_fichier(formule, taille_police)
        if chemin_image:
            # hauteur forcee : l'image de matplotlib est recadree pile sur
            # l'encre du dessin (sans les marges qu'a une police de texte
            # normale), donc a "hauteur egale" elle parait plus grande qu'une
            # lettre du texte alentour. On vise plutot la hauteur d'une
            # majuscule (~ 0.8 x la taille de police) que la taille de police
            # entiere. Toujours base sur `taille_police` (celle du texte
            # alentour), jamais un plancher independant : sinon une formule au
            # milieu d'une phrase se retrouve disproportionnee par rapport aux
            # lettres qui l'entourent.
            hauteur_cible = round(taille_police * 0.8)
            morceaux.append(
                f'<img src="{chemin_image}" height="{hauteur_cible}" style="vertical-align:middle;">'
            )
        else:
            # repli si le rendu echoue : on montre la formule telle quelle
            morceaux.append(html_echappement.escape(f"${formule}$"))

        position = correspondance.end()

    reste = texte[position:]
    if reste:
        morceaux.append(html_echappement.escape(reste).replace("\n", "<br>"))

    return "".join(morceaux)


class RenduBlocs(QWidget):
    """Affiche une liste de blocs (texte avec $formules$ inline / katex / image)
    d'un cote de flashcard."""

    def __init__(self, parent=None, taille_police=24):
        super().__init__(parent)
        self._taille_police = taille_police
        # necessaire pour que le background-color defini via setStyleSheet
        # soit bien pris en compte sur un QWidget "nu" (sinon Qt l'ignore)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._mise_en_page = QHBoxLayout(self)
        self._mise_en_page.setContentsMargins(16, 16, 16, 16)
        self._mise_en_page.setSpacing(14)
        self._mise_en_page.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def afficher(self, blocs):
        # rendu synchrone : on vide et on reconstruit immediatement, sans
        # aucune attente ni chargement asynchrone
        while self._mise_en_page.count():
            item = self._mise_en_page.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not blocs:
            vide = QLabel("Aucun contenu pour ce côté")
            vide.setStyleSheet(f"color: {styles.TEXT_SECONDARY}; font-style: italic; font-size: 14px;")
            self._mise_en_page.addWidget(vide)
            return

        for bloc in blocs:
            type_bloc = bloc.get("type")
            contenu = bloc.get("contenu", "")
            if not contenu:
                continue

            if type_bloc == "texte":
                self._mise_en_page.addWidget(self._creer_label_texte(contenu))

            elif type_bloc == "katex":
                # ancien format (formule seule, hors texte) : on la traite comme
                # un texte reduit a une seule formule inline, pour reutiliser le
                # meme rendu
                self._mise_en_page.addWidget(self._creer_label_texte(f"${contenu}$"))

            elif type_bloc == "image":
                pixmap = QPixmap(contenu)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(
                        360, 260,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    etiquette = QLabel()
                    etiquette.setPixmap(pixmap)
                    self._mise_en_page.addWidget(etiquette)

    def _creer_label_texte(self, texte):
        etiquette = QLabel()
        etiquette.setWordWrap(True)
        etiquette.setAlignment(Qt.AlignmentFlag.AlignCenter)
        etiquette.setTextFormat(Qt.TextFormat.RichText)
        html_interieur = _html_depuis_texte(texte, self._taille_police)
        etiquette.setText(
            f'<span style="color:{styles.TEXT_PRIMARY}; font-size:{self._taille_police}px;">'
            f"{html_interieur}</span>"
        )
        return etiquette

"""
Widget de rendu d'un cote de flashcard : une liste de blocs {"type": "texte" |
"katex" | "image", "contenu": ...} affiches ensemble.

Un bloc "texte" peut contenir des formules INLINE, ecrites entre $...$ (ex.
"la formule du glucose est $C_6H_{12}O_6$"). Le type "katex" separe existe
encore pour compatibilite avec d'anciennes flashcards (formule seule, hors
texte).

RENDU VIA UN VRAI MOTEUR KATEX (QWebEngineView + katex.min.js/css embarques
dans assets/katex/, 100% local/hors-ligne, aucune connexion internet requise).
Remplace l'ancien rendu 100% natif Qt (mathtext/matplotlib), conserve tel
quel dans bloc_renderer_mathtext.py au cas ou on voudrait revenir en arriere -
voir plus bas le mecanisme de repli automatique si QWebEngineView ou les
fichiers KaTeX embarques sont absents.

Un rendu web avait deja ete tente puis abandonne plus tot dans ce projet a
cause de deux bugs recurrents. Comment ils sont evites cette fois :
  - "le contenu n'apparaissait qu'apres un redimensionnement manuel" : le
    widget se redimensionne tout seul via un ResizeObserver cote JavaScript
    (qui se redeclenche tout seul si une police web charge en retard et fait
    bouger la mise en page), relaye a Python via `document.title` + le signal
    Qt `titleChanged` (aucun sondage/minuterie a la main, aucune supposition
    sur le delai de chargement).
  - "l'ancien contenu restait visible un instant" : le widget est ecrase a
    une taille de 1x1 (donc invisible) DES le debut du chargement d'une
    nouvelle carte, et ne reprend sa vraie taille qu'une fois le nouveau
    contenu reellement mesure -> jamais d'ancien contenu visible pendant la
    transition.
"""

import html as html_echappement
import json
import re
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel

from ui import styles

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    _WEBENGINE_DISPONIBLE = True
except ImportError:
    _WEBENGINE_DISPONIBLE = False

MOTIF_FORMULE_INLINE = re.compile(r"\$([^$]+)\$")
MOTIF_TITRE_TAILLE = re.compile(r"^(\d+)x(\d+)$")


def _chemin_assets_katex():
    """Dossier contenant katex.min.js/css + les polices (assets/katex/),
    aussi bien en mode developpement qu'une fois empaquete en .exe/.app/
    AppImage par PyInstaller (meme logique que la police d'emoji de
    secours dans main.py)."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    else:
        base = Path(__file__).resolve().parent.parent  # src/ui/.. -> src/
    return base / "assets" / "katex"


_ASSETS_KATEX = _chemin_assets_katex()
_KATEX_UTILISABLE = _WEBENGINE_DISPONIBLE and (_ASSETS_KATEX / "katex.min.js").exists()


def _construire_contenu_html(texte):
    """Transforme un texte contenant des $formules$ en HTML (texte normal
    echappe + un <span id="fbfN"> vide par formule, que le JS de la page
    remplira via katex.render). Renvoie (html, liste_des_formules_brutes)."""
    morceaux = []
    formules = []
    position = 0

    for correspondance in MOTIF_FORMULE_INLINE.finditer(texte):
        avant = texte[position:correspondance.start()]
        if avant:
            morceaux.append(html_echappement.escape(avant).replace("\n", "<br>"))

        indice = len(formules)
        formules.append(correspondance.group(1))
        morceaux.append(f'<span class="fbf" id="fbf{indice}"></span>')

        position = correspondance.end()

    reste = texte[position:]
    if reste:
        morceaux.append(html_echappement.escape(reste).replace("\n", "<br>"))

    return "".join(morceaux), formules


LARGEUR_MAX_VISUALISEUR = 640


def _construire_page_html(texte, taille_police, couleur_texte):
    contenu_html, formules = _construire_contenu_html(texte)
    formules_json = json.dumps(formules)
    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<link rel="stylesheet" href="katex.min.css">
<script src="katex.min.js"></script>
<style>
  html, body {{
    margin: 0; padding: 0; background: transparent; overflow: hidden;
  }}
  #fbcontenu {{
    display: inline-block;
    max-width: {LARGEUR_MAX_VISUALISEUR}px;
    color: {couleur_texte};
    font-size: {taille_police}px;
    font-family: "Segoe UI", -apple-system, sans-serif;
    text-align: center;
    white-space: normal;
    padding: 2px;
  }}
  .fbf-erreur {{ color: #e06c6c; }}
</style>
</head>
<body>
<div id="fbcontenu">{contenu_html}</div>
<script>
  var formules = {formules_json};
  formules.forEach(function (source, indice) {{
    var cible = document.getElementById("fbf" + indice);
    if (!cible) return;
    try {{
      katex.render(source, cible, {{ throwOnError: false }});
    }} catch (erreur) {{
      // repli : la formule ne casse jamais l'affichage, elle s'affiche
      // juste telle quelle si KaTeX n'arrive vraiment pas a la comprendre
      cible.textContent = "$" + source + "$";
      cible.className = "fbf-erreur";
    }}
  }});

  var elementContenu = document.getElementById("fbcontenu");
  var minuteurSignal = null;
  function signalerTailleImmediat() {{
    var rect = elementContenu.getBoundingClientRect();
    document.title = Math.ceil(rect.width) + "x" + Math.ceil(rect.height);
  }}
  // ATTENTION taille "amortie" (debounce), pas immediate : les polices KaTeX
  // (une dizaine de fichiers .woff2, une par style/taille de symbole) ne
  // chargent pas toutes d'un coup, chacune fait legerement bouger la mise en
  // page a son tour -> sans amorti, Python recevait une rafale de tailles
  // legerement differentes coup sur coup et redimensionnait le widget a
  // chaque fois, d'ou l'effet de "vibration" pendant 1-2 secondes. On attend
  // ici 150ms sans AUCUN nouveau changement de taille avant de signaler quoi
  // que ce soit a Python : le widget ne bouge donc plus qu'UNE SEULE fois,
  // une fois la mise en page reellement stabilisee.
  function signalerTailleAmortie() {{
    if (minuteurSignal) clearTimeout(minuteurSignal);
    minuteurSignal = setTimeout(signalerTailleImmediat, 150);
  }}
  new ResizeObserver(signalerTailleAmortie).observe(elementContenu);
  // document.fonts.ready : attend que TOUTES les polices utilisees par la
  // page (donc les polices KaTeX) aient fini de charger avant le tout premier
  // signal, pour ne meme pas avoir a attendre un premier amorti a vide.
  if (window.document && document.fonts && document.fonts.ready) {{
    document.fonts.ready.then(signalerTailleAmortie);
  }} else {{
    signalerTailleAmortie();
  }}
</script>
</body>
</html>"""


if _KATEX_UTILISABLE:

    class _VisualiseurKatexWeb(QWebEngineView):
        """Un seul bloc "texte" (avec eventuelles formules $...$ inline),
        rendu par un vrai moteur KaTeX dans une page web chargee en local.
        Se redimensionne tout seul a la taille exacte du contenu (voir le
        docstring du module)."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.page().setBackgroundColor(Qt.GlobalColor.transparent)
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
            # LARGEUR fixee des le debut (et pas 1px) : c'est ce qui evitait
            # la "vibration" observee meme SANS formule KaTeX. En partant a
            # 1x1, la page n'a d'abord que 1px de large pour se mettre en
            # page -> le texte s'y enroule lettre par lettre, on mesure cette
            # forme (haute et etroite), Python agrandit le widget en
            # consequence, ce qui change la largeur reellement disponible, ce
            # qui change a son tour comment le texte s'enroule -> nouvelle
            # mesure differente -> nouveau redimensionnement... et ainsi de
            # suite jusqu'a ce que ca converge, ce qui EST la vibration. En
            # gardant la largeur FIXE des le premier affichage (identique a
            # `max-width` cote CSS), l'enroulement du texte ne depend plus
            # jamais de la taille du widget -> il n'y a plus qu'UN SEUL
            # redimensionnement (la hauteur, une fois mesuree).
            self.setFixedSize(LARGEUR_MAX_VISUALISEUR, 10)
            self.titleChanged.connect(self._sur_titre_change)

        def afficher(self, texte, taille_police):
            # ecrase IMMEDIATEMENT a une hauteur quasi nulle (largeur
            # INCHANGEE, voir __init__) : le widget ne reprendra sa vraie
            # hauteur qu'une fois le NOUVEAU contenu effectivement mesure
            # (voir _sur_titre_change) -> on ne montre jamais l'ancien
            # contenu pendant la transition vers le nouveau.
            self.setFixedSize(LARGEUR_MAX_VISUALISEUR, 10)
            html = _construire_page_html(texte, taille_police, styles.TEXT_PRIMARY)
            base_url = QUrl.fromLocalFile(str(_ASSETS_KATEX) + "/")
            self.setHtml(html, base_url)

        def _sur_titre_change(self, titre):
            correspondance = MOTIF_TITRE_TAILLE.match(titre)
            if not correspondance:
                return  # titre "normal" (ex. l'URL de la page) : on l'ignore
            largeur = int(correspondance.group(1))
            hauteur = int(correspondance.group(2))
            if largeur > 0 and hauteur > 0:
                # petite marge pour ne jamais faire apparaitre de barre de
                # defilement a cause d'un arrondi de sous-pixel
                self.setFixedSize(largeur + 4, hauteur + 4)


    class RenduBlocs(QWidget):
        """Affiche une liste de blocs (texte avec $formules$ inline / katex /
        image) d'un cote de flashcard."""

        def __init__(self, parent=None, taille_police=24):
            super().__init__(parent)
            self._taille_police = taille_police
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

            self._mise_en_page = QHBoxLayout(self)
            self._mise_en_page.setContentsMargins(16, 16, 16, 16)
            self._mise_en_page.setSpacing(14)
            self._mise_en_page.setAlignment(Qt.AlignmentFlag.AlignCenter)

        def afficher(self, blocs):
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
                    self._mise_en_page.addWidget(self._creer_visualiseur(contenu))

                elif type_bloc == "katex":
                    # ancien format (formule seule, hors texte) : traitee
                    # comme un texte reduit a une seule formule inline
                    self._mise_en_page.addWidget(self._creer_visualiseur(f"${contenu}$"))

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

        def _creer_visualiseur(self, texte):
            visualiseur = _VisualiseurKatexWeb(self)
            visualiseur.afficher(texte, self._taille_police)
            return visualiseur

else:
    # QWebEngineView indisponible (module non installe) ou fichiers KaTeX
    # embarques manquants (ex. oubli lors d'un build) : on retombe sans
    # bruit sur l'ancien rendu 100% natif Qt (mathtext), garde tel quel dans
    # bloc_renderer_mathtext.py, plutot que de planter l'app entiere.
    from ui.bloc_renderer_mathtext import RenduBlocs  # noqa: F401

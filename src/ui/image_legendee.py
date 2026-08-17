"""Widget "image a legender" : une image sur laquelle on place des points,
chacun relie par un trait qu'on dessine soi-meme a un champ de texte ou l'on
ecrit la legende. Les deux bouts du trait (la pointe sur l'image ET la
legende) peuvent ensuite etre deplaces librement a la souris.

Deux modes :
- "edition" (utilise dans l'editeur de flashcard) :
    * cliquer-glisser depuis l'image dessine un nouveau trait, du point de
      depart (la pointe, sur l'image) jusqu'au point de relachement (ou la
      legende viendra se placer). Un simple clic (sans glisser) ajoute un
      point avec une legende placee automatiquement juste a cote.
    * on tape directement la bonne legende dans le champ.
    * un glissement sur le petit rond numerote deplace la pointe du trait ;
      un glissement sur la poignee "⠿" a cote du champ deplace la legende.
    * un petit bouton "✕" a cote de chaque champ retire le point.
- "revision" (utilise en session de revision) : les champs sont vides au
  depart (l'utilisateur tape sa reponse), et verifier() compare chaque champ
  a la bonne legende (comparaison insensible a la casse et aux espaces) pour
  determiner automatiquement si la carte est reussie. Rien n'est deplaçable
  dans ce mode.
"""

from PyQt6.QtCore import Qt, QRectF, QPointF, QMarginsF, QTimer
from PyQt6.QtGui import QPixmap, QPen, QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QGraphicsLineItem,
    QGraphicsRectItem, QGraphicsSimpleTextItem, QLineEdit, QPushButton,
    QSizePolicy
)

from ui import styles

LARGEUR_AFFICHAGE_MAX = 460
HAUTEUR_AFFICHAGE_MAX = 380
LARGEUR_CHAMP = 120
LONGUEUR_TRAIT_DEFAUT = 44
TAILLE_POIGNEE = 14

# cles utilisees pour retrouver un item graphique dans mousePressEvent
CLE_MARQUEUR = "marqueur"
CLE_POIGNEE = "poignee"


class CanevasLegende(QGraphicsView):
    def __init__(self, mode="edition", parent=None):
        super().__init__(parent)
        self._mode = mode  # "edition" ou "revision"
        self._chemin_image = None
        # points : [{"x","y" (pointe, relatifs image), "ancre_x","ancre_y"
        #            (legende, relatifs image, peuvent depasser 0-1),
        #            "legende": str}, ...]
        self._points = []
        self._legendes_correctes = []  # utilise seulement en mode revision
        self._pixmap_item = None
        self._largeur_image = 0
        self._hauteur_image = 0
        self._champs = []  # QLineEdit dans le meme ordre que self._points
        # items graphiques par point (memorises pour pouvoir les deplacer
        # directement pendant un glissement, SANS tout redessiner a chaque
        # pixel : detruire/recreer les QLineEdit a chaque mouseMoveEvent est
        # ce qui rendait le glisser-deposer saccade)
        self._elements = []

        self._glissement = None  # None | "creation" | "marqueur" | "poignee"
        self._glissement_index = None
        self._glissement_depart = None
        self._ligne_previsualisation = None

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(self.renderHints())
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setStyleSheet(
            f"QGraphicsView {{ background-color: {styles.BG_CARD}; border: none; }}"
        )
        if self._mode == "edition":
            self.setCursor(Qt.CursorShape.CrossCursor)

    # ------------------------------------------------------------------
    # Chargement
    # ------------------------------------------------------------------

    def charger_image(self, chemin_image):
        """Change l'image de base (mode edition). Reinitialise les points."""
        self._chemin_image = chemin_image
        self._points = []
        self._legendes_correctes = []
        self._redessiner()

    def definir_points(self, points):
        """Pre-remplit les points (mode edition, ex. flashcard existante)."""
        self._points = [self._normaliser_point(p) for p in points]
        self._redessiner()

    def charger_pour_revision(self, chemin_image, points):
        """Prepare le canevas pour une session de revision : l'image est affichee
        avec des marqueurs numerotes, les champs sont vides (a completer)."""
        self._chemin_image = chemin_image
        self._legendes_correctes = [p.get("legende", "") for p in points]
        self._points = [
            {**self._normaliser_point(p), "legende": ""} for p in points
        ]
        self._redessiner()

    @staticmethod
    def _normaliser_point(point):
        """Ajoute ancre_x/ancre_y par defaut si absents (compatibilite avec
        d'anciennes flashcards enregistrees avant l'ajout du glisser-deposer)."""
        point = dict(point)
        if "ancre_x" not in point or "ancre_y" not in point:
            point["ancre_x"] = point["x"] + 0.12
            point["ancre_y"] = point["y"]
        return point

    # ------------------------------------------------------------------
    # Rendu
    # ------------------------------------------------------------------

    def _synchroniser_textes(self):
        """Recopie le texte actuellement tape dans chaque champ vers
        self._points, pour ne rien perdre avant un redessin (ex. pendant un
        glissement d'un AUTRE point, qui redessine tout le canevas)."""
        for point, champ in zip(self._points, self._champs):
            point["legende"] = champ.text()

    def _redessiner(self):
        # NB : pas de synchronisation automatique des textes ici. Elle doit se
        # faire AVANT toute mutation de self._points (ajout/suppression), sinon
        # apres une suppression les index de self._points et self._champs ne
        # correspondent plus et les legendes se melangent entre elles. Chaque
        # appelant qui a besoin de preserver le texte tape appelle donc
        # _synchroniser_textes() lui-meme, au bon moment.
        self._scene.clear()
        self._champs = []
        self._elements = []
        self._ligne_previsualisation = None

        if not self._chemin_image:
            return

        pixmap_original = QPixmap(self._chemin_image)
        if pixmap_original.isNull():
            return

        pixmap = pixmap_original.scaled(
            LARGEUR_AFFICHAGE_MAX, HAUTEUR_AFFICHAGE_MAX,
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )

        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._largeur_image = pixmap.width()
        self._hauteur_image = pixmap.height()

        for index, point in enumerate(self._points):
            point_x = point["x"] * self._largeur_image
            point_y = point["y"] * self._hauteur_image
            ancre_x = point["ancre_x"] * self._largeur_image
            ancre_y = point["ancre_y"] * self._hauteur_image

            element = {}
            element["ligne"] = self._dessiner_trait(point_x, point_y, ancre_x, ancre_y)
            element["cercle"], element["numero"] = self._dessiner_marqueur(index, point_x, point_y)
            element["proxy_champ"] = self._dessiner_champ(index, ancre_x, ancre_y, point["legende"])
            element["poignee"] = None
            element["proxy_suppr"] = None
            if self._mode == "edition":
                element["poignee"] = self._dessiner_poignee(index, ancre_x, ancre_y)
                element["proxy_suppr"] = self._dessiner_bouton_suppr(index, ancre_x, ancre_y)
            self._elements.append(element)

        # la scene englobe toujours l'image + tous les traits/legendes, meme
        # ceux places en dehors de l'image ; le canevas centre ensuite le tout
        self._mettre_a_jour_rect_scene()

    def _mettre_a_jour_rect_scene(self):
        rect = self._scene.itemsBoundingRect()
        if rect.isEmpty():
            rect = QRectF(0, 0, max(self._largeur_image, 10), max(self._hauteur_image, 10))
        self._scene.setSceneRect(rect.marginsAdded(QMarginsF(24, 24, 24, 24)))

    def _dessiner_marqueur(self, index, x, y):
        rayon = 11
        cercle = QGraphicsEllipseItem(x - rayon, y - rayon, rayon * 2, rayon * 2)
        cercle.setBrush(QBrush(QColor(styles.ACCENT)))
        cercle.setPen(QPen(QColor(styles.BG_CARD), 2))
        if self._mode == "edition":
            cercle.setData(0, (CLE_MARQUEUR, index))
            cercle.setCursor(Qt.CursorShape.OpenHandCursor)
            cercle.setToolTip("Glisser pour déplacer la pointe")
        self._scene.addItem(cercle)

        numero = QGraphicsSimpleTextItem(str(index + 1))
        numero.setBrush(QBrush(QColor(styles.TEXT_ON_ACCENT)))
        police = QFont()
        police.setBold(True)
        police.setPointSize(9)
        numero.setFont(police)
        rect_texte = numero.boundingRect()
        numero.setPos(x - rect_texte.width() / 2, y - rect_texte.height() / 2)
        numero.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self._scene.addItem(numero)
        return cercle, numero

    def _dessiner_trait(self, x1, y1, x2, y2):
        ligne = QGraphicsLineItem(x1, y1, x2, y2)
        ligne.setPen(QPen(QColor(styles.ACCENT), 2))
        self._scene.addItem(ligne)
        return ligne

    def _dessiner_champ(self, index, ancre_x, ancre_y, valeur_initiale):
        champ = QLineEdit()
        champ.setFixedWidth(LARGEUR_CHAMP)
        champ.setText(valeur_initiale)
        if self._mode == "revision":
            champ.setPlaceholderText("Ta réponse…")
        proxy = self._scene.addWidget(champ)
        proxy.setPos(ancre_x, ancre_y - 12)
        self._champs.append(champ)
        return proxy

    def _dessiner_bouton_suppr(self, index, ancre_x, ancre_y):
        bouton_suppr = QPushButton("✕")
        bouton_suppr.setFixedSize(20, 20)
        bouton_suppr.setObjectName("bouton_icone")
        bouton_suppr.setCursor(Qt.CursorShape.PointingHandCursor)
        # deplacement en file d'attente (QTimer.singleShot(0, ...)) et pas un
        # appel direct : sinon on detruit le bouton (via scene.clear() dans
        # _redessiner) PENDANT qu'il est encore en train de traiter son propre
        # signal clicked(), ce qui fait planter l'appli (use-after-free Qt).
        bouton_suppr.clicked.connect(lambda: QTimer.singleShot(0, lambda: self._supprimer_point(index)))
        proxy_bouton = self._scene.addWidget(bouton_suppr)
        proxy_bouton.setPos(ancre_x + LARGEUR_CHAMP + 4, ancre_y - 12)
        return proxy_bouton

    def _dessiner_poignee(self, index, ancre_x, ancre_y):
        poignee = QGraphicsRectItem(
            ancre_x - TAILLE_POIGNEE - 4, ancre_y - TAILLE_POIGNEE / 2,
            TAILLE_POIGNEE, TAILLE_POIGNEE
        )
        poignee.setBrush(QBrush(QColor(styles.BORDER_STRONG)))
        poignee.setPen(QPen(QColor(styles.TEXT_SECONDARY), 1))
        poignee.setData(0, (CLE_POIGNEE, index))
        poignee.setCursor(Qt.CursorShape.OpenHandCursor)
        poignee.setToolTip("Glisser pour déplacer la légende")
        self._scene.addItem(poignee)
        return poignee

    # ------------------------------------------------------------------
    # Deplacement direct des items existants (pendant un glissement) : on
    # bouge juste les items concernes au lieu de tout detruire/reconstruire,
    # sinon recreer les QLineEdit a chaque mouseMoveEvent rend le glissement
    # tres saccade.
    # ------------------------------------------------------------------

    def _deplacer_pointe(self, index, x, y):
        element = self._elements[index]
        rayon = 11
        element["cercle"].setRect(x - rayon, y - rayon, rayon * 2, rayon * 2)
        rect_texte = element["numero"].boundingRect()
        element["numero"].setPos(x - rect_texte.width() / 2, y - rect_texte.height() / 2)
        ligne_actuelle = element["ligne"].line()
        element["ligne"].setLine(x, y, ligne_actuelle.x2(), ligne_actuelle.y2())

    def _deplacer_ancre(self, index, x, y):
        element = self._elements[index]
        element["proxy_champ"].setPos(x, y - 12)
        if element["poignee"] is not None:
            element["poignee"].setRect(
                x - TAILLE_POIGNEE - 4, y - TAILLE_POIGNEE / 2, TAILLE_POIGNEE, TAILLE_POIGNEE
            )
        if element["proxy_suppr"] is not None:
            element["proxy_suppr"].setPos(x + LARGEUR_CHAMP + 4, y - 12)
        ligne_actuelle = element["ligne"].line()
        element["ligne"].setLine(ligne_actuelle.x1(), ligne_actuelle.y1(), x, y)

    # ------------------------------------------------------------------
    # Edition : creation par glissement, deplacement, suppression
    # ------------------------------------------------------------------

    def _donnee_item_sous_curseur(self, position_vue):
        """Cherche parmi TOUS les items empiles a cette position (pas juste le
        plus haut) un marqueur ou une poignee : le numero du marqueur (texte)
        est dessine par-dessus le rond et masquerait sinon la detection."""
        items = self.items(position_vue)
        for item in items:
            donnee = item.data(0)
            if isinstance(donnee, tuple) and donnee[0] in (CLE_MARQUEUR, CLE_POIGNEE):
                return donnee[0], donnee[1]
        return None, (items[0] if items else None)

    def mousePressEvent(self, event):
        if self._mode != "edition" or self._pixmap_item is None:
            super().mousePressEvent(event)
            return

        cle, valeur = self._donnee_item_sous_curseur(event.pos())

        if cle == CLE_MARQUEUR:
            self._glissement = "marqueur"
            self._glissement_index = valeur
            event.accept()
            return

        if cle == CLE_POIGNEE:
            self._glissement = "poignee"
            self._glissement_index = valeur
            event.accept()
            return

        position_scene = self.mapToScene(event.pos())
        rect_image = self._pixmap_item.boundingRect()
        item_brut = valeur  # item Qt sous le curseur, si ce n'est ni marqueur ni poignee

        if item_brut is self._pixmap_item and rect_image.contains(position_scene):
            self._glissement = "creation"
            self._glissement_depart = position_scene
            self._ligne_previsualisation = QGraphicsLineItem(
                position_scene.x(), position_scene.y(), position_scene.x(), position_scene.y()
            )
            self._ligne_previsualisation.setPen(
                QPen(QColor(styles.ACCENT), 2, Qt.PenStyle.DashLine)
            )
            self._scene.addItem(self._ligne_previsualisation)
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._glissement is None:
            super().mouseMoveEvent(event)
            return

        position_scene = self.mapToScene(event.pos())

        if self._glissement == "creation" and self._ligne_previsualisation is not None:
            self._ligne_previsualisation.setLine(
                self._glissement_depart.x(), self._glissement_depart.y(),
                position_scene.x(), position_scene.y()
            )
            event.accept()
            return

        if self._glissement in ("marqueur", "poignee") and self._largeur_image:
            index = self._glissement_index
            x_relatif = position_scene.x() / self._largeur_image
            y_relatif = position_scene.y() / self._hauteur_image
            if self._glissement == "marqueur":
                # la pointe reste dans les limites de l'image
                x_relatif = min(max(x_relatif, 0.0), 1.0)
                y_relatif = min(max(y_relatif, 0.0), 1.0)
                self._points[index]["x"] = x_relatif
                self._points[index]["y"] = y_relatif
                self._deplacer_pointe(index, x_relatif * self._largeur_image, y_relatif * self._hauteur_image)
            else:
                # la legende, elle, peut sortir de l'image (a cote, par ex.)
                self._points[index]["ancre_x"] = x_relatif
                self._points[index]["ancre_y"] = y_relatif
                self._deplacer_ancre(index, x_relatif * self._largeur_image, y_relatif * self._hauteur_image)
            self._mettre_a_jour_rect_scene()
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._glissement == "creation":
            position_scene = self.mapToScene(event.pos())
            depart = self._glissement_depart
            distance = ((position_scene.x() - depart.x()) ** 2 + (position_scene.y() - depart.y()) ** 2) ** 0.5

            if self._ligne_previsualisation is not None:
                self._scene.removeItem(self._ligne_previsualisation)
                self._ligne_previsualisation = None

            if self._largeur_image:
                if distance > 6:
                    # glissement reel : la legende va la ou l'utilisateur a relache
                    ancre_x = position_scene.x() / self._largeur_image
                    ancre_y = position_scene.y() / self._hauteur_image
                else:
                    # simple clic : legende placee automatiquement a cote
                    ancre_x = depart.x() / self._largeur_image + 0.12
                    ancre_y = depart.y() / self._hauteur_image

                # les points existants ne bougent pas d'index (on ajoute a la
                # fin) : on peut synchroniser puis ajouter sans rien perdre
                self._synchroniser_textes()
                self._points.append({
                    "x": depart.x() / self._largeur_image,
                    "y": depart.y() / self._hauteur_image,
                    "ancre_x": ancre_x,
                    "ancre_y": ancre_y,
                    "legende": "",
                })
                self._redessiner()
                if self._champs:
                    self._champs[-1].setFocus()

            self._glissement = None
            self._glissement_index = None
            self._glissement_depart = None
            event.accept()
            return

        if self._glissement in ("marqueur", "poignee"):
            self._glissement = None
            self._glissement_index = None
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def _supprimer_point(self, index):
        # synchroniser AVANT de retirer l'element : une fois l'index supprime,
        # self._points et self._champs n'ont plus la meme longueur et on ne
        # peut plus faire correspondre les textes tapes aux bons points
        self._synchroniser_textes()
        del self._points[index]
        self._redessiner()

    def recuperer_points(self):
        """Renvoie les points a jour (mode edition), en recuperant le texte
        actuellement tape dans chaque champ comme legende."""
        self._synchroniser_textes()
        return [dict(p) for p in self._points]

    def a_des_points(self):
        return len(self._points) > 0

    # ------------------------------------------------------------------
    # Revision (verification automatique)
    # ------------------------------------------------------------------

    def verifier(self):
        """Compare chaque champ a la bonne legende (mode revision). Colore les
        champs et les passe en lecture seule. Renvoie True si TOUT est correct."""
        tout_correct = True

        for champ, legende_correcte in zip(self._champs, self._legendes_correctes):
            reponse = champ.text().strip()
            correct = reponse.casefold() == legende_correcte.strip().casefold()
            tout_correct = tout_correct and correct

            champ.setReadOnly(True)
            if correct:
                champ.setStyleSheet(
                    f"background-color: {styles.SUCCES_SOFT}; color: {styles.SUCCES}; "
                    f"border: 1px solid {styles.SUCCES}; border-radius: 4px; padding: 2px 4px;"
                )
            else:
                champ.setText(f"{reponse}  →  {legende_correcte}")
                champ.setStyleSheet(
                    f"background-color: {styles.ECHEC_SOFT}; color: {styles.ECHEC}; "
                    f"border: 1px solid {styles.ECHEC}; border-radius: 4px; padding: 2px 4px;"
                )

        return tout_correct

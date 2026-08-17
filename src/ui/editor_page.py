"""Page d'edition d'une flashcard : mode (question/reponse ou recto/verso) et,
pour chaque cote, une zone de texte libre ou l'on ecrit naturellement, avec
des formules inline entre $...$, plus des images ajoutees a part."""

import os
import tempfile

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QComboBox,
    QFileDialog, QTextEdit, QScrollArea, QMessageBox, QApplication
)

import lists
from ui import styles
from ui.bloc_renderer import RenduBlocs
from ui.image_legendee import CanevasLegende


def _image_du_presse_papier_vers_fichier_local():
    """Si le presse-papiers contient une image, la sauvegarde via
    lists.stocker_image_locale (comme pour une image choisie via un fichier)
    et renvoie son chemin local. Renvoie None si le presse-papiers ne contient
    pas d'image."""
    image = QApplication.clipboard().image()
    if image.isNull():
        return None

    descripteur, chemin_temp = tempfile.mkstemp(suffix=".png")
    os.close(descripteur)
    try:
        image.save(chemin_temp, "PNG")
        return lists.stocker_image_locale(chemin_temp)
    finally:
        os.remove(chemin_temp)

LABELS_MODE = {
    "Question / Réponse (un seul sens)": "one_side",
    "Recto / Verso (dans les deux sens)": "two_sides",
    "Légender une image": "legende_image",
}
LABELS_MODE_INVERSE = {valeur: cle for cle, valeur in LABELS_MODE.items()}


def _aplanir_blocs(blocs):
    """Convertit une liste de blocs (y compris l'ancien format avec plusieurs
    blocs texte/katex separes) en (texte, images) pour peupler l'editeur.
    Une ancienne formule "katex" devient un $...$ insere dans le texte."""
    morceaux_texte = []
    images = []
    for bloc in blocs:
        type_bloc = bloc.get("type")
        contenu = bloc.get("contenu", "")
        if type_bloc == "texte":
            morceaux_texte.append(contenu)
        elif type_bloc == "katex":
            morceaux_texte.append(f"${contenu}$")
        elif type_bloc == "image":
            images.append(contenu)
    return " ".join(morceaux_texte), images


def _blocs_depuis(texte, images):
    blocs = []
    if texte.strip():
        blocs.append({"type": "texte", "contenu": texte})
    for chemin in images:
        blocs.append({"type": "image", "contenu": chemin})
    return blocs


class MiniatureImage(QFrame):
    """Petite vignette d'une image ajoutee, avec un bouton pour la retirer."""

    def __init__(self, chemin, on_supprimer):
        super().__init__()
        self.setObjectName("carte")
        mise_en_page = QVBoxLayout(self)
        mise_en_page.setContentsMargins(4, 4, 4, 4)
        mise_en_page.setSpacing(2)

        image = QLabel()
        pixmap = QPixmap(chemin)
        if not pixmap.isNull():
            pixmap = pixmap.scaled(
                64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            image.setPixmap(pixmap)
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mise_en_page.addWidget(image)

        bouton_suppr = QPushButton("✕ retirer")
        bouton_suppr.setObjectName("bouton_icone")
        bouton_suppr.setCursor(Qt.CursorShape.PointingHandCursor)
        # IMPORTANT : ne jamais connecter on_supprimer directement au signal
        # clicked. QPushButton.clicked envoie un booleen "checked" en argument
        # positionnel qui, sinon, ecraserait silencieusement le "chemin"
        # deja capture par defaut dans on_supprimer (c'est exactement le bug
        # qui causait un crash ValueError ici : chemin devenait False).
        bouton_suppr.clicked.connect(lambda checked=False: on_supprimer())
        mise_en_page.addWidget(bouton_suppr)


class EditeurCote(QWidget):
    """Gere la composition libre d'un seul cote : texte + $formules$ inline +
    images, avec apercu en direct."""

    def __init__(self, titre):
        super().__init__()
        self.images = []

        mise_en_page = QVBoxLayout(self)
        mise_en_page.setSpacing(8)

        etiquette_titre = QLabel(titre)
        etiquette_titre.setStyleSheet("font-weight: 600; font-size: 14px;")
        mise_en_page.addWidget(etiquette_titre)

        # taille_police relevee (16 -> 20) pour que l'apercu reste lisible,
        # y compris les formules $...$ : comme le rendu d'une formule est
        # toujours proportionnel a taille_police (voir bloc_renderer), monter
        # cette valeur agrandit texte ET formules ENSEMBLE, sans jamais rendre
        # une formule disproportionnee par rapport au texte autour d'elle.
        self._apercu = RenduBlocs(taille_police=20)
        self._apercu.setFixedHeight(140)
        self._apercu.setStyleSheet(f"border: 1px solid {styles.BORDER}; border-radius: 10px;")
        mise_en_page.addWidget(self._apercu)

        self._zone_texte = QTextEdit()
        self._zone_texte.setPlaceholderText(
            "Écris librement ici.\n"
            "Pour une formule au milieu d'une phrase, entoure-la de $ : "
            "par exemple $C_6H_{12}O_6$."
        )
        self._zone_texte.setFixedHeight(120)
        self._zone_texte.textChanged.connect(self._redessiner)
        mise_en_page.addWidget(self._zone_texte)

        self._ligne_images = QHBoxLayout()
        self._ligne_images.setSpacing(6)
        mise_en_page.addLayout(self._ligne_images)

        ligne_boutons_image = QHBoxLayout()
        bouton_image = QPushButton("➕ 🖼  Ajouter une image")
        bouton_image.setObjectName("bouton_secondaire")
        bouton_image.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_image.clicked.connect(self._ajouter_image)
        ligne_boutons_image.addWidget(bouton_image)

        bouton_coller = QPushButton("📋  Coller l'image du presse-papier")
        bouton_coller.setObjectName("bouton_secondaire")
        bouton_coller.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_coller.setToolTip("Colle une image copiée ailleurs (Ctrl+C sur une image, un extrait d'écran...)")
        bouton_coller.clicked.connect(self._coller_image)
        ligne_boutons_image.addWidget(bouton_coller)

        ligne_boutons_image.addStretch()
        mise_en_page.addLayout(ligne_boutons_image)

        mise_en_page.addStretch()

    @property
    def blocs(self):
        return _blocs_depuis(self._zone_texte.toPlainText(), self.images)

    def definir_blocs(self, blocs):
        texte, images = _aplanir_blocs(blocs)
        self._zone_texte.blockSignals(True)
        self._zone_texte.setPlainText(texte)
        self._zone_texte.blockSignals(False)
        self.images = images
        self._redessiner_miniatures()
        self._redessiner()

    def _ajouter_image(self):
        chemin, _ = QFileDialog.getOpenFileName(
            self, "Choisir une image", "", "Images (*.png *.jpg *.jpeg *.gif *.webp)"
        )
        if chemin:
            # copie l'image dans data/images/ : la flashcard ne depend plus du
            # fichier d'origine (qui pourrait etre deplace/supprime), et reste
            # exportable telle quelle si on la partage plus tard
            self.images.append(lists.stocker_image_locale(chemin))
            self._redessiner_miniatures()
            self._redessiner()

    def _coller_image(self):
        chemin_local = _image_du_presse_papier_vers_fichier_local()
        if chemin_local is None:
            QMessageBox.information(
                self, "Presse-papiers vide",
                "Il n'y a pas d'image dans le presse-papiers pour l'instant. "
                "Copie une image (Ctrl+C, ou un outil de capture d'écran) puis réessaie."
            )
            return
        self.images.append(chemin_local)
        self._redessiner_miniatures()
        self._redessiner()

    def _supprimer_image(self, chemin):
        self.images.remove(chemin)
        self._redessiner_miniatures()
        self._redessiner()

    def _redessiner_miniatures(self):
        while self._ligne_images.count():
            item = self._ligne_images.takeAt(0)
            widget = item.widget()
            if widget:
                # setParent(None) detache immediatement le widget (deleteLater
                # seul ne le detruit qu'au prochain passage dans la boucle
                # d'evenements, ce qui pouvait laisser une vignette fantome
                # brievement cliquable apres un ajout/suppression rapide)
                widget.setParent(None)
                widget.deleteLater()

        for chemin in self.images:
            miniature = MiniatureImage(chemin, on_supprimer=lambda c=chemin: self._supprimer_image(c))
            self._ligne_images.addWidget(miniature)
        self._ligne_images.addStretch()

    def _redessiner(self):
        self._apercu.afficher(self.blocs)

    def focus_texte(self):
        self._zone_texte.setFocus()


class EditeurImageLegendee(QWidget):
    """Gere l'edition du mode "légender une image" : choix de l'image, puis
    clic sur l'image pour placer des points relies a un champ de legende."""

    def __init__(self):
        super().__init__()
        mise_en_page = QVBoxLayout(self)
        mise_en_page.setSpacing(8)

        instructions = QLabel(
            "Choisis une image, puis clique-glisse depuis l'endroit à légender "
            "jusqu'à où tu veux poser la légende (un simple clic la place "
            "automatiquement à côté). Tape directement la bonne réponse dans "
            "le champ. Glisse le rond numéroté pour déplacer la pointe, ou la "
            "poignée « ⠿ » pour déplacer la légende. Clique sur ✕ pour retirer un point."
        )
        instructions.setWordWrap(True)
        instructions.setObjectName("sous_titre")
        mise_en_page.addWidget(instructions)

        ligne_boutons_image = QHBoxLayout()
        bouton_image = QPushButton("🖼  Choisir une image")
        bouton_image.setObjectName("bouton_secondaire")
        bouton_image.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_image.clicked.connect(self._choisir_image)
        ligne_boutons_image.addWidget(bouton_image)

        bouton_coller = QPushButton("📋  Coller l'image du presse-papier")
        bouton_coller.setObjectName("bouton_secondaire")
        bouton_coller.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_coller.setToolTip("Colle une image copiée ailleurs (Ctrl+C sur une image, un extrait d'écran...)")
        bouton_coller.clicked.connect(self._coller_image)
        ligne_boutons_image.addWidget(bouton_coller)

        ligne_boutons_image.addStretch()
        mise_en_page.addLayout(ligne_boutons_image)

        self._canevas = CanevasLegende(mode="edition")
        self._canevas.setMinimumHeight(420)
        mise_en_page.addWidget(self._canevas, stretch=1)

    def _choisir_image(self):
        chemin, _ = QFileDialog.getOpenFileName(
            self, "Choisir une image", "", "Images (*.png *.jpg *.jpeg *.gif *.webp)"
        )
        if chemin:
            self._canevas.charger_image(lists.stocker_image_locale(chemin))

    def _coller_image(self):
        chemin_local = _image_du_presse_papier_vers_fichier_local()
        if chemin_local is None:
            QMessageBox.information(
                self, "Presse-papiers vide",
                "Il n'y a pas d'image dans le presse-papiers pour l'instant. "
                "Copie une image (Ctrl+C, ou un outil de capture d'écran) puis réessaie."
            )
            return
        self._canevas.charger_image(chemin_local)

    def definir_bloc(self, blocs):
        """blocs : la liste renvoyee par lists.flashcards[id][0], attendue de
        la forme [{"type": "image_legendee", "chemin": ..., "points": [...]}]."""
        if blocs and blocs[0].get("type") == "image_legendee":
            bloc = blocs[0]
            self._canevas.charger_image(bloc["chemin"])
            self._canevas.definir_points(bloc["points"])

    def chemin_image(self):
        return self._canevas._chemin_image

    def points(self):
        return self._canevas.recuperer_points()

    def est_valide(self):
        return bool(self._canevas._chemin_image) and self._canevas.a_des_points()


class BlocFlashcard(QFrame):
    """Un bloc d'edition complet (mode + cote 1/2 + legende) pour UNE
    flashcard. La page d'edition en empile plusieurs les uns sous les autres
    quand on cree plusieurs cartes a la suite, chacun restant modifiable
    independamment avec les memes outils que l'edition normale."""

    def __init__(self, flashcard_id, on_retirer):
        super().__init__()
        self.flashcard_id = flashcard_id
        self.setObjectName("carte")

        mise_en_page = QVBoxLayout(self)
        mise_en_page.setSpacing(12)
        mise_en_page.setContentsMargins(16, 14, 16, 16)

        entete = QHBoxLayout()
        self._label_numero = QLabel()
        self._label_numero.setStyleSheet("font-weight: 700; font-size: 15px;")
        entete.addWidget(self._label_numero, stretch=1)

        entete.addWidget(QLabel("Mode :"))
        self._combo_mode = QComboBox()
        self._combo_mode.addItems(list(LABELS_MODE.keys()))
        self._combo_mode.currentTextChanged.connect(self._sur_changement_mode)
        entete.addWidget(self._combo_mode)

        bouton_retirer = QPushButton("🗑️  Retirer cette carte")
        bouton_retirer.setObjectName("bouton_echec")
        bouton_retirer.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_retirer.clicked.connect(lambda checked=False: on_retirer(self))
        entete.addWidget(bouton_retirer)

        mise_en_page.addLayout(entete)

        self._conteneur_colonnes = QWidget()
        colonnes = QHBoxLayout(self._conteneur_colonnes)
        colonnes.setContentsMargins(0, 0, 0, 0)
        colonnes.setSpacing(24)
        self._cote_1 = EditeurCote("Côté 1")
        self._cote_2 = EditeurCote("Côté 2")
        colonnes.addWidget(self._cote_1, stretch=1)
        colonnes.addWidget(self._cote_2, stretch=1)
        mise_en_page.addWidget(self._conteneur_colonnes)

        self._editeur_legende = EditeurImageLegendee()
        mise_en_page.addWidget(self._editeur_legende)

        self._sur_changement_mode(self._combo_mode.currentText())

    def definir_numero(self, numero):
        self._label_numero.setText(f"Carte {numero}")

    def _sur_changement_mode(self, texte_mode):
        est_legende = LABELS_MODE.get(texte_mode) == "legende_image"
        self._conteneur_colonnes.setVisible(not est_legende)
        self._editeur_legende.setVisible(est_legende)

    def charger(self):
        """Peuple le bloc avec le contenu actuellement enregistre de
        self.flashcard_id (carte existante, ou fraichement creee et donc
        vierge)."""
        valeurs = lists.flashcards[self.flashcard_id]
        cote_1, cote_2, mode = valeurs[0], valeurs[1], valeurs[2]
        self._combo_mode.setCurrentText(LABELS_MODE_INVERSE.get(mode, list(LABELS_MODE.keys())[0]))
        if mode == "legende_image":
            self._editeur_legende.definir_bloc(cote_1)
        else:
            self._cote_1.definir_blocs(cote_1)
            self._cote_2.definir_blocs(cote_2)
        self._sur_changement_mode(self._combo_mode.currentText())

    def sauvegarder(self):
        """Valide puis enregistre ce bloc dans lists.flashcards. Renvoie
        (succes, mode) : succes=False si la validation echoue (rien n'est
        enregistre dans ce cas)."""
        mode = LABELS_MODE[self._combo_mode.currentText()]

        if mode == "legende_image":
            if not self._editeur_legende.est_valide():
                QMessageBox.warning(
                    self, "Image à légender incomplète",
                    f"« {self._label_numero.text()} » : choisis une image et "
                    f"place au moins un point à légender avant d'enregistrer."
                )
                return False, mode
            lists.definir_image_legendee(
                self.flashcard_id,
                self._editeur_legende.chemin_image(),
                self._editeur_legende.points(),
            )
        else:
            lists.definir_mode(self.flashcard_id, mode)
            lists.definir_cote(self.flashcard_id, 1, self._cote_1.blocs)
            lists.definir_cote(self.flashcard_id, 2, self._cote_2.blocs)

        return True, mode

    def focus_texte(self):
        if self._conteneur_colonnes.isVisible():
            self._cote_1.focus_texte()


class EditorPage(QWidget):
    def __init__(self, aller_a):
        super().__init__()
        self.setObjectName("page")
        self._aller_a = aller_a
        self._subject_name = None
        self._sous_dossier_courant = None
        self._blocs = []

        racine = QVBoxLayout(self)
        racine.setContentsMargins(36, 32, 36, 32)
        racine.setSpacing(18)

        self._titre = QLabel("Modifier la flashcard")
        self._titre.setObjectName("titre_page")
        racine.addWidget(self._titre)

        # Les blocs (un par carte) sont empiles dans une zone defilante : meme
        # avec beaucoup de cartes creees a la suite, la barre du bas
        # (Annuler/Enregistrer) reste TOUJOURS visible, hors du scroll.
        self._zone_defilement = QScrollArea()
        self._zone_defilement.setWidgetResizable(True)
        conteneur = QWidget()
        self._conteneur_blocs = QVBoxLayout(conteneur)
        self._conteneur_blocs.setSpacing(16)
        self._conteneur_blocs.addStretch()
        self._zone_defilement.setWidget(conteneur)
        racine.addWidget(self._zone_defilement, stretch=1)

        bas = QHBoxLayout()
        bouton_annuler = QPushButton("←  Annuler")
        bouton_annuler.setObjectName("bouton_secondaire")
        bouton_annuler.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_annuler.clicked.connect(self._annuler)
        bas.addWidget(bouton_annuler)

        bas.addStretch()

        bouton_enregistrer_nouvelle = QPushButton("💾➕  Enregistrer et créer une nouvelle")
        bouton_enregistrer_nouvelle.setObjectName("bouton_secondaire")
        bouton_enregistrer_nouvelle.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_enregistrer_nouvelle.setToolTip(
            "Enregistre toutes les cartes ci-dessus et en ajoute une nouvelle, "
            "vierge, juste en dessous — dans la même matière/sous-dossier, "
            "avec le même mode déjà sélectionné."
        )
        bouton_enregistrer_nouvelle.clicked.connect(self._enregistrer_et_nouvelle)
        bas.addWidget(bouton_enregistrer_nouvelle)

        bouton_enregistrer = QPushButton("💾  Enregistrer")
        bouton_enregistrer.setObjectName("bouton_accent")
        bouton_enregistrer.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_enregistrer.clicked.connect(self._enregistrer)
        bas.addWidget(bouton_enregistrer)

        widget_bas = QWidget()
        widget_bas.setLayout(bas)
        racine.addWidget(widget_bas)

    def charger(self, flashcard_id):
        """Reinitialise la page avec UN SEUL bloc pour flashcard_id (cas
        normal : ouverture depuis "Modifier" ou "+ Nouvelle flashcard")."""
        self._vider_blocs()

        valeurs = lists.flashcards[flashcard_id]
        self._sous_dossier_courant = valeurs[5] if len(valeurs) > 5 else None
        self._subject_name = self._trouver_matiere(flashcard_id)

        bloc = self._creer_bloc(flashcard_id)
        bloc.charger()

    def _trouver_matiere(self, flashcard_id):
        for subject_name, ids in lists.subjects.items():
            if flashcard_id in ids:
                return subject_name
        return None

    def _vider_blocs(self):
        while self._conteneur_blocs.count() > 1:
            item = self._conteneur_blocs.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
        self._blocs = []

    def _creer_bloc(self, flashcard_id):
        bloc = BlocFlashcard(flashcard_id, on_retirer=self._retirer_bloc)
        self._blocs.append(bloc)
        self._renumeroter_blocs()
        self._conteneur_blocs.insertWidget(self._conteneur_blocs.count() - 1, bloc)
        return bloc

    def _renumeroter_blocs(self):
        for index, bloc in enumerate(self._blocs, start=1):
            bloc.definir_numero(f"Carte {index}" if len(self._blocs) > 1 else "Flashcard")

    def _retirer_bloc(self, bloc):
        reponse = QMessageBox.question(
            self, "Supprimer cette flashcard ?",
            "Elle sera déplacée vers la Corbeille, d'où tu pourras la restaurer si besoin.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reponse != QMessageBox.StandardButton.Yes:
            return

        subject_name = self._subject_name
        lists.supprimer_flashcard(bloc.flashcard_id)
        self._blocs.remove(bloc)
        bloc.setParent(None)
        bloc.deleteLater()

        if not self._blocs:
            # plus rien a editer ici : retour a la matiere
            self._aller_a("matiere", subject_name=subject_name)
            return

        self._renumeroter_blocs()

    def _sauvegarder_tout(self):
        """Valide et enregistre tous les blocs presents, dans l'ordre. Des
        qu'un bloc echoue sa validation, on s'arrete la (les blocs precedents
        restent enregistres, c'est sans risque de les re-enregistrer plus
        tard). Renvoie (succes_global, mode_du_dernier_bloc_sauve)."""
        dernier_mode = None
        for bloc in self._blocs:
            succes, mode = bloc.sauvegarder()
            if not succes:
                return False, dernier_mode
            dernier_mode = mode
        return True, dernier_mode

    def _annuler(self):
        dernier_id = self._blocs[-1].flashcard_id if self._blocs else None
        self._aller_a("matiere", subject_name=self._subject_name, flashcard_a_reveler=dernier_id)

    def _enregistrer(self):
        succes, _ = self._sauvegarder_tout()
        if not succes:
            return
        dernier_id = self._blocs[-1].flashcard_id if self._blocs else None
        self._aller_a("matiere", subject_name=self._subject_name, flashcard_a_reveler=dernier_id)

    def _enregistrer_et_nouvelle(self):
        succes, mode = self._sauvegarder_tout()
        if not succes:
            return

        subject_name = self._subject_name
        if not subject_name:
            # cas limite improbable (matiere introuvable) : on retombe sur le
            # comportement normal plutot que de planter
            self._aller_a("matiere", subject_name=subject_name)
            return

        lists.create_flashcard(subject_name, sous_dossier=self._sous_dossier_courant)
        nouveau_id = lists.subjects[subject_name][-1]
        # garde le meme mode que la derniere carte : pratique pour enchainer
        # plusieurs cartes du meme type sans avoir a le reselectionner
        if mode:
            lists.definir_mode(nouveau_id, mode)

        nouveau_bloc = self._creer_bloc(nouveau_id)
        nouveau_bloc.charger()

        QTimer.singleShot(0, lambda: self._zone_defilement.ensureWidgetVisible(nouveau_bloc, 0, 40))
        nouveau_bloc.focus_texte()

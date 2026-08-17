"""Page d'une matiere : liste de ses flashcards (regroupees par sous-dossier /
chapitre, s'il y en a) + acces a la revision et a l'edition."""

from PyQt6.QtCore import Qt, QTimer, QMimeData, QPoint
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QPushButton,
    QMessageBox, QInputDialog, QFileDialog, QCheckBox
)

import lists
from ui import styles
from ui.apercu import resume_cote
from ui.move_dialog import DialogueDeplacer
from ui.reglages_portee_dialog import DialogueReglagesPortee


FORMAT_MIME_FLASHCARD = "application/x-flashbang-flashcard-id"


class _PoigneeGlisser(QLabel):
    """Petite poignee "⠿" : seul cet endroit precis de la ligne demarre un
    glisser-deposer (le reste de la ligne recoit des clics normaux - boutons
    Deplacer/Modifier/Supprimer -, qui seraient sinon en conflit avec un
    glissement demarre n'importe ou sur la ligne).

    Un simple CLIC (sans glisser) bascule en mode selection (cases a cocher)
    a la place - raccourci pratique pour choisir plusieurs flashcards a
    deplacer d'un coup, sans avoir a aller chercher le bouton dans la barre
    d'actions."""

    def __init__(self, flashcard_id, on_clic_simple=None):
        super().__init__("⠿")
        self._flashcard_id = flashcard_id
        self._on_clic_simple = on_clic_simple
        self._glissement_demarre = False
        self.setObjectName("poignee_glisser")
        self.setFixedWidth(26)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Glisser pour réordonner/déplacer, ou cliquer pour sélectionner plusieurs flashcards")
        self.setStyleSheet(f"color: {styles.TEXT_SECONDARY}; font-size: 16px;")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._origine = event.position().toPoint()
            self._glissement_demarre = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if (event.position().toPoint() - getattr(self, "_origine", QPoint())).manhattanLength() < 10:
            return
        self._glissement_demarre = True
        glisser = QDrag(self)
        donnees = QMimeData()
        donnees.setData(FORMAT_MIME_FLASHCARD, self._flashcard_id.encode("utf-8"))
        glisser.setMimeData(donnees)
        glisser.exec(Qt.DropAction.MoveAction)

    def mouseReleaseEvent(self, event):
        # un "clic simple" est un appui + relachement SANS jamais avoir
        # depasse le seuil de declenchement du glissement (sinon on
        # basculerait en mode selection juste apres avoir termine un
        # glisser-deposer, ce qui n'a pas de sens)
        if (event.button() == Qt.MouseButton.LeftButton
                and not self._glissement_demarre and self._on_clic_simple is not None):
            self._on_clic_simple()
        super().mouseReleaseEvent(event)


class LigneFlashcard(QFrame):
    def __init__(self, flashcard_id, on_modifier, on_supprimer, on_deplacer,
                 mode_selection=False, selectionnee=False, on_selection_changee=None,
                 on_glisser_deposer=None, on_bascule_selection=None):
        super().__init__()
        self.setObjectName("carte")
        self._flashcard_id = flashcard_id
        self._on_glisser_deposer = on_glisser_deposer
        mise_en_page = QHBoxLayout(self)
        mise_en_page.setContentsMargins(16, 12, 16, 12)

        cote_1, cote_2, mode, derniere_revision, indice, *_ = lists.flashcards[flashcard_id]

        if mode_selection:
            case = QCheckBox()
            case.setChecked(selectionnee)
            if on_selection_changee:
                case.toggled.connect(lambda coche: on_selection_changee(flashcard_id, coche))
            mise_en_page.addWidget(case)
        elif on_glisser_deposer is not None:
            mise_en_page.addWidget(_PoigneeGlisser(flashcard_id, on_clic_simple=on_bascule_selection))
            self.setAcceptDrops(True)

        colonne = QVBoxLayout()
        recto = QLabel(resume_cote(cote_1))
        recto.setStyleSheet("font-weight: 600; font-size: 13px;")
        colonne.addWidget(recto)

        info = "Recto / verso" if mode == "two_sides" else "Question → réponse"
        etat = "jamais révisée" if derniere_revision is None else f"revue le {derniere_revision.strftime('%d/%m/%Y')}"
        sous = QLabel(f"{info}  ·  {etat}  ·  intervalle actuel : indice {indice}")
        sous.setObjectName("sous_titre")
        colonne.addWidget(sous)

        mise_en_page.addLayout(colonne, stretch=1)

        if mode_selection:
            return

        bouton_deplacer = QPushButton("📂  Déplacer")
        bouton_deplacer.setObjectName("bouton_secondaire")
        bouton_deplacer.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_deplacer.clicked.connect(lambda: on_deplacer(flashcard_id))
        mise_en_page.addWidget(bouton_deplacer)

        bouton_modifier = QPushButton("✏️  Modifier")
        bouton_modifier.setObjectName("bouton_secondaire")
        bouton_modifier.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_modifier.clicked.connect(lambda: on_modifier(flashcard_id))
        mise_en_page.addWidget(bouton_modifier)

        bouton_supprimer = QPushButton("🗑️  Supprimer")
        bouton_supprimer.setObjectName("bouton_echec")
        bouton_supprimer.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_supprimer.clicked.connect(lambda: on_supprimer(flashcard_id))
        mise_en_page.addWidget(bouton_supprimer)

    # ------------------------------------------------------------------
    # Glisser-deposer (reordonner en deposant une carte "entre" deux autres)
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event):
        if self._on_glisser_deposer is not None and event.mimeData().hasFormat(FORMAT_MIME_FLASHCARD):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if not event.mimeData().hasFormat(FORMAT_MIME_FLASHCARD):
            return
        # ligne en haut de la carte survolee -> "avant elle", en bas -> "apres
        # elle" : indication visuelle simple (bordure superieure/inferieure
        # coloree) de l'endroit exact ou la carte glissee va atterrir
        apres = event.position().y() > self.height() / 2
        self.setStyleSheet(
            f"border-{'bottom' if apres else 'top'}: 3px solid {styles.ACCENT};"
        )
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.setStyleSheet("")

    def dropEvent(self, event):
        self.setStyleSheet("")
        if self._on_glisser_deposer is None or not event.mimeData().hasFormat(FORMAT_MIME_FLASHCARD):
            return
        id_source = bytes(event.mimeData().data(FORMAT_MIME_FLASHCARD)).decode("utf-8")
        if id_source == self._flashcard_id:
            return
        apres = event.position().y() > self.height() / 2
        self._on_glisser_deposer(id_source, self._flashcard_id, apres)
        event.acceptProposedAction()


class EnteteSousDossier(QWidget):
    """En-tete d'un groupe de flashcards (racine ou un sous-dossier nomme,
    eventuellement imbrique). `profondeur` (0 = racine ou sous-dossier de
    1er niveau) sert juste a indenter visuellement la hierarchie.

    IMPORTANT : chaque callback est un callable SANS argument (deja "capture"
    par l'appelant via un lambda par defaut) ; on le connecte via un wrapper
    `lambda checked=False: callback()` et pas directement, car QPushButton.clicked
    envoie un booleen "checked" en argument positionnel qui, sinon, ecraserait
    silencieusement un eventuel argument par defaut du callback (c'est ce qui
    causait le bug ou un sous-dossier se retrouvait nomme "False")."""

    def __init__(self, titre, profondeur=0, on_ajouter=None, on_ajouter_sousdossier=None,
                 on_supprimer=None, on_partager=None, plie=None, on_basculer_pli=None, on_melanger=None,
                 on_reglages=None, on_reviser=None, on_recevoir_glisser=None):
        super().__init__()
        self._on_recevoir_glisser = on_recevoir_glisser
        if on_recevoir_glisser is not None:
            # accepte le depot d'une flashcard glissee directement sur l'en-tete
            # de la section (indispensable pour un sous-dossier encore VIDE, qui
            # n'a donc aucune carte existante sur laquelle la deposer)
            self.setAcceptDrops(True)
        mise_en_page = QHBoxLayout(self)
        mise_en_page.setContentsMargins(2 + profondeur * 22, 14, 2, 2)

        # `plie` est None pour la racine (pas repliable), True/False pour un
        # vrai sous-dossier : une petite flèche permet de replier/déplier son
        # contenu (flashcards ET sous-sous-dossiers) sans rien supprimer.
        if plie is not None and on_basculer_pli:
            bouton_pli = QPushButton("▸" if plie else "▾")
            bouton_pli.setObjectName("bouton_icone")
            bouton_pli.setFixedWidth(24)
            bouton_pli.setCursor(Qt.CursorShape.PointingHandCursor)
            bouton_pli.setToolTip("Déplier" if plie else "Replier")
            bouton_pli.clicked.connect(lambda checked=False: on_basculer_pli())
            mise_en_page.addWidget(bouton_pli)

        label = QLabel(titre)
        label.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {styles.TEXT_SECONDARY};")
        # sans ca, le titre force la ligne entiere (tous les boutons compris)
        # a etre au moins aussi large que le texte complet -> quand la fenetre
        # est trop etroite, ce sont les boutons a droite qui se retrouvent
        # pousses hors de l'ecran. minimumWidth(0) autorise le titre a se
        # comprimer en premier (et etre tronque), pour que les boutons restent
        # toujours entierement visibles et cliquables.
        label.setMinimumWidth(0)
        mise_en_page.addWidget(label, stretch=1)

        if on_reviser:
            bouton_reviser = QPushButton("▶️")
            bouton_reviser.setObjectName("bouton_icone")
            bouton_reviser.setCursor(Qt.CursorShape.PointingHandCursor)
            bouton_reviser.setToolTip("Réviser uniquement ce sous-dossier")
            bouton_reviser.clicked.connect(lambda checked=False: on_reviser())
            mise_en_page.addWidget(bouton_reviser)

        if on_melanger:
            bouton_melanger = QPushButton("🔀")
            bouton_melanger.setObjectName("bouton_icone")
            bouton_melanger.setCursor(Qt.CursorShape.PointingHandCursor)
            bouton_melanger.setToolTip("Mélanger l'ordre des flashcards de ce sous-dossier")
            bouton_melanger.clicked.connect(lambda checked=False: on_melanger())
            mise_en_page.addWidget(bouton_melanger)

        if on_partager:
            bouton_partager = QPushButton("📤")
            bouton_partager.setObjectName("bouton_icone")
            bouton_partager.setCursor(Qt.CursorShape.PointingHandCursor)
            bouton_partager.setToolTip("Partager ce sous-dossier avec un ami")
            bouton_partager.clicked.connect(lambda checked=False: on_partager())
            mise_en_page.addWidget(bouton_partager)

        if on_reglages:
            bouton_reglages = QPushButton("🎚️")
            bouton_reglages.setObjectName("bouton_icone")
            bouton_reglages.setCursor(Qt.CursorShape.PointingHandCursor)
            bouton_reglages.setToolTip("Personnaliser la répétition espacée pour ce sous-dossier")
            bouton_reglages.clicked.connect(lambda checked=False: on_reglages())
            mise_en_page.addWidget(bouton_reglages)

        if on_ajouter:
            bouton_ajouter = QPushButton("➕ Flashcard")
            bouton_ajouter.setObjectName("bouton_icone")
            bouton_ajouter.setCursor(Qt.CursorShape.PointingHandCursor)
            bouton_ajouter.clicked.connect(lambda checked=False: on_ajouter())
            mise_en_page.addWidget(bouton_ajouter)

        if on_ajouter_sousdossier:
            bouton_sous = QPushButton("📁➕")
            bouton_sous.setObjectName("bouton_icone")
            bouton_sous.setCursor(Qt.CursorShape.PointingHandCursor)
            bouton_sous.setToolTip("Créer un sous-dossier à l'intérieur de celui-ci")
            bouton_sous.clicked.connect(lambda checked=False: on_ajouter_sousdossier())
            mise_en_page.addWidget(bouton_sous)

        if on_supprimer:
            bouton_supprimer = QPushButton("🗑️")
            bouton_supprimer.setObjectName("bouton_icone")
            bouton_supprimer.setCursor(Qt.CursorShape.PointingHandCursor)
            bouton_supprimer.setToolTip(
                "Supprime ce sous-dossier et ses sous-dossiers éventuels "
                "(les flashcards remontent à la racine, rien n'est supprimé)"
            )
            bouton_supprimer.clicked.connect(lambda checked=False: on_supprimer())
            mise_en_page.addWidget(bouton_supprimer)

    def dragEnterEvent(self, event):
        if self._on_recevoir_glisser is not None and event.mimeData().hasFormat(FORMAT_MIME_FLASHCARD):
            self.setStyleSheet(f"border: 2px dashed {styles.ACCENT};")
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.setStyleSheet("")

    def dropEvent(self, event):
        self.setStyleSheet("")
        if self._on_recevoir_glisser is None or not event.mimeData().hasFormat(FORMAT_MIME_FLASHCARD):
            return
        id_source = bytes(event.mimeData().data(FORMAT_MIME_FLASHCARD)).decode("utf-8")
        self._on_recevoir_glisser(id_source)
        event.acceptProposedAction()


class SubjectPage(QWidget):
    def __init__(self, aller_a):
        super().__init__()
        self.setObjectName("page")
        self._aller_a = aller_a
        self._subject_name = None
        self._mode_selection = False
        self._selection = set()
        # {subject_name: {chemins repliés}} — persiste tant que l'app tourne,
        # separe par matiere pour ne pas melanger les etats de deux matieres
        # differentes qui auraient des sous-dossiers de meme nom
        self._sousdossiers_plies = {}

        self._mise_en_page = QVBoxLayout(self)
        self._mise_en_page.setContentsMargins(36, 32, 36, 32)
        self._mise_en_page.setSpacing(16)

        entete = QHBoxLayout()
        colonne_titre = QVBoxLayout()
        self._titre = QLabel()
        self._titre.setObjectName("titre_page")
        self._titre.setMinimumWidth(0)
        colonne_titre.addWidget(self._titre)
        self._sous_titre = QLabel()
        self._sous_titre.setObjectName("sous_titre")
        self._sous_titre.setMinimumWidth(0)
        colonne_titre.addWidget(self._sous_titre)
        entete.addLayout(colonne_titre, stretch=1)

        self._bouton_reviser = QPushButton("▶️  Commencer la révision")
        self._bouton_reviser.setObjectName("bouton_accent")
        self._bouton_reviser.setCursor(Qt.CursorShape.PointingHandCursor)
        self._bouton_reviser.clicked.connect(self._lancer_revision)
        entete.addWidget(self._bouton_reviser, alignment=Qt.AlignmentFlag.AlignTop)

        bouton_partager_matiere = QPushButton("📤  Partager la matière")
        bouton_partager_matiere.setObjectName("bouton_secondaire")
        bouton_partager_matiere.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_partager_matiere.clicked.connect(self._exporter_matiere)
        entete.addWidget(bouton_partager_matiere, alignment=Qt.AlignmentFlag.AlignTop)

        bouton_reglages_matiere = QPushButton("🎚️")
        bouton_reglages_matiere.setObjectName("bouton_icone")
        bouton_reglages_matiere.setFixedSize(36, 36)
        bouton_reglages_matiere.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_reglages_matiere.setToolTip("Personnaliser la répétition espacée pour cette matière")
        bouton_reglages_matiere.clicked.connect(lambda checked=False: self._reglages_portee_matiere())
        entete.addWidget(bouton_reglages_matiere, alignment=Qt.AlignmentFlag.AlignTop)

        bouton_supprimer_matiere = QPushButton("🗑️  Supprimer la matière")
        bouton_supprimer_matiere.setObjectName("bouton_echec")
        bouton_supprimer_matiere.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_supprimer_matiere.clicked.connect(self._demander_suppression_matiere)
        entete.addWidget(bouton_supprimer_matiere, alignment=Qt.AlignmentFlag.AlignTop)

        self._mise_en_page.addLayout(entete)

        barre_actions = QHBoxLayout()
        # ces 3 boutons n'ont pas de sens pendant une selection multiple (on
        # ne cree/reordonne pas pendant qu'on choisit des cartes a deplacer) :
        # ils sont donc caches en mode selection (cf. _basculer_selection),
        # ce qui laisse de la place a "Deplacer/Partager la selection" sans
        # que la barre ne deborde de l'ecran (c'etait le bug remonte)
        self._bouton_nouvelle = QPushButton("➕  Nouvelle flashcard")
        self._bouton_nouvelle.setObjectName("bouton_secondaire")
        self._bouton_nouvelle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._bouton_nouvelle.clicked.connect(lambda: self._creer_flashcard(sous_dossier=None))
        barre_actions.addWidget(self._bouton_nouvelle)

        self._bouton_nouveau_sousdossier = QPushButton("📁➕  Nouveau sous-dossier")
        self._bouton_nouveau_sousdossier.setObjectName("bouton_secondaire")
        self._bouton_nouveau_sousdossier.setCursor(Qt.CursorShape.PointingHandCursor)
        self._bouton_nouveau_sousdossier.setToolTip("Ex. pour regrouper les flashcards par chapitre")
        self._bouton_nouveau_sousdossier.clicked.connect(lambda checked=False: self._creer_sousdossier())
        barre_actions.addWidget(self._bouton_nouveau_sousdossier)

        self._bouton_melanger = QPushButton("🔀  Mélanger l'ordre")
        self._bouton_melanger.setObjectName("bouton_secondaire")
        self._bouton_melanger.setCursor(Qt.CursorShape.PointingHandCursor)
        self._bouton_melanger.setToolTip(
            "Randomise l'ordre de révision de toutes les flashcards de cette "
            "matière (chaque sous-dossier est mélangé séparément, les cartes "
            "ne changent pas d'endroit)"
        )
        self._bouton_melanger.clicked.connect(self._melanger_matiere)
        barre_actions.addWidget(self._bouton_melanger)

        barre_actions.addStretch()

        self._bouton_selection = QPushButton("☑️  Sélectionner des flashcards")
        self._bouton_selection.setObjectName("bouton_secondaire")
        self._bouton_selection.setCursor(Qt.CursorShape.PointingHandCursor)
        self._bouton_selection.clicked.connect(self._basculer_selection)
        barre_actions.addWidget(self._bouton_selection)

        self._bouton_deplacer_selection = QPushButton("📂  Déplacer la sélection")
        self._bouton_deplacer_selection.setObjectName("bouton_secondaire")
        self._bouton_deplacer_selection.setCursor(Qt.CursorShape.PointingHandCursor)
        self._bouton_deplacer_selection.clicked.connect(self._deplacer_selection)
        self._bouton_deplacer_selection.hide()
        barre_actions.addWidget(self._bouton_deplacer_selection)

        self._bouton_partager_selection = QPushButton("📤  Partager la sélection")
        self._bouton_partager_selection.setObjectName("bouton_accent")
        self._bouton_partager_selection.setCursor(Qt.CursorShape.PointingHandCursor)
        self._bouton_partager_selection.clicked.connect(self._exporter_selection)
        self._bouton_partager_selection.hide()
        barre_actions.addWidget(self._bouton_partager_selection)

        self._mise_en_page.addLayout(barre_actions)

        self._zone_defilement = QScrollArea()
        self._zone_defilement.setWidgetResizable(True)
        self._conteneur_liste = QWidget()
        self._liste = QVBoxLayout(self._conteneur_liste)
        self._liste.setSpacing(8)
        self._liste.addStretch()
        self._zone_defilement.setWidget(self._conteneur_liste)
        self._mise_en_page.addWidget(self._zone_defilement)

    def _creer_flashcard(self, sous_dossier=None):
        lists.create_flashcard(self._subject_name, sous_dossier=sous_dossier)
        nouveau_id = self._subject_name and lists.subjects[self._subject_name][-1]
        self.charger(self._subject_name)
        self._aller_a("editeur", flashcard_id=nouveau_id)

    def _creer_sousdossier(self, parent=None):
        invite = (
            f"Nom du sous-dossier à créer dans « {parent} » :" if parent
            else "Nom du sous-dossier (ex. Chapitre 1) :"
        )
        nom, ok = QInputDialog.getText(self, "Nouveau sous-dossier", invite)
        if ok and nom:
            chemin = f"{parent}{lists.SEPARATEUR_SOUSDOSSIER}{nom}" if parent else nom
            lists.create_subfolder(self._subject_name, chemin)
            self.charger(self._subject_name)

    def charger(self, subject_name, flashcard_a_reveler=None):
        self._subject_name = subject_name
        self._titre.setText(subject_name)

        if flashcard_a_reveler is not None:
            # deplie automatiquement le sous-dossier (et ses parents) de la
            # carte qu'on veut montrer, sinon elle resterait invisible si on
            # avait replie ce sous-dossier avant d'aller l'editer
            sous_dossier_cible = lists._sous_dossier_de(flashcard_a_reveler)
            if sous_dossier_cible is not None:
                plies = self._sousdossiers_plies.get(subject_name, set())
                for chemin in self._ancetres_de(sous_dossier_cible) + [sous_dossier_cible]:
                    plies.discard(chemin)

        nombre = lists.nombre_flashcards_a_reviser(subject_name)
        total = len(lists.subjects.get(subject_name, []))
        self._sous_titre.setText(f"{total} flashcard(s) au total  ·  {nombre} à réviser aujourd'hui")

        # le bouton reste actif meme si rien n'est prevu : ca permet de lancer
        # une revision libre sur toutes les flashcards de la matiere, en avance
        self._bouton_reviser.setEnabled(total > 0)
        if nombre > 0:
            self._bouton_reviser.setText("▶️  Commencer la révision")
        elif total > 0:
            self._bouton_reviser.setText("🔁  Réviser quand même (rien de prévu)")
        else:
            self._bouton_reviser.setText("Aucune flashcard dans cette matière")

        while self._liste.count() > 1:
            item = self._liste.takeAt(0)
            widget = item.widget()
            if widget:
                # setParent(None) detache immediatement le widget de l'arbre
                # (deleteLater seul ne le detruit qu'au prochain passage dans
                # la boucle d'evenements, ce qui laissait des doublons visibles
                # le temps d'un rafraichissement, par ex. en repliant un
                # sous-dossier juste apres un autre rafraichissement)
                widget.setParent(None)
                widget.deleteLater()

        lignes_par_id = {}

        groupes = lists.flashcards_par_sousdossier(subject_name)
        racine = groupes.pop(None, [])
        # tri alphabetique, mais qui respecte la hierarchie : tous les enfants
        # d'un chemin apparaissent juste apres lui (tri lexicographique normal
        # sur les chemins "Chapitre 1/Partie A" fait deja exactement ca)
        chemins_tries = sorted(groupes.keys())

        # la racine n'a pas de bouton "supprimer" (ce n'est pas un vrai
        # sous-dossier) mais garde le bouton "+" pour y ajouter directement
        if racine or not chemins_tries:
            entete_racine = EnteteSousDossier(
                "📍 À la racine" if chemins_tries else "Flashcards",
                on_ajouter=None if self._mode_selection else (lambda: self._creer_flashcard(sous_dossier=None)),
                on_recevoir_glisser=None if self._mode_selection else (
                    lambda id_source: self._deplacer_flashcard_vers_sousdossier(id_source, None)
                ),
            )
            self._liste.insertWidget(self._liste.count() - 1, entete_racine)
            for flashcard_id in racine:
                ligne = self._creer_ligne(flashcard_id)
                lignes_par_id[flashcard_id] = ligne
                self._liste.insertWidget(self._liste.count() - 1, ligne)

        plies = self._sousdossiers_plies.get(subject_name, set())

        for chemin in chemins_tries:
            # cache si un de ses ANCETRES (pas lui-meme) est replie : dans ce
            # cas son en-tete elle-meme ne s'affiche pas (elle reste "a
            # l'interieur" du parent replie), mais son propre etat de pli est
            # conserve pour quand le parent sera redeplie
            ancetres = self._ancetres_de(chemin)
            if any(a in plies for a in ancetres):
                continue

            profondeur = chemin.count(lists.SEPARATEUR_SOUSDOSSIER)
            nom_affiche = chemin.rsplit(lists.SEPARATEUR_SOUSDOSSIER, 1)[-1]
            est_plie = chemin in plies
            entete = EnteteSousDossier(
                f"📂 {nom_affiche}",
                profondeur=profondeur,
                on_ajouter=None if self._mode_selection else (lambda c=chemin: self._creer_flashcard(sous_dossier=c)),
                on_ajouter_sousdossier=None if self._mode_selection else (lambda c=chemin: self._creer_sousdossier(parent=c)),
                on_supprimer=None if self._mode_selection else (lambda c=chemin: self._demander_suppression_sousdossier(c)),
                on_partager=None if self._mode_selection else (lambda c=chemin: self._exporter_sousdossier(c)),
                on_melanger=None if self._mode_selection else (lambda c=chemin: self._melanger_sousdossier(c)),
                on_reglages=None if self._mode_selection else (lambda c=chemin: self._reglages_portee_sousdossier(c)),
                on_reviser=None if self._mode_selection else (lambda c=chemin: self._lancer_revision_sousdossier(c)),
                plie=est_plie,
                on_basculer_pli=lambda c=chemin: self._basculer_pli(c),
                on_recevoir_glisser=None if self._mode_selection else (
                    lambda id_source, c=chemin: self._deplacer_flashcard_vers_sousdossier(id_source, c)
                ),
            )
            self._liste.insertWidget(self._liste.count() - 1, entete)
            if not est_plie:
                cartes_du_groupe = groupes[chemin]
                for flashcard_id in cartes_du_groupe:
                    ligne = self._creer_ligne(flashcard_id)
                    lignes_par_id[flashcard_id] = ligne
                    self._liste.insertWidget(self._liste.count() - 1, ligne)

        if flashcard_a_reveler is not None and flashcard_a_reveler in lignes_par_id:
            widget_cible = lignes_par_id[flashcard_a_reveler]
            # differe au prochain passage dans la boucle d'evenements : la
            # zone de defilement doit d'abord terminer sa mise en page avec
            # le nouveau contenu avant qu'ensureWidgetVisible ait un resultat
            # fiable (sinon la position calculee est celle d'avant le refresh)
            QTimer.singleShot(0, lambda: self._zone_defilement.ensureWidgetVisible(widget_cible, 0, 40))

    @staticmethod
    def _ancetres_de(chemin):
        """Renvoie la liste des chemins ancetres STRICTS de `chemin` (sans lui-
        meme), du plus proche parent racine au plus proche parent direct."""
        segments = chemin.split(lists.SEPARATEUR_SOUSDOSSIER)
        ancetres = []
        cumul = ""
        for segment in segments[:-1]:
            cumul = segment if not cumul else f"{cumul}{lists.SEPARATEUR_SOUSDOSSIER}{segment}"
            ancetres.append(cumul)
        return ancetres

    def _basculer_pli(self, chemin):
        plies = self._sousdossiers_plies.setdefault(self._subject_name, set())
        if chemin in plies:
            plies.discard(chemin)
        else:
            plies.add(chemin)
        self.charger(self._subject_name)

    def _creer_ligne(self, flashcard_id):
        return LigneFlashcard(
            flashcard_id,
            on_modifier=lambda fid: self._aller_a("editeur", flashcard_id=fid),
            on_supprimer=self._demander_suppression,
            on_deplacer=self._deplacer_flashcard,
            mode_selection=self._mode_selection,
            selectionnee=flashcard_id in self._selection,
            on_selection_changee=self._on_selection_changee,
            on_glisser_deposer=None if self._mode_selection else self._deplacer_flashcard_glisser,
            on_bascule_selection=None if self._mode_selection else self._basculer_selection,
        )

    def _deplacer_flashcard_glisser(self, id_source, id_cible, apres):
        if id_source == id_cible:
            return
        sous_dossier_cible = lists._sous_dossier_de(id_cible)
        if lists._sous_dossier_de(id_source) != sous_dossier_cible:
            # deposee sur une carte d'un AUTRE sous-dossier : la carte
            # change carrement de sous-dossier (comme le bouton "📂 Déplacer",
            # mais en un geste), puis se positionne pile a l'endroit du depot
            lists.deplacer_flashcard(id_source, self._subject_name, sous_dossier_cible)
        if lists.deplacer_flashcard_vers_position(self._subject_name, id_source, id_cible, apres=apres):
            # remet en evidence la carte qu'on vient de deplacer, comme apres
            # n'importe quelle autre modification qui rafraichit la liste
            self.charger(self._subject_name, flashcard_a_reveler=id_source)

    def _deplacer_flashcard_vers_sousdossier(self, id_source, sous_dossier_cible):
        """Depot sur l'EN-TETE d'une section (pas sur une carte precise) :
        deplace simplement la carte dans ce sous-dossier, ajoutee a la fin -
        c'est le seul moyen de deplacer une carte par glisser-deposer vers un
        sous-dossier encore VIDE (qui n'a donc aucune carte sur laquelle la
        deposer)."""
        if lists._sous_dossier_de(id_source) == sous_dossier_cible:
            return
        lists.deplacer_flashcard(id_source, self._subject_name, sous_dossier_cible)
        self.charger(self._subject_name, flashcard_a_reveler=id_source)

    # ------------------------------------------------------------------
    # Sélection multiple (pour partager une sélection libre de flashcards)
    # ------------------------------------------------------------------

    def _basculer_selection(self):
        self._mode_selection = not self._mode_selection
        self._selection.clear()
        self._bouton_selection.setText(
            "✖️  Annuler la sélection" if self._mode_selection else "☑️  Sélectionner des flashcards"
        )
        self._bouton_partager_selection.setVisible(self._mode_selection)
        self._bouton_partager_selection.setText("📤  Partager la sélection")
        self._bouton_partager_selection.setEnabled(False)
        self._bouton_deplacer_selection.setVisible(self._mode_selection)
        self._bouton_deplacer_selection.setText("📂  Déplacer la sélection")
        self._bouton_deplacer_selection.setEnabled(False)
        # cache les actions de creation/reordonnancement pendant la selection
        # (elles n'ont pas leur place ici et manqueraient sinon de place a
        # cote des boutons "Deplacer/Partager la selection")
        self._bouton_nouvelle.setVisible(not self._mode_selection)
        self._bouton_nouveau_sousdossier.setVisible(not self._mode_selection)
        self._bouton_melanger.setVisible(not self._mode_selection)
        self.charger(self._subject_name)

    def _on_selection_changee(self, flashcard_id, coche):
        if coche:
            self._selection.add(flashcard_id)
        else:
            self._selection.discard(flashcard_id)
        nombre = len(self._selection)
        self._bouton_partager_selection.setEnabled(nombre > 0)
        self._bouton_partager_selection.setText(
            f"📤  Partager la sélection ({nombre})" if nombre else "📤  Partager la sélection"
        )
        self._bouton_deplacer_selection.setEnabled(nombre > 0)
        self._bouton_deplacer_selection.setText(
            f"📂  Déplacer la sélection ({nombre})" if nombre else "📂  Déplacer la sélection"
        )

    def _deplacer_selection(self):
        if not self._selection:
            return
        dialogue = DialogueDeplacer(self, self._subject_name, None)
        dialogue.setWindowTitle(f"Déplacer {len(self._selection)} flashcard(s)")
        if dialogue.exec():
            subject_name_cible, sous_dossier_cible = dialogue.resultat()
            for flashcard_id in list(self._selection):
                lists.deplacer_flashcard(flashcard_id, subject_name_cible, sous_dossier_cible)
            self._basculer_selection()  # quitte le mode selection + rafraichit

    def _exporter_selection(self):
        if not self._selection:
            return
        chemin, _ = QFileDialog.getSaveFileName(
            self, "Partager la sélection", "sélection.fbshare", "Partage Flash Bang (*.fbshare)"
        )
        if not chemin:
            return
        if not chemin.endswith(".fbshare"):
            chemin += ".fbshare"
        try:
            lists.exporter_selection(list(self._selection), chemin)
        except OSError as erreur:
            QMessageBox.warning(self, "Échec de l'export", f"Impossible d'écrire le fichier :\n{erreur}")
            return
        QMessageBox.information(
            self, "Sélection partagée",
            f"{len(self._selection)} flashcard(s) exportée(s) avec succès."
        )
        self._basculer_selection()

    def _deplacer_flashcard(self, flashcard_id):
        sous_dossier_actuel = lists.flashcards[flashcard_id][5] if len(lists.flashcards[flashcard_id]) > 5 else None
        dialogue = DialogueDeplacer(self, self._subject_name, sous_dossier_actuel)
        if dialogue.exec():
            subject_name_cible, sous_dossier_cible = dialogue.resultat()
            lists.deplacer_flashcard(flashcard_id, subject_name_cible, sous_dossier_cible)
            self.charger(self._subject_name)

    def _demander_suppression_sousdossier(self, chemin_sous_dossier):
        nom_affiche = chemin_sous_dossier.rsplit(lists.SEPARATEUR_SOUSDOSSIER, 1)[-1]
        nombre = len(lists.flashcards_du_sousarbre(self._subject_name, chemin_sous_dossier))

        boite = QMessageBox(self)
        boite.setIcon(QMessageBox.Icon.Question)
        boite.setWindowTitle("Supprimer ce sous-dossier ?")
        boite.setText(
            f"« {nom_affiche} » (et ses éventuels sous-dossiers) contient "
            f"{nombre} flashcard{'s' if nombre != 1 else ''}. Qu'en faire ?"
        )
        bouton_deplacer = boite.addButton("📂  Déplacer les flashcards ailleurs", QMessageBox.ButtonRole.ActionRole)
        bouton_supprimer = boite.addButton("🗑️  Les envoyer à la Corbeille aussi", QMessageBox.ButtonRole.DestructiveRole)
        boite.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        boite.exec()
        bouton_clique = boite.clickedButton()

        if bouton_clique is bouton_deplacer:
            dialogue = DialogueDeplacer(self, self._subject_name, None)
            dialogue.setWindowTitle(f"Déplacer le contenu de « {nom_affiche} »")
            if dialogue.exec():
                subject_name_cible, sous_dossier_cible = dialogue.resultat()
                lists.deplacer_contenu_sousdossier(
                    self._subject_name, chemin_sous_dossier, subject_name_cible, sous_dossier_cible
                )
                self.charger(self._subject_name)
        elif bouton_clique is bouton_supprimer:
            lists.supprimer_sousdossier_et_flashcards(self._subject_name, chemin_sous_dossier)
            self.charger(self._subject_name)

    def _exporter_matiere(self):
        chemin, _ = QFileDialog.getSaveFileName(
            self, f"Partager « {self._subject_name} »",
            f"{self._subject_name}.fbshare", "Partage Flash Bang (*.fbshare)"
        )
        if not chemin:
            return
        if not chemin.endswith(".fbshare"):
            chemin += ".fbshare"
        try:
            lists.exporter_matiere(self._subject_name, chemin)
        except OSError as erreur:
            QMessageBox.warning(self, "Échec de l'export", f"Impossible d'écrire le fichier :\n{erreur}")
            return
        QMessageBox.information(
            self, "Matière partagée",
            f"« {self._subject_name} » a été exportée avec succès."
        )

    def _exporter_sousdossier(self, chemin_sous_dossier):
        nom_affiche = chemin_sous_dossier.rsplit(lists.SEPARATEUR_SOUSDOSSIER, 1)[-1]
        chemin, _ = QFileDialog.getSaveFileName(
            self, f"Partager « {nom_affiche} »",
            f"{nom_affiche}.fbshare", "Partage Flash Bang (*.fbshare)"
        )
        if not chemin:
            return
        if not chemin.endswith(".fbshare"):
            chemin += ".fbshare"
        try:
            lists.exporter_sousdossier(self._subject_name, chemin_sous_dossier, chemin)
        except OSError as erreur:
            QMessageBox.warning(self, "Échec de l'export", f"Impossible d'écrire le fichier :\n{erreur}")
            return
        QMessageBox.information(
            self, "Sous-dossier partagé",
            f"« {nom_affiche} » a été exporté avec succès."
        )

    def _reglages_portee_matiere(self):
        dialogue = DialogueReglagesPortee(
            self, f"matière « {self._subject_name} »", lists.cle_portee_matiere(self._subject_name)
        )
        dialogue.exec()
        self.charger(self._subject_name)

    def _reglages_portee_sousdossier(self, chemin):
        nom_affiche = chemin.rsplit(lists.SEPARATEUR_SOUSDOSSIER, 1)[-1]
        dialogue = DialogueReglagesPortee(
            self, f"sous-dossier « {nom_affiche} »",
            lists.cle_portee_sousdossier(self._subject_name, chemin)
        )
        dialogue.exec()
        self.charger(self._subject_name)

    def _melanger_matiere(self):
        lists.melanger_ordre_flashcards(self._subject_name)
        self.charger(self._subject_name)

    def _melanger_sousdossier(self, chemin):
        lists.melanger_ordre_flashcards(self._subject_name, sous_dossier=chemin)
        self.charger(self._subject_name)

    def _lancer_revision(self):
        rien_de_prevu = lists.nombre_flashcards_a_reviser(self._subject_name) == 0
        self._aller_a(
            "revision",
            subject_name=self._subject_name,
            toutes_les_flashcards=rien_de_prevu
        )

    def _lancer_revision_sousdossier(self, chemin):
        rien_de_prevu = lists.nombre_flashcards_a_reviser_sousdossier(self._subject_name, chemin) == 0
        self._aller_a(
            "revision",
            subject_name=self._subject_name,
            subfolder_path=chemin,
            toutes_les_flashcards=rien_de_prevu
        )

    def _demander_suppression(self, flashcard_id):
        reponse = QMessageBox.question(
            self, "Supprimer cette flashcard ?",
            "Elle sera déplacée vers la Corbeille, d'où tu pourras la restaurer si besoin.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reponse == QMessageBox.StandardButton.Yes:
            lists.supprimer_flashcard(flashcard_id)
            self.charger(self._subject_name)

    def _demander_suppression_matiere(self):
        nombre = len(lists.subjects.get(self._subject_name, []))
        reponse = QMessageBox.question(
            self, "Supprimer cette matière ?",
            f"« {self._subject_name} » et ses {nombre} flashcard(s) seront "
            f"déplacées vers la Corbeille, d'où tu pourras tout restaurer si besoin.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reponse == QMessageBox.StandardButton.Yes:
            lists.supprimer_matiere(self._subject_name)
            self._aller_a("accueil")

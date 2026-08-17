"""Fenetre principale : barre laterale (dossiers/matieres) + zone de contenu
qui bascule entre les differentes pages de l'app."""

import json

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QStackedWidget, QInputDialog, QFrame, QButtonGroup,
    QFileDialog, QMessageBox
)

import lists
from ui import styles
from ui.dashboard_page import DashboardPage
from ui.calendar_page import CalendarPage
from ui.subject_page import SubjectPage
from ui.editor_page import EditorPage
from ui.review_page import ReviewPage
from ui.trash_page import TrashPage
from ui.settings_page import SettingsPage
from ui.reglages_portee_dialog import DialogueReglagesPortee
from ui.import_dialog import DialogueDestination


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Flash Bang")
        self.resize(1200, 780)
        self.setStyleSheet(styles.definir_theme("sombre"))  # theme sombre par defaut au lancement
        self._page_courante = "accueil"
        self._kwargs_courants = {}

        central = QWidget()
        self.setCentralWidget(central)
        mise_en_page = QHBoxLayout(central)
        mise_en_page.setContentsMargins(0, 0, 0, 0)
        mise_en_page.setSpacing(0)

        self._construire_sidebar()
        mise_en_page.addWidget(self._sidebar)

        self._pile = QStackedWidget()
        mise_en_page.addWidget(self._pile, stretch=1)

        self._pages = {
            "accueil": DashboardPage(self.aller_a),
            "calendrier": CalendarPage(self.aller_a),
            "matiere": SubjectPage(self.aller_a),
            "editeur": EditorPage(self.aller_a),
            "revision": ReviewPage(self.aller_a),
            "corbeille": TrashPage(self.aller_a),
            "parametres": SettingsPage(self.aller_a),
        }
        self._noms_pages = list(self._pages.keys())
        for page in self._pages.values():
            self._pile.addWidget(page)

        self.aller_a("accueil")

        # verification silencieuse de mise a jour, differee de quelques
        # secondes pour ne jamais retarder l'affichage de la fenetre au
        # lancement (et laisser le temps a la connexion de s'etablir) ; en
        # cas d'echec (pas d'internet...), rien ne s'affiche - seule une
        # vraie mise a jour disponible declenche une popup (voir
        # SettingsPage._sur_resultat_maj)
        QTimer.singleShot(3000, lambda: self._pages["parametres"]._verifier_maj(silencieux=True))

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------

    def _construire_sidebar(self):
        self._sidebar = QWidget()
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setFixedWidth(240)

        mise_en_page = QVBoxLayout(self._sidebar)
        mise_en_page.setContentsMargins(0, 16, 0, 16)
        mise_en_page.setSpacing(4)

        titre = QLabel("🔁  Flash Bang")
        titre.setObjectName("titre_app")
        titre.setContentsMargins(16, 0, 16, 12)
        mise_en_page.addWidget(titre)

        self._groupe_nav = QButtonGroup(self)
        self._groupe_nav.setExclusive(True)

        self._bouton_accueil = self._creer_lien("🏠  Accueil", lambda: self.aller_a("accueil"))
        self._bouton_calendrier = self._creer_lien("📅  Calendrier", lambda: self.aller_a("calendrier"))
        self._bouton_corbeille = self._creer_lien("🗑️  Corbeille", lambda: self.aller_a("corbeille"))
        self._bouton_parametres = self._creer_lien("⚙️  Paramètres", lambda: self.aller_a("parametres"))
        mise_en_page.addWidget(self._bouton_accueil)
        mise_en_page.addWidget(self._bouton_calendrier)
        mise_en_page.addWidget(self._bouton_corbeille)
        mise_en_page.addWidget(self._bouton_parametres)

        label_dossiers = QLabel("DOSSIERS")
        label_dossiers.setObjectName("section_sidebar")
        mise_en_page.addWidget(label_dossiers)

        self._zone_defilement = QScrollArea()
        self._zone_defilement.setWidgetResizable(True)
        self._conteneur_dossiers = QWidget()
        self._mise_en_page_dossiers = QVBoxLayout(self._conteneur_dossiers)
        self._mise_en_page_dossiers.setContentsMargins(4, 0, 4, 0)
        self._mise_en_page_dossiers.setSpacing(2)
        self._mise_en_page_dossiers.addStretch()
        self._zone_defilement.setWidget(self._conteneur_dossiers)
        mise_en_page.addWidget(self._zone_defilement, stretch=1)

        bouton_nouveau_dossier = QPushButton("➕ 📁  Nouveau dossier")
        bouton_nouveau_dossier.setObjectName("bouton_secondaire")
        bouton_nouveau_dossier.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_nouveau_dossier.clicked.connect(self._creer_dossier)
        boite = QHBoxLayout()
        boite.setContentsMargins(12, 8, 12, 4)
        boite.addWidget(bouton_nouveau_dossier)
        mise_en_page.addLayout(boite)

        bouton_importer = QPushButton("📥  Importer un partage")
        bouton_importer.setObjectName("bouton_secondaire")
        bouton_importer.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_importer.setToolTip("Ouvrir un fichier .fbshare reçu d'un ami")
        bouton_importer.clicked.connect(self._importer_fichier)
        boite_importer = QHBoxLayout()
        boite_importer.setContentsMargins(12, 0, 12, 8)
        boite_importer.addWidget(bouton_importer)
        mise_en_page.addLayout(boite_importer)

        self._bouton_theme = QPushButton("☀️  Mode clair")
        self._bouton_theme.setObjectName("bouton_secondaire")
        self._bouton_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self._bouton_theme.clicked.connect(self._basculer_theme)
        boite_theme = QHBoxLayout()
        boite_theme.setContentsMargins(12, 0, 12, 0)
        boite_theme.addWidget(self._bouton_theme)
        mise_en_page.addLayout(boite_theme)

        self._rafraichir_sidebar()

    def _basculer_theme(self):
        nouvelle_qss = styles.basculer_theme()
        self.setStyleSheet(nouvelle_qss)
        self._bouton_theme.setText(
            "☀️  Mode clair" if styles.mode_actuel == "sombre" else "🌙  Mode sombre"
        )
        # on rejoue la navigation courante pour que toutes les couleurs deja
        # dessinees (badges, previsualisations KaTeX...) se regenerent avec le
        # nouveau theme, plutot que de tout redessiner manuellement page par page.
        # Exception : la page de revision, ou rejouer aller_a() redemarrerait
        # une session en cours -> on se contente de redessiner la carte affichee.
        if self._page_courante == "revision":
            self._pages["revision"]._afficher_carte_courante()
        else:
            self.aller_a(self._page_courante, **self._kwargs_courants)

    def _creer_lien(self, texte, gestionnaire):
        bouton = QPushButton(texte)
        bouton.setObjectName("lien_sidebar")
        bouton.setCheckable(True)
        bouton.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton.setContentsMargins(0, 0, 0, 0)
        bouton.clicked.connect(gestionnaire)
        return bouton

    def _rafraichir_sidebar(self):
        while self._mise_en_page_dossiers.count() > 1:
            item = self._mise_en_page_dossiers.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        noms_matieres = list(lists.subjects.keys())

        for folder_name, subject_names in lists.folders.items():
            ligne_dossier = QHBoxLayout()
            label_dossier = QLabel(f"📁  {folder_name}")
            label_dossier.setStyleSheet("font-size: 12px; font-weight: 600; padding: 8px 6px 2px 10px;")
            # sans ca, le nom du dossier force toute la ligne (icones comprises)
            # a etre plus large que la barre laterale -> les icones de droite se
            # retrouvent poussees hors de la vue plutot que d'etre toujours
            # visibles/cliquables
            label_dossier.setMinimumWidth(0)
            ligne_dossier.addWidget(label_dossier, stretch=1)

            nombre_du_dossier = sum(lists.nombre_flashcards_a_reviser(s) for s in subject_names)
            bouton_reviser_dossier = QPushButton("▶️")
            bouton_reviser_dossier.setFixedSize(24, 24)
            bouton_reviser_dossier.setObjectName("bouton_icone")
            bouton_reviser_dossier.setCursor(Qt.CursorShape.PointingHandCursor)
            bouton_reviser_dossier.setToolTip(
                f"Réviser les {nombre_du_dossier} flashcard(s) suggérée(s) de ce dossier"
                if nombre_du_dossier > 0 else "Réviser ce dossier (rien de prévu, entraînement libre)"
            )
            bouton_reviser_dossier.clicked.connect(lambda checked=False, d=folder_name: self._lancer_revision_dossier(d))
            ligne_dossier.addWidget(bouton_reviser_dossier)

            bouton_partager = QPushButton("📤")
            bouton_partager.setFixedSize(24, 24)
            bouton_partager.setObjectName("bouton_icone")
            bouton_partager.setCursor(Qt.CursorShape.PointingHandCursor)
            bouton_partager.setToolTip("Partager ce dossier avec un ami")
            bouton_partager.clicked.connect(lambda checked=False, d=folder_name: self._exporter_dossier(d))
            ligne_dossier.addWidget(bouton_partager)

            bouton_reglages_dossier = QPushButton("🎚️")
            bouton_reglages_dossier.setFixedSize(24, 24)
            bouton_reglages_dossier.setObjectName("bouton_icone")
            bouton_reglages_dossier.setCursor(Qt.CursorShape.PointingHandCursor)
            bouton_reglages_dossier.setToolTip("Personnaliser la répétition espacée pour ce dossier")
            bouton_reglages_dossier.clicked.connect(lambda checked=False, d=folder_name: self._reglages_portee_dossier(d))
            ligne_dossier.addWidget(bouton_reglages_dossier)

            bouton_ajouter = QPushButton("➕")
            bouton_ajouter.setFixedSize(24, 24)
            bouton_ajouter.setObjectName("bouton_icone")
            bouton_ajouter.setCursor(Qt.CursorShape.PointingHandCursor)
            bouton_ajouter.setToolTip("Ajouter une matière dans ce dossier")
            bouton_ajouter.clicked.connect(lambda checked=False, d=folder_name: self._creer_matiere(d))
            ligne_dossier.addWidget(bouton_ajouter)

            bouton_supprimer_dossier = QPushButton("🗑️")
            bouton_supprimer_dossier.setFixedSize(24, 24)
            bouton_supprimer_dossier.setObjectName("bouton_icone")
            bouton_supprimer_dossier.setCursor(Qt.CursorShape.PointingHandCursor)
            bouton_supprimer_dossier.setToolTip("Supprimer ce dossier")
            bouton_supprimer_dossier.clicked.connect(lambda checked=False, d=folder_name: self._demander_suppression_dossier(d))
            ligne_dossier.addWidget(bouton_supprimer_dossier)

            widget_ligne = QWidget()
            widget_ligne.setLayout(ligne_dossier)
            self._mise_en_page_dossiers.insertWidget(self._mise_en_page_dossiers.count() - 1, widget_ligne)

            for subject_name in subject_names:
                nombre = lists.nombre_flashcards_a_reviser(subject_name)
                fond, texte = styles.badge_pour(subject_name, noms_matieres)
                libelle = f"●  {subject_name}" + (f"   {nombre}" if nombre > 0 else "")
                bouton = self._creer_lien(
                    libelle, lambda checked=False, s=subject_name: self.aller_a("matiere", subject_name=s)
                )
                bouton.setStyleSheet(f"QPushButton#lien_sidebar {{ color: {texte if nombre else styles.TEXT_PRIMARY}; padding-left: 26px; }}")
                self._mise_en_page_dossiers.insertWidget(self._mise_en_page_dossiers.count() - 1, bouton)

    def _creer_dossier(self):
        nom, ok = QInputDialog.getText(self, "Nouveau dossier", "Nom du dossier (ex. Semestre 1) :")
        if ok and nom:
            lists.create_folder(nom)
            self._rafraichir_sidebar()

    def _creer_matiere(self, folder_name):
        nom, ok = QInputDialog.getText(self, "Nouvelle matière", "Nom de la matière :")
        if ok and nom:
            lists.create_subject(folder_name, nom)
            self._rafraichir_sidebar()
            self.aller_a("matiere", subject_name=nom)

    def _reglages_portee_dossier(self, folder_name):
        dialogue = DialogueReglagesPortee(
            self, f"dossier « {folder_name} »", lists.cle_portee_dossier(folder_name)
        )
        dialogue.exec()
        self._rafraichir_sidebar()

    def _lancer_revision_dossier(self, folder_name):
        matieres = lists.folders.get(folder_name, [])
        if not matieres or not any(lists.subjects.get(s) for s in matieres):
            QMessageBox.information(
                self, "Rien à réviser",
                f"« {folder_name} » n'a aucune flashcard pour l'instant."
            )
            return
        rien_de_prevu = sum(lists.nombre_flashcards_a_reviser(s) for s in matieres) == 0
        self.aller_a("revision", folder_name=folder_name, toutes_les_flashcards=rien_de_prevu)

    def _demander_suppression_dossier(self, folder_name):
        matieres = lists.folders.get(folder_name, [])
        nombre_flashcards = sum(len(lists.subjects.get(s, [])) for s in matieres)
        reponse = QMessageBox.question(
            self, "Supprimer ce dossier ?",
            f"« {folder_name} », ses {len(matieres)} matière(s) et "
            f"{nombre_flashcards} flashcard(s) seront déplacés vers la "
            f"Corbeille, d'où tu pourras tout restaurer si besoin.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reponse == QMessageBox.StandardButton.Yes:
            lists.supprimer_dossier(folder_name)
            self.aller_a("accueil")

    # ------------------------------------------------------------------
    # Partage : exporter/importer un dossier entier
    # ------------------------------------------------------------------

    def _exporter_dossier(self, folder_name):
        chemin, _ = QFileDialog.getSaveFileName(
            self, f"Partager « {folder_name} »",
            f"{folder_name}.fbshare", "Partage Flash Bang (*.fbshare)"
        )
        if not chemin:
            return
        if not chemin.endswith(".fbshare"):
            chemin += ".fbshare"
        try:
            lists.exporter_dossier(folder_name, chemin)
        except OSError as erreur:
            QMessageBox.warning(self, "Échec de l'export", f"Impossible d'écrire le fichier :\n{erreur}")
            return
        QMessageBox.information(
            self, "Dossier partagé",
            f"« {folder_name} » a été exporté avec succès.\n\n"
            f"Envoie simplement ce fichier à ton ami — il pourra l'importer "
            f"depuis le bouton « Importer un dossier partagé »."
        )

    def _importer_fichier(self):
        chemin, _ = QFileDialog.getOpenFileName(
            self, "Importer un partage", "", "Partage Flash Bang (*.fbshare);;Tous les fichiers (*)"
        )
        if not chemin:
            return
        try:
            entete = lists.lire_entete_partage(chemin)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as erreur:
            QMessageBox.warning(
                self, "Échec de l'import",
                f"Ce fichier n'a pas pu être lu :\n{erreur}"
            )
            return

        try:
            if entete["type"] == "dossier":
                folder_name = lists.importer_dossier(chemin)
                message = f"Le dossier « {folder_name} » a été importé avec succès !"
            else:
                dialogue = DialogueDestination(self, entete["nom_partage"], entete["type"])
                if not dialogue.exec():
                    return
                folder_name, subject_name, sous_dossier = dialogue.resultat()
                if not folder_name or not subject_name:
                    QMessageBox.warning(self, "Échec de l'import", "Merci de choisir un dossier et une matière.")
                    return
                folder_name, subject_name = lists.importer_a_destination(
                    chemin, folder_name, subject_name, sous_dossier=sous_dossier
                )
                message = f"« {entete['nom_partage']} » a été importé dans « {subject_name} » ({folder_name}) !"
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as erreur:
            QMessageBox.warning(
                self, "Échec de l'import",
                f"Ce fichier n'a pas pu être importé :\n{erreur}"
            )
            return

        self._rafraichir_sidebar()
        QMessageBox.information(self, "Import réussi", message)

    # ------------------------------------------------------------------
    # Navigation entre pages
    # ------------------------------------------------------------------

    def aller_a(self, nom_page, **kwargs):
        page = self._pages[nom_page]

        # IMPORTANT : on rend la page visible AVANT de la charger. Les pages qui
        # contiennent un QWebEngineView (editeur, revision) ne peignent pas
        # correctement tant qu'elles sont cachees dans le QStackedWidget ; charger
        # leur contenu avant de les afficher provoquait un rendu en retard d'un
        # cran (le recto n'apparaissait qu'apres avoir retourne la carte).
        self._pile.setCurrentWidget(page)

        if nom_page == "accueil":
            page.rafraichir()
        elif nom_page == "calendrier":
            page.rafraichir()
        elif nom_page == "corbeille":
            page.rafraichir()
        elif nom_page == "parametres":
            page.rafraichir()
        elif nom_page == "matiere":
            page.charger(kwargs["subject_name"], flashcard_a_reveler=kwargs.get("flashcard_a_reveler"))
        elif nom_page == "editeur":
            page.charger(kwargs["flashcard_id"])
        elif nom_page == "revision":
            page.charger(
                subject_name=kwargs.get("subject_name"),
                folder_name=kwargs.get("folder_name"),
                subfolder_path=kwargs.get("subfolder_path"),
                toutes_les_flashcards=kwargs.get("toutes_les_flashcards", False),
                globale=kwargs.get("globale", False)
            )

        self._bouton_accueil.setChecked(nom_page == "accueil")
        self._bouton_calendrier.setChecked(nom_page == "calendrier")
        self._bouton_corbeille.setChecked(nom_page == "corbeille")
        self._bouton_parametres.setChecked(nom_page == "parametres")
        self._rafraichir_sidebar()

        self._page_courante = nom_page
        self._kwargs_courants = kwargs

    def closeEvent(self, event):
        lists.sauvegarder()
        super().closeEvent(event)

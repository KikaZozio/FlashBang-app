"""Page de revision : affiche le cote 1 en grand, permet de retourner la carte,
puis de valider bonne/mauvaise reponse. Boucle sur lists.demarrer_session /
prochaine_carte / repondre jusqu'a la fin de la session.

Pas d'animation : a chaque changement d'affichage, le contenu disparait
brievement puis la nouvelle face apparait directement. Delai plus court pour
un simple retournement de carte (DELAI_RETOURNEMENT_MS) que pour un vrai
changement de carte (DELAI_CHANGEMENT_MS), pour bien marquer la difference.
"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QStackedLayout

import lists
from ui import styles
from ui.bloc_renderer import RenduBlocs
from ui.image_legendee import CanevasLegende

DELAI_RETOURNEMENT_MS = 100
DELAI_CHANGEMENT_MS = 300


class ReviewPage(QWidget):
    def __init__(self, aller_a):
        super().__init__()
        self.setObjectName("page")
        self._aller_a = aller_a
        self._session = None
        self._subject_name = None
        self._folder_name = None
        self._subfolder_path = None
        self._globale = False
        self._retournee = False
        self._en_transition = False
        self._mode_carte_actuelle = None
        self._resultat_auto = None

        racine = QVBoxLayout(self)
        racine.setContentsMargins(36, 32, 36, 32)
        racine.setSpacing(16)

        entete = QHBoxLayout()
        self._titre = QLabel()
        self._titre.setObjectName("titre_page")
        entete.addWidget(self._titre, stretch=1)

        self._bouton_arriere = QPushButton("⬅️  Précédent")
        self._bouton_arriere.setObjectName("bouton_secondaire")
        self._bouton_arriere.setCursor(Qt.CursorShape.PointingHandCursor)
        self._bouton_arriere.clicked.connect(self._revenir_en_arriere)
        entete.addWidget(self._bouton_arriere)

        bouton_quitter = QPushButton("✕  Quitter la révision")
        bouton_quitter.setObjectName("bouton_secondaire")
        bouton_quitter.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_quitter.clicked.connect(self._quitter)
        entete.addWidget(bouton_quitter)
        racine.addLayout(entete)

        ligne_progression = QHBoxLayout()
        self._progression = QLabel()
        self._progression.setObjectName("sous_titre")
        ligne_progression.addWidget(self._progression, stretch=1)

        self._a_rattraper = QLabel()
        self._a_rattraper.setStyleSheet(
            f"color: {styles.ECHEC}; font-size: 13px; font-weight: 600;"
        )
        ligne_progression.addWidget(self._a_rattraper)
        racine.addLayout(ligne_progression)

        # cadre bien distinct du reste de l'ecran : bordure epaisse coloree
        self._carte = QFrame()
        self._carte.setObjectName("carte_revision")
        self._carte.setGraphicsEffect(styles.ombre_carte(rayon=26, decalage_y=8, opacite=25))

        # QStackedLayout avec un cache opaque par-dessus le rendu : le rendu
        # (QWebEngineView) met du temps a "vider" son contenu car setHtml()
        # est asynchrone -> l'ancien cote restait visible un instant. Le cache
        # est un widget Qt natif tout simple, sa mise au premier plan est
        # instantanee (independante du rendu Chromium en dessous).
        self._pile_carte = QStackedLayout(self._carte)
        self._rendu = RenduBlocs(taille_police=30)
        self._canevas_legende = CanevasLegende(mode="revision")
        self._cache = QWidget()
        self._cache.setStyleSheet(f"background-color: {styles.BG_CARD}; border-radius: 14px;")
        self._pile_carte.addWidget(self._rendu)
        self._pile_carte.addWidget(self._canevas_legende)
        self._pile_carte.addWidget(self._cache)
        racine.addWidget(self._carte, stretch=1)

        self._bouton_retourner = QPushButton("🔄  Retourner la carte")
        self._bouton_retourner.setObjectName("bouton_accent")
        self._bouton_retourner.setCursor(Qt.CursorShape.PointingHandCursor)
        self._bouton_retourner.clicked.connect(self._retourner)
        racine.addWidget(self._bouton_retourner)

        self._bouton_continuer = QPushButton("➡️  Continuer")
        self._bouton_continuer.setObjectName("bouton_accent")
        self._bouton_continuer.setCursor(Qt.CursorShape.PointingHandCursor)
        self._bouton_continuer.clicked.connect(self._continuer_apres_legende)
        self._bouton_continuer.setVisible(False)
        racine.addWidget(self._bouton_continuer)

        self._boutons_reponse = QHBoxLayout()
        bouton_mauvais = QPushButton("✕  Mauvaise réponse")
        bouton_mauvais.setObjectName("bouton_echec")
        bouton_mauvais.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_mauvais.clicked.connect(lambda: self._repondre(False))

        bouton_bon = QPushButton("✓  Bonne réponse")
        bouton_bon.setObjectName("bouton_succes")
        bouton_bon.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_bon.clicked.connect(lambda: self._repondre(True))

        self._boutons_reponse.addWidget(bouton_mauvais)
        self._boutons_reponse.addWidget(bouton_bon)
        self._widget_boutons_reponse = QWidget()
        self._widget_boutons_reponse.setLayout(self._boutons_reponse)
        racine.addWidget(self._widget_boutons_reponse)

    # ------------------------------------------------------------------
    # Chargement / affichage
    # ------------------------------------------------------------------

    def charger(self, subject_name=None, folder_name=None, subfolder_path=None,
                toutes_les_flashcards=False, globale=False):
        """subject_name : revision d'une seule matiere. folder_name : revision
        groupee de TOUTES les matieres d'un dossier en une seule session.
        subfolder_path (avec subject_name) : revision limitee a un seul
        sous-dossier/sous-sous-dossier de cette matiere. globale=True :
        revision de TOUTES les matieres de TOUS les dossiers, regroupees par
        matiere. Un seul de subject_name(+subfolder_path)/folder_name/globale
        doit etre fourni."""
        self._subject_name = subject_name
        self._folder_name = folder_name
        self._subfolder_path = subfolder_path
        self._globale = globale

        if globale:
            self._session = lists.demarrer_session_globale(toutes_les_flashcards=toutes_les_flashcards)
            nom_affiche = "toutes les matières"
        elif folder_name is not None:
            self._session = lists.demarrer_session_dossier(folder_name, toutes_les_flashcards=toutes_les_flashcards)
            nom_affiche = f"dossier « {folder_name} »"
        elif subfolder_path is not None:
            self._session = lists.demarrer_session_sousdossier(
                subject_name, subfolder_path, toutes_les_flashcards=toutes_les_flashcards
            )
            nom_affiche_sousdossier = subfolder_path.rsplit(lists.SEPARATEUR_SOUSDOSSIER, 1)[-1]
            nom_affiche = f"{subject_name} — {nom_affiche_sousdossier}"
        else:
            self._session = lists.demarrer_session(subject_name, toutes_les_flashcards=toutes_les_flashcards)
            nom_affiche = subject_name

        self._titre.setText(
            f"Révision libre — {nom_affiche}" if toutes_les_flashcards
            else f"Révision — {nom_affiche}"
        )
        self._retournee = False
        self._en_transition = False
        self._afficher_carte_courante()

    def _carte_id_et_cote(self):
        return lists.prochaine_carte(self._session)

    def _mettre_a_jour_progression(self):
        traitees = self._session["traitees"]
        total = self._session["total_initial"]
        self._progression.setText(f"{traitees} / {total} cartes")

        nombre_a_rattraper = len(self._session["a_rattraper"])
        if nombre_a_rattraper > 0:
            self._a_rattraper.setText(f"🔁 {nombre_a_rattraper} à rattraper")
            self._a_rattraper.setVisible(True)
        else:
            self._a_rattraper.setVisible(False)

        peut_revenir = self._retournee or bool(self._session["historique"])
        self._bouton_arriere.setEnabled(peut_revenir)

    def _afficher_carte_courante(self):
        carte = self._carte_id_et_cote()
        self._mettre_a_jour_progression()

        if carte is None:
            self._terminer_session()
            return

        flashcard_id, numero_cote = carte

        cote_1, cote_2, mode, derniere_revision, indice, *_ = lists.flashcards[flashcard_id]
        self._mode_carte_actuelle = mode
        self._retournee = False
        self._resultat_auto = None

        if mode == "legende_image":
            bloc = cote_1[0]
            self._canevas_legende.charger_pour_revision(bloc["chemin"], bloc["points"])
            self._bouton_retourner.setText("✓  Vérifier mes réponses")
            self._bouton_retourner.setVisible(True)
            self._widget_boutons_reponse.setVisible(False)
            self._bouton_continuer.setVisible(False)
            return

        self._blocs_recto = cote_1 if numero_cote == 1 else cote_2
        self._blocs_verso = cote_2 if numero_cote == 1 else cote_1

        self._bouton_retourner.setText("🔄  Retourner la carte")
        self._rendu.afficher(self._blocs_recto)
        self._bouton_retourner.setVisible(True)
        self._widget_boutons_reponse.setVisible(False)
        self._bouton_continuer.setVisible(False)

    def _terminer_session(self):
        if self._globale:
            self._titre.setText("Révision — toutes les matières")
            message_vide = "Tu n'as encore aucune flashcard."
        elif self._folder_name is not None:
            self._titre.setText(f"Révision — dossier « {self._folder_name} »")
            message_vide = "Ce dossier n'a aucune flashcard pour l'instant."
        elif self._subfolder_path is not None:
            nom_affiche_sousdossier = self._subfolder_path.rsplit(lists.SEPARATEUR_SOUSDOSSIER, 1)[-1]
            self._titre.setText(f"Révision — {self._subject_name} — {nom_affiche_sousdossier}")
            message_vide = "Ce sous-dossier n'a aucune flashcard pour l'instant."
        else:
            self._titre.setText(f"Révision — {self._subject_name}")
            message_vide = "Cette matière n'a aucune flashcard pour l'instant."

        if self._session["total_initial"] == 0:
            message = message_vide
        else:
            message = "Session terminée, bravo ! 🎉"
        self._mode_carte_actuelle = None
        self._rendu.afficher([{"type": "texte", "contenu": message}])
        self._pile_carte.setCurrentWidget(self._rendu)
        self._bouton_retourner.setVisible(False)
        self._widget_boutons_reponse.setVisible(False)
        self._bouton_continuer.setVisible(False)

    # ------------------------------------------------------------------
    # Delai simple (sans animation) entre 2 affichages
    # ------------------------------------------------------------------

    def _avec_delai(self, callback, delai_ms=DELAI_CHANGEMENT_MS):
        self._en_transition = True
        self._pile_carte.setCurrentWidget(self._cache)  # cache instantane, avant meme le rendu
        self._bouton_retourner.setVisible(False)
        self._widget_boutons_reponse.setVisible(False)
        self._bouton_continuer.setVisible(False)
        QTimer.singleShot(delai_ms, lambda: self._fin_delai(callback))

    def _fin_delai(self, callback):
        # RenduBlocs utilise a nouveau QWebEngineView (rendu KaTeX) : son
        # contenu se met a jour de facon ASYNCHRONE (setHtml() + un instant
        # avant que le JS ait fini de dessiner). Le _cache (widget Qt natif,
        # mis au premier plan des _avec_delai) reste devant jusqu'a la fin du
        # delai, donc l'ancien contenu n'est jamais visible entre-temps -
        # peu importe que le nouveau soit deja pret ou pas encore.
        callback()
        cible = self._canevas_legende if self._mode_carte_actuelle == "legende_image" else self._rendu
        self._pile_carte.setCurrentWidget(cible)
        self._en_transition = False

    # ------------------------------------------------------------------
    # Actions utilisateur
    # ------------------------------------------------------------------

    def _retourner(self):
        if self._en_transition:
            return

        if self._mode_carte_actuelle == "legende_image":
            self._verifier_legende()
            return

        def afficher_verso():
            self._retournee = True
            self._rendu.afficher(self._blocs_verso)
            self._bouton_retourner.setVisible(False)
            self._widget_boutons_reponse.setVisible(True)
            self._mettre_a_jour_progression()

        self._avec_delai(afficher_verso, delai_ms=DELAI_RETOURNEMENT_MS)

    def _verifier_legende(self):
        """Compare automatiquement les legendes tapees aux bonnes reponses,
        colore les champs, et fait apparaitre le bouton "Continuer" (pas de
        bonne/mauvaise reponse manuelle pour ce type de carte)."""
        reussi = self._canevas_legende.verifier()
        self._resultat_auto = reussi
        self._retournee = True
        self._bouton_retourner.setVisible(False)
        self._widget_boutons_reponse.setVisible(False)
        self._bouton_continuer.setVisible(True)
        self._mettre_a_jour_progression()

    def _continuer_apres_legende(self):
        if self._en_transition or self._resultat_auto is None:
            return
        self._repondre(self._resultat_auto)

    def _repondre(self, reussi):
        if self._en_transition:
            return
        lists.repondre(self._session, reussi)
        lists.sauvegarder()  # on sauvegarde a chaque reponse pour ne rien perdre
        self._avec_delai(self._afficher_carte_courante)

    def _revenir_en_arriere(self):
        if self._en_transition:
            return

        if self._retournee:
            if self._mode_carte_actuelle == "legende_image":
                # on retente simplement la carte avec des champs vierges
                self._avec_delai(self._afficher_carte_courante, delai_ms=DELAI_RETOURNEMENT_MS)
                return

            def afficher_recto():
                self._retournee = False
                self._rendu.afficher(self._blocs_recto)
                self._bouton_retourner.setVisible(True)
                self._widget_boutons_reponse.setVisible(False)
                self._mettre_a_jour_progression()

            self._avec_delai(afficher_recto, delai_ms=DELAI_RETOURNEMENT_MS)
            return

        if not self._session["historique"]:
            return  # rien a annuler (tout debut de la session)

        lists.annuler_derniere_reponse(self._session)
        lists.sauvegarder()
        self._avec_delai(self._afficher_carte_courante)

    def _quitter(self):
        if self._globale or self._folder_name is not None:
            self._aller_a("accueil")
        else:
            self._aller_a("matiere", subject_name=self._subject_name)

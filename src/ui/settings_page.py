"""Page "Paramètres" : personnaliser le système de répétition espacée -
les intervalles (en jours) entre chaque palier de révision, et ce qui se
passe sur une mauvaise réponse (indice remis à zéro / reculé d'un palier /
inchangé)."""

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QLineEdit, QRadioButton, QButtonGroup, QMessageBox, QScrollArea
)

import lists
from ui import styles
from version import VERSION
from mises_a_jour import VerificationMiseAJour

LIBELLES_COMPORTEMENT = {
    "zero": (
        "Repartir de zéro",
        "Une mauvaise réponse ramène la carte au tout début (1 jour). "
        "Comportement historique.",
    ),
    "un_palier": (
        "Reculer d'un seul palier",
        "Une mauvaise réponse fait juste reculer la carte d'un cran, "
        "pas jusqu'au tout début.",
    ),
    "aucun": (
        "Ne rien changer",
        "Une mauvaise réponse ne modifie pas la progression de la carte — "
        "juste une piqûre de rappel, sans pénalité.",
    ),
}


class SettingsPage(QWidget):
    def __init__(self, aller_a):
        super().__init__()
        self.setObjectName("page")
        self._aller_a = aller_a

        racine = QVBoxLayout(self)
        racine.setContentsMargins(36, 32, 36, 32)
        racine.setSpacing(16)

        titre = QLabel("⚙️  Paramètres")
        titre.setObjectName("titre_page")
        racine.addWidget(titre)

        sous_titre = QLabel("Personnalise le système de répétition espacée.")
        sous_titre.setObjectName("sous_titre")
        racine.addWidget(sous_titre)

        zone = QScrollArea()
        zone.setWidgetResizable(True)
        zone.setFrameShape(QFrame.Shape.NoFrame)
        conteneur = QWidget()
        mise_en_page = QVBoxLayout(conteneur)
        mise_en_page.setSpacing(20)
        mise_en_page.setContentsMargins(0, 8, 0, 0)

        # ------------------------------------------------------------
        # Mises a jour
        # ------------------------------------------------------------
        carte_maj = QFrame()
        carte_maj.setObjectName("carte")
        mp_maj = QVBoxLayout(carte_maj)
        mp_maj.setContentsMargins(20, 18, 20, 18)
        mp_maj.setSpacing(10)

        label_maj = QLabel(f"Mises à jour  ·  version installée : {VERSION}")
        label_maj.setStyleSheet("font-weight: 600; font-size: 14px;")
        mp_maj.addWidget(label_maj)

        self._statut_maj = QLabel(
            "Flash Bang peut vérifier automatiquement si une nouvelle version "
            "est disponible en ligne."
        )
        self._statut_maj.setWordWrap(True)
        self._statut_maj.setStyleSheet(f"color: {styles.TEXT_SECONDARY}; font-size: 12px;")
        mp_maj.addWidget(self._statut_maj)

        ligne_maj = QHBoxLayout()
        self._bouton_verifier_maj = QPushButton("🔄  Vérifier les mises à jour")
        self._bouton_verifier_maj.setObjectName("bouton_secondaire")
        self._bouton_verifier_maj.setCursor(Qt.CursorShape.PointingHandCursor)
        self._bouton_verifier_maj.clicked.connect(lambda: self._verifier_maj(silencieux=False))
        ligne_maj.addWidget(self._bouton_verifier_maj)

        self._bouton_telecharger_maj = QPushButton("⬇️  Télécharger la mise à jour")
        self._bouton_telecharger_maj.setObjectName("bouton_accent")
        self._bouton_telecharger_maj.setCursor(Qt.CursorShape.PointingHandCursor)
        self._bouton_telecharger_maj.clicked.connect(self._telecharger_maj)
        self._bouton_telecharger_maj.hide()
        ligne_maj.addWidget(self._bouton_telecharger_maj)

        ligne_maj.addStretch()
        mp_maj.addLayout(ligne_maj)

        mise_en_page.addWidget(carte_maj)

        self._url_telechargement_maj = None
        self._verificateur_maj = None

        # ------------------------------------------------------------
        # Intervalles
        # ------------------------------------------------------------
        carte_intervalles = QFrame()
        carte_intervalles.setObjectName("carte")
        mp_intervalles = QVBoxLayout(carte_intervalles)
        mp_intervalles.setContentsMargins(20, 18, 20, 18)
        mp_intervalles.setSpacing(10)

        label_intervalles = QLabel("Intervalles de révision (en jours)")
        label_intervalles.setStyleSheet("font-weight: 600; font-size: 14px;")
        mp_intervalles.addWidget(label_intervalles)

        aide_intervalles = QLabel(
            "Un nombre par palier, séparés par des virgules. Par exemple "
            "« 1, 1, 2, 3, 7, 14, 28 » veut dire : revoir la carte le "
            "lendemain, puis encore le lendemain, puis 2 jours après, etc. "
            "Le dernier nombre est repris pour chaque palier suivant, jusqu'à "
            "ce que la carte soit marquée comme apprise."
        )
        aide_intervalles.setWordWrap(True)
        aide_intervalles.setStyleSheet(f"color: {styles.TEXT_SECONDARY}; font-size: 12px;")
        mp_intervalles.addWidget(aide_intervalles)

        self._champ_intervalles = QLineEdit()
        self._champ_intervalles.setPlaceholderText("1, 1, 2, 3, 7, 14, 28")
        mp_intervalles.addWidget(self._champ_intervalles)

        ligne_reinit = QHBoxLayout()
        bouton_reinit = QPushButton("↺  Réinitialiser aux valeurs par défaut")
        bouton_reinit.setObjectName("bouton_secondaire")
        bouton_reinit.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_reinit.clicked.connect(self._reinitialiser_intervalles)
        ligne_reinit.addWidget(bouton_reinit)
        ligne_reinit.addStretch()
        mp_intervalles.addLayout(ligne_reinit)

        mise_en_page.addWidget(carte_intervalles)

        # ------------------------------------------------------------
        # Comportement en cas d'echec
        # ------------------------------------------------------------
        carte_echec = QFrame()
        carte_echec.setObjectName("carte")
        mp_echec = QVBoxLayout(carte_echec)
        mp_echec.setContentsMargins(20, 18, 20, 18)
        mp_echec.setSpacing(4)

        label_echec = QLabel("En cas de mauvaise réponse")
        label_echec.setStyleSheet("font-weight: 600; font-size: 14px;")
        mp_echec.addWidget(label_echec)
        mp_echec.addSpacing(6)

        self._groupe_echec = QButtonGroup(self)
        self._boutons_echec = {}
        for mode, (titre_option, description) in LIBELLES_COMPORTEMENT.items():
            bouton = QRadioButton(titre_option)
            bouton.setCursor(Qt.CursorShape.PointingHandCursor)
            desc = QLabel(description)
            desc.setWordWrap(True)
            desc.setStyleSheet(
                f"color: {styles.TEXT_SECONDARY}; font-size: 12px; "
                "margin-left: 24px; margin-bottom: 8px;"
            )
            self._groupe_echec.addButton(bouton)
            self._boutons_echec[mode] = bouton
            mp_echec.addWidget(bouton)
            mp_echec.addWidget(desc)

        mise_en_page.addWidget(carte_echec)

        bouton_enregistrer = QPushButton("✓  Enregistrer les paramètres")
        bouton_enregistrer.setObjectName("bouton_accent")
        bouton_enregistrer.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_enregistrer.clicked.connect(self._enregistrer)
        mise_en_page.addWidget(bouton_enregistrer)

        mise_en_page.addStretch()
        zone.setWidget(conteneur)
        racine.addWidget(zone, stretch=1)

    # ------------------------------------------------------------------

    def rafraichir(self):
        self._champ_intervalles.setText(", ".join(str(v) for v in lists.spaced_repetition))
        bouton = self._boutons_echec.get(lists.comportement_echec)
        if bouton:
            bouton.setChecked(True)

    def _verifier_maj(self, silencieux=False):
        """Lance la verification en arriere-plan (jamais bloquant). Si
        `silencieux=True` (appel automatique au demarrage de l'app), rien ne
        s'affiche en cas d'echec (pas d'internet...) ou d'absence de mise a
        jour - seule une vraie mise a jour disponible declenche un message."""
        if self._verificateur_maj is not None and self._verificateur_maj.isRunning():
            return
        self._silencieux_maj = silencieux
        if not silencieux:
            self._bouton_verifier_maj.setEnabled(False)
            self._statut_maj.setText("Vérification en cours…")
        self._verificateur_maj = VerificationMiseAJour()
        self._verificateur_maj.resultat.connect(self._sur_resultat_maj)
        self._verificateur_maj.start()

    def _sur_resultat_maj(self, info):
        silencieux = getattr(self, "_silencieux_maj", False)
        self._bouton_verifier_maj.setEnabled(True)

        if "erreur" in info:
            if not silencieux:
                self._statut_maj.setText(
                    "Impossible de vérifier pour l'instant (pas de connexion, "
                    "ou dépôt pas encore configuré)."
                )
            return

        if not info.get("disponible"):
            if not silencieux:
                self._statut_maj.setText(f"Tu as déjà la dernière version ({VERSION}).")
            return

        self._url_telechargement_maj = info.get("url")
        self._bouton_telecharger_maj.setVisible(True)
        self._statut_maj.setText(
            f"Nouvelle version disponible : {info.get('version')} "
            f"(tu as la {VERSION}). Clique sur « Télécharger la mise à jour »."
        )
        if silencieux:
            reponse = QMessageBox.question(
                self, "Mise à jour disponible",
                f"Une nouvelle version de Flash Bang est disponible : "
                f"{info.get('version')} (tu as la {VERSION}).\n\n"
                f"Veux-tu ouvrir la page de téléchargement ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reponse == QMessageBox.StandardButton.Yes:
                self._telecharger_maj()

    def _telecharger_maj(self):
        if self._url_telechargement_maj:
            QDesktopServices.openUrl(QUrl(self._url_telechargement_maj))

    def _reinitialiser_intervalles(self):
        self._champ_intervalles.setText(", ".join(str(v) for v in lists.INTERVALLES_PAR_DEFAUT))

    def _mode_echec_choisi(self):
        for mode, bouton in self._boutons_echec.items():
            if bouton.isChecked():
                return mode
        return lists.comportement_echec

    def _enregistrer(self):
        texte = self._champ_intervalles.text().strip()
        morceaux = [m.strip() for m in texte.split(",") if m.strip()]
        if not morceaux:
            QMessageBox.warning(
                self, "Intervalles invalides",
                "Indique au moins un palier (ex. : 1, 1, 2, 3, 7, 14, 28)."
            )
            return
        try:
            valeurs = [int(m) for m in morceaux]
        except ValueError:
            QMessageBox.warning(
                self, "Intervalles invalides",
                "Chaque palier doit être un nombre entier de jours "
                "(ex. : 1, 1, 2, 3, 7, 14, 28)."
            )
            return
        if any(v < 1 for v in valeurs):
            QMessageBox.warning(
                self, "Intervalles invalides",
                "Chaque palier doit être d'au moins 1 jour."
            )
            return

        lists.definir_intervalles_revision(valeurs)
        lists.definir_comportement_echec(self._mode_echec_choisi())
        QMessageBox.information(
            self, "Paramètres enregistrés",
            "Le nouveau système de répétition espacée s'appliquera à toutes "
            "les prochaines révisions."
        )

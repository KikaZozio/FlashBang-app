"""Dialogue pour personnaliser (ou revenir aux valeurs héritées) le système
de répétition espacée pour une portée précise : dossier, matière,
sous-dossier ou sous-sous-dossier. Voir lists.reglages_par_portee et la
hiérarchie de priorité dans lists._reglages_effectifs_pour."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QRadioButton, QButtonGroup, QMessageBox, QCheckBox
)

import lists
from ui import styles
from ui.settings_page import LIBELLES_COMPORTEMENT


class DialogueReglagesPortee(QDialog):
    def __init__(self, parent, titre_portee, cle_portee):
        super().__init__(parent)
        self._cle_portee = cle_portee
        self.setWindowTitle(f"Répétition espacée — {titre_portee}")
        self.setMinimumWidth(440)
        self.setStyleSheet(styles.generer_qss())

        racine = QVBoxLayout(self)
        racine.setContentsMargins(20, 20, 20, 20)
        racine.setSpacing(14)

        info = QLabel(
            f"Personnalise le système de répétition espacée pour « {titre_portee} ». "
            "S'applique à tout ce qu'elle contient, sauf si un niveau plus précis "
            "(sous-dossier, sous-sous-dossier) a lui-même un réglage personnalisé — "
            "c'est toujours le réglage le plus précis qui l'emporte."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {styles.TEXT_SECONDARY}; font-size: 12px;")
        racine.addWidget(info)

        self._case_personnaliser = QCheckBox("Utiliser des réglages personnalisés ici")
        self._case_personnaliser.setCursor(Qt.CursorShape.PointingHandCursor)
        self._case_personnaliser.toggled.connect(self._basculer_activation)
        racine.addWidget(self._case_personnaliser)

        label_intervalles = QLabel("Intervalles de révision (en jours)")
        label_intervalles.setStyleSheet("font-weight: 600; font-size: 13px;")
        racine.addWidget(label_intervalles)

        self._champ_intervalles = QLineEdit()
        self._champ_intervalles.setPlaceholderText("1, 1, 2, 3, 7, 14, 28")
        racine.addWidget(self._champ_intervalles)

        label_echec = QLabel("En cas de mauvaise réponse")
        label_echec.setStyleSheet("font-weight: 600; font-size: 13px;")
        racine.addWidget(label_echec)

        self._groupe_echec = QButtonGroup(self)
        self._boutons_echec = {}
        for mode, (titre_option, _description) in LIBELLES_COMPORTEMENT.items():
            bouton = QRadioButton(titre_option)
            bouton.setCursor(Qt.CursorShape.PointingHandCursor)
            self._groupe_echec.addButton(bouton)
            self._boutons_echec[mode] = bouton
            racine.addWidget(bouton)

        # Pre-remplissage : si cette portee a deja un reglage personnalise,
        # on l'affiche tel quel (case cochee). Sinon on affiche ce qu'elle
        # HERITERAIT (case decochee, champs desactives mais visibles).
        reglage_existant = lists.reglages_par_portee.get(cle_portee)
        if reglage_existant:
            intervalles_affiches = reglage_existant["intervalles"]
            mode_affiche = reglage_existant["comportement_echec"]
        else:
            intervalles_affiches, mode_affiche = lists.reglages_effectifs_pour_portee(cle_portee)

        self._champ_intervalles.setText(", ".join(str(v) for v in intervalles_affiches))
        bouton_a_cocher = self._boutons_echec.get(mode_affiche)
        if bouton_a_cocher:
            bouton_a_cocher.setChecked(True)

        self._case_personnaliser.setChecked(bool(reglage_existant))
        self._basculer_activation(self._case_personnaliser.isChecked())

        ligne_boutons = QHBoxLayout()
        bouton_annuler = QPushButton("Annuler")
        bouton_annuler.setObjectName("bouton_secondaire")
        bouton_annuler.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_annuler.clicked.connect(self.reject)
        ligne_boutons.addWidget(bouton_annuler)
        ligne_boutons.addStretch()
        bouton_enregistrer = QPushButton("✓  Enregistrer")
        bouton_enregistrer.setObjectName("bouton_accent")
        bouton_enregistrer.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_enregistrer.clicked.connect(self._enregistrer)
        ligne_boutons.addWidget(bouton_enregistrer)
        racine.addLayout(ligne_boutons)

    def _basculer_activation(self, actif):
        self._champ_intervalles.setEnabled(actif)
        for bouton in self._boutons_echec.values():
            bouton.setEnabled(actif)

    def _mode_echec_choisi(self):
        for mode, bouton in self._boutons_echec.items():
            if bouton.isChecked():
                return mode
        return "zero"

    def _enregistrer(self):
        if not self._case_personnaliser.isChecked():
            lists.definir_reglages_portee(self._cle_portee, None)
            self.accept()
            return

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

        lists.definir_reglages_portee(self._cle_portee, {
            "intervalles": valeurs,
            "comportement_echec": self._mode_echec_choisi(),
        })
        self.accept()

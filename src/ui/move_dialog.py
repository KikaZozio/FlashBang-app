"""Petite boite de dialogue pour deplacer une flashcard : choisir un dossier
principal, une matiere dans ce dossier, puis eventuellement un sous-dossier
(chapitre) dans cette matiere. Permet de reorganiser une flashcard entre
sous-dossiers, matieres, ou meme dossiers principaux differents."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QDialogButtonBox,
    QInputDialog
)

import lists

RACINE = "— À la racine (pas de sous-dossier) —"
NOUVEAU_SOUS_DOSSIER = "+ Nouveau sous-dossier..."


class DialogueDeplacer(QDialog):
    def __init__(self, parent, subject_name_actuelle, sous_dossier_actuel=None):
        super().__init__(parent)
        self.setWindowTitle("Déplacer la flashcard")
        self.setMinimumWidth(360)

        mise_en_page = QVBoxLayout(self)
        mise_en_page.setSpacing(10)

        mise_en_page.addWidget(QLabel("Dossier :"))
        self._combo_dossier = QComboBox()
        self._combo_dossier.addItems(list(lists.folders.keys()))
        mise_en_page.addWidget(self._combo_dossier)

        mise_en_page.addWidget(QLabel("Matière :"))
        self._combo_matiere = QComboBox()
        mise_en_page.addWidget(self._combo_matiere)

        mise_en_page.addWidget(QLabel("Sous-dossier (optionnel) :"))
        self._combo_sous_dossier = QComboBox()
        mise_en_page.addWidget(self._combo_sous_dossier)

        boutons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        boutons.accepted.connect(self.accept)
        boutons.rejected.connect(self.reject)
        mise_en_page.addWidget(boutons)

        # pre-selectionne le dossier/matiere actuels de la flashcard
        folder_name_actuel = None
        for f_name, noms_matieres in lists.folders.items():
            if subject_name_actuelle in noms_matieres:
                folder_name_actuel = f_name
                break
        if folder_name_actuel:
            self._combo_dossier.setCurrentText(folder_name_actuel)

        self._combo_dossier.currentTextChanged.connect(self._rafraichir_matieres)
        self._rafraichir_matieres(self._combo_dossier.currentText())
        if subject_name_actuelle in [self._combo_matiere.itemText(i) for i in range(self._combo_matiere.count())]:
            self._combo_matiere.setCurrentText(subject_name_actuelle)

        self._combo_matiere.currentTextChanged.connect(self._rafraichir_sous_dossiers)
        self._rafraichir_sous_dossiers(self._combo_matiere.currentText())
        if sous_dossier_actuel:
            index = self._combo_sous_dossier.findData(sous_dossier_actuel)
            if index >= 0:
                self._combo_sous_dossier.setCurrentIndex(index)

        # "activated" (et pas currentTextChanged) : ne se declenche que sur une
        # vraie interaction utilisateur, pas quand on repeuple la liste par code
        self._combo_sous_dossier.activated.connect(self._sur_choix_sous_dossier)

    def _rafraichir_matieres(self, folder_name):
        self._combo_matiere.clear()
        self._combo_matiere.addItems(list(lists.folders.get(folder_name, [])))

    def _rafraichir_sous_dossiers(self, subject_name):
        self._combo_sous_dossier.clear()
        self._combo_sous_dossier.addItem(RACINE, None)
        # chemins tries : les enfants d'un chemin apparaissent juste apres lui
        # (tri lexicographique normal), avec une indentation visuelle selon la
        # profondeur pour bien voir la hierarchie (le vrai chemin complet est
        # stocke dans les donnees de l'item, pas dans le texte affiche)
        for chemin in sorted(lists.subject_subfolders.get(subject_name, [])):
            profondeur = chemin.count(lists.SEPARATEUR_SOUSDOSSIER)
            nom_affiche = chemin.rsplit(lists.SEPARATEUR_SOUSDOSSIER, 1)[-1]
            self._combo_sous_dossier.addItem("　" * profondeur + "📂 " + nom_affiche, chemin)
        self._combo_sous_dossier.addItem(NOUVEAU_SOUS_DOSSIER, NOUVEAU_SOUS_DOSSIER)

    def _sur_choix_sous_dossier(self, index):
        if self._combo_sous_dossier.itemData(index) != NOUVEAU_SOUS_DOSSIER:
            return
        nom, ok = QInputDialog.getText(self, "Nouveau sous-dossier", "Nom du sous-dossier :")
        if ok and nom:
            # insere le nouveau nom juste avant "+ Nouveau sous-dossier...", et le selectionne
            position = self._combo_sous_dossier.count() - 1
            self._combo_sous_dossier.insertItem(position, "📂 " + nom, nom)
            self._combo_sous_dossier.setCurrentIndex(position)
        else:
            self._combo_sous_dossier.setCurrentIndex(0)  # retombe sur RACINE

    def resultat(self):
        """Renvoie (subject_name_cible, sous_dossier_cible) une fois validee.
        sous_dossier_cible est None si "a la racine" a ete choisi."""
        subject_name_cible = self._combo_matiere.currentText()
        chemin_sous_dossier = self._combo_sous_dossier.currentData()

        if chemin_sous_dossier == NOUVEAU_SOUS_DOSSIER:
            return subject_name_cible, None

        return subject_name_cible, chemin_sous_dossier

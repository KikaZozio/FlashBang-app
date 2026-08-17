"""Boite de dialogue de destination pour l'import d'une matiere, d'un
sous-dossier ou d'une selection de flashcards partagee par un ami : contrairement
a DialogueDeplacer, on peut ici choisir un dossier/une matiere/un sous-dossier
DEJA EXISTANT ou bien en creer un nouveau a la volee, sans quitter la boite."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox, QDialogButtonBox, QInputDialog
)

import lists

RACINE = "— À la racine (pas de sous-dossier) —"
NOUVEAU_DOSSIER = "+ Nouveau dossier..."
NOUVELLE_MATIERE = "+ Nouvelle matière..."
NOUVEAU_SOUS_DOSSIER = "+ Nouveau sous-dossier..."


class DialogueDestination(QDialog):
    """`nom_partage` et `type_partage` (juste pour l'affichage) decrivent ce
    qui est en train d'etre importe. resultat() renvoie (folder_name,
    subject_name, sous_dossier) une fois valide."""

    def __init__(self, parent, nom_partage, type_partage):
        super().__init__(parent)
        self.setWindowTitle("Choisir où importer")
        self.setMinimumWidth(380)

        mise_en_page = QVBoxLayout(self)
        mise_en_page.setSpacing(10)

        libelles_type = {"matiere": "la matière", "sousdossier": "le sous-dossier", "selection": "la sélection"}
        info = QLabel(f"Où placer {libelles_type.get(type_partage, 'ceci')} « {nom_partage} » ?")
        info.setWordWrap(True)
        mise_en_page.addWidget(info)

        mise_en_page.addWidget(QLabel("Dossier :"))
        self._combo_dossier = QComboBox()
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

        self._remplir_dossiers()
        self._combo_dossier.activated.connect(self._sur_choix_dossier)
        self._rafraichir_matieres(self._combo_dossier.currentText())
        self._combo_matiere.activated.connect(self._sur_choix_matiere)
        self._rafraichir_sous_dossiers(self._combo_matiere.currentText())
        self._combo_sous_dossier.activated.connect(self._sur_choix_sous_dossier)

    # -- dossier --------------------------------------------------------

    def _remplir_dossiers(self):
        self._combo_dossier.clear()
        self._combo_dossier.addItems(list(lists.folders.keys()))
        self._combo_dossier.addItem(NOUVEAU_DOSSIER)

    def _sur_choix_dossier(self, index):
        if self._combo_dossier.itemText(index) != NOUVEAU_DOSSIER:
            self._rafraichir_matieres(self._combo_dossier.currentText())
            return
        nom, ok = QInputDialog.getText(self, "Nouveau dossier", "Nom du dossier :")
        if ok and nom:
            position = self._combo_dossier.count() - 1
            self._combo_dossier.insertItem(position, nom)
            self._combo_dossier.setCurrentIndex(position)
        else:
            self._combo_dossier.setCurrentIndex(0)
        self._rafraichir_matieres(self._combo_dossier.currentText())

    # -- matiere ----------------------------------------------------------

    def _rafraichir_matieres(self, folder_name):
        self._combo_matiere.clear()
        self._combo_matiere.addItems(list(lists.folders.get(folder_name, [])))
        self._combo_matiere.addItem(NOUVELLE_MATIERE)
        self._rafraichir_sous_dossiers(self._combo_matiere.currentText())

    def _sur_choix_matiere(self, index):
        if self._combo_matiere.itemText(index) != NOUVELLE_MATIERE:
            self._rafraichir_sous_dossiers(self._combo_matiere.currentText())
            return
        nom, ok = QInputDialog.getText(self, "Nouvelle matière", "Nom de la matière :")
        if ok and nom:
            position = self._combo_matiere.count() - 1
            self._combo_matiere.insertItem(position, nom)
            self._combo_matiere.setCurrentIndex(position)
        else:
            self._combo_matiere.setCurrentIndex(0)
        self._rafraichir_sous_dossiers(self._combo_matiere.currentText())

    # -- sous-dossier -----------------------------------------------------

    def _rafraichir_sous_dossiers(self, subject_name):
        self._combo_sous_dossier.clear()
        self._combo_sous_dossier.addItem(RACINE, None)
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
            position = self._combo_sous_dossier.count() - 1
            self._combo_sous_dossier.insertItem(position, "📂 " + nom, nom)
            self._combo_sous_dossier.setCurrentIndex(position)
        else:
            self._combo_sous_dossier.setCurrentIndex(0)

    def resultat(self):
        """Renvoie (folder_name, subject_name, sous_dossier_cible)."""
        folder_name = self._combo_dossier.currentText()
        subject_name = self._combo_matiere.currentText()
        chemin_sous_dossier = self._combo_sous_dossier.currentData()
        if chemin_sous_dossier == NOUVEAU_SOUS_DOSSIER:
            chemin_sous_dossier = None
        return folder_name, subject_name, chemin_sous_dossier

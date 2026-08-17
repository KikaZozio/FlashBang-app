"""Page "Corbeille" : liste tout ce qui a ete supprime (flashcard, matiere ou
dossier), avec tout son contenu, et permet de le restaurer integralement.
Rien n'y est jamais purge automatiquement : un element n'en sort que si on le
restaure ou qu'on le supprime definitivement a la main."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QPushButton,
    QMessageBox
)

import lists
from ui import styles

ICONES_TYPE = {
    "flashcard": "🗂️",
    "matiere": "📚",
    "dossier": "📁",
    "sousdossier": "📂",
}
LIBELLES_TYPE = {
    "flashcard": "Flashcard",
    "matiere": "Matière",
    "dossier": "Dossier",
    "sousdossier": "Sous-dossier",
}


def _description_contenu(entree):
    """Petite phrase precisant ce qu'il y a a l'interieur, pour que la personne
    sache ce qu'elle restaure sans avoir a deviner."""
    type_element = entree["type"]
    donnees = entree["donnees"]
    if type_element == "flashcard":
        return "1 flashcard"
    if type_element == "matiere":
        nombre = len(donnees.get("flashcard_ids", []))
        return f"{nombre} flashcard{'s' if nombre != 1 else ''}"
    if type_element == "dossier":
        matieres = donnees.get("subjects", {})
        nombre_matieres = len(matieres)
        nombre_flashcards = sum(len(fids) for fids in matieres.values())
        return (
            f"{nombre_matieres} matière{'s' if nombre_matieres != 1 else ''}, "
            f"{nombre_flashcards} flashcard{'s' if nombre_flashcards != 1 else ''}"
        )
    if type_element == "sousdossier":
        nombre = len(donnees.get("flashcard_ids", []))
        return f"{nombre} flashcard{'s' if nombre != 1 else ''}"
    return ""


class LigneCorbeille(QFrame):
    def __init__(self, entree, on_restaurer, on_supprimer_definitivement):
        super().__init__()
        self.setObjectName("carte")
        mise_en_page = QHBoxLayout(self)
        mise_en_page.setContentsMargins(16, 12, 16, 12)

        icone = ICONES_TYPE.get(entree["type"], "🗑️")
        libelle_type = LIBELLES_TYPE.get(entree["type"], entree["type"])

        colonne = QVBoxLayout()
        nom = QLabel(f"{icone}  {entree['nom']}")
        nom.setStyleSheet("font-weight: 600; font-size: 13px;")
        colonne.addWidget(nom)

        sous = QLabel(
            f"{libelle_type}  ·  {_description_contenu(entree)}  ·  "
            f"supprimé le {entree['supprime_le'].replace('T', ' à ')}"
        )
        sous.setObjectName("sous_titre")
        colonne.addWidget(sous)

        mise_en_page.addLayout(colonne, stretch=1)

        bouton_restaurer = QPushButton("♻️  Restaurer")
        bouton_restaurer.setObjectName("bouton_succes")
        bouton_restaurer.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_restaurer.clicked.connect(lambda: on_restaurer(entree["id"]))
        mise_en_page.addWidget(bouton_restaurer)

        bouton_purger = QPushButton("❌  Supprimer définitivement")
        bouton_purger.setObjectName("bouton_echec")
        bouton_purger.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_purger.clicked.connect(lambda: on_supprimer_definitivement(entree["id"], entree["nom"]))
        mise_en_page.addWidget(bouton_purger)


class TrashPage(QWidget):
    def __init__(self, aller_a):
        super().__init__()
        self.setObjectName("page")
        self._aller_a = aller_a

        racine = QVBoxLayout(self)
        racine.setContentsMargins(36, 32, 36, 32)
        racine.setSpacing(16)

        entete = QHBoxLayout()
        colonne_titre = QVBoxLayout()
        self._titre = QLabel("🗑️  Corbeille")
        self._titre.setObjectName("titre_page")
        colonne_titre.addWidget(self._titre)
        self._sous_titre = QLabel()
        self._sous_titre.setObjectName("sous_titre")
        colonne_titre.addWidget(self._sous_titre)
        entete.addLayout(colonne_titre, stretch=1)

        self._bouton_vider = QPushButton("🧹  Vider la corbeille")
        self._bouton_vider.setObjectName("bouton_echec")
        self._bouton_vider.setCursor(Qt.CursorShape.PointingHandCursor)
        self._bouton_vider.clicked.connect(self._demander_vidage)
        entete.addWidget(self._bouton_vider, alignment=Qt.AlignmentFlag.AlignTop)

        racine.addLayout(entete)

        info = QLabel(
            "Rien n'est jamais supprimé automatiquement d'ici : un élément y "
            "reste jusqu'à ce que tu le restaures ou le supprimes définitivement."
        )
        info.setWordWrap(True)
        info.setObjectName("sous_titre")
        racine.addWidget(info)

        self._zone_defilement = QScrollArea()
        self._zone_defilement.setWidgetResizable(True)
        self._conteneur_liste = QWidget()
        self._liste = QVBoxLayout(self._conteneur_liste)
        self._liste.setSpacing(10)
        self._liste.addStretch()
        self._zone_defilement.setWidget(self._conteneur_liste)
        racine.addWidget(self._zone_defilement, stretch=1)

    def rafraichir(self):
        nombre = len(lists.corbeille)
        self._sous_titre.setText(
            "La corbeille est vide." if nombre == 0
            else f"{nombre} élément{'s' if nombre != 1 else ''} dans la corbeille."
        )
        self._bouton_vider.setEnabled(nombre > 0)

        while self._liste.count() > 1:
            item = self._liste.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # les plus recemment supprimes en premier
        for entree in reversed(lists.corbeille):
            ligne = LigneCorbeille(
                entree,
                on_restaurer=self._restaurer,
                on_supprimer_definitivement=self._demander_suppression_definitive,
            )
            self._liste.insertWidget(self._liste.count() - 1, ligne)

        if nombre == 0:
            vide = QLabel("Rien à afficher pour l'instant.")
            vide.setStyleSheet(f"color: {styles.TEXT_SECONDARY};")
            self._liste.insertWidget(0, vide)

    def _restaurer(self, id_corbeille):
        lists.restaurer_element(id_corbeille)
        self.rafraichir()

    def _demander_suppression_definitive(self, id_corbeille, nom):
        reponse = QMessageBox.warning(
            self, "Supprimer définitivement ?",
            f"⚠️ « {nom} » sera supprimé pour de bon, sans possibilité de "
            f"récupération cette fois-ci.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reponse == QMessageBox.StandardButton.Yes:
            lists.supprimer_definitivement_de_corbeille(id_corbeille)
            self.rafraichir()

    def _demander_vidage(self):
        reponse = QMessageBox.warning(
            self, "Vider la corbeille ?",
            "⚠️ Tous les éléments de la corbeille seront supprimés pour de "
            "bon, sans possibilité de récupération.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reponse == QMessageBox.StandardButton.Yes:
            lists.vider_corbeille()
            self.rafraichir()

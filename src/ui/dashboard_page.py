"""Page d'accueil : total de flashcards a reviser + une carte cliquable par matiere."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QGridLayout, QPushButton
)

import lists
from ui import styles


class CarteMatiere(QFrame):
    def __init__(self, subject_name, nombre_a_reviser, couleur_badge, on_click):
        super().__init__()
        self.setObjectName("carte")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setGraphicsEffect(styles.ombre_carte())
        self.setFixedHeight(120)

        fond, texte = couleur_badge
        mise_en_page = QVBoxLayout(self)
        mise_en_page.setContentsMargins(18, 16, 18, 16)

        badge = QLabel("●")
        badge.setStyleSheet(f"color: {texte}; font-size: 14px;")
        mise_en_page.addWidget(badge)

        nom = QLabel(subject_name)
        nom.setStyleSheet("font-size: 15px; font-weight: 600;")
        nom.setWordWrap(True)
        mise_en_page.addWidget(nom)

        mise_en_page.addStretch()

        compte = QLabel(
            f"{nombre_a_reviser} flashcard{'s' if nombre_a_reviser != 1 else ''} à réviser"
            if nombre_a_reviser > 0 else "À jour ✓"
        )
        couleur_compte = texte if nombre_a_reviser > 0 else styles.TEXT_SECONDARY
        compte.setStyleSheet(f"color: {couleur_compte}; font-size: 12px; font-weight: 600;")
        mise_en_page.addWidget(compte)

        self._on_click = on_click

    def mousePressEvent(self, event):
        self._on_click()
        super().mousePressEvent(event)


class DashboardPage(QWidget):
    def __init__(self, aller_a):
        super().__init__()
        self.setObjectName("page")
        self._aller_a = aller_a

        self._mise_en_page = QVBoxLayout(self)
        self._mise_en_page.setContentsMargins(36, 32, 36, 32)
        self._mise_en_page.setSpacing(20)

        entete = QHBoxLayout()
        colonne_titre = QVBoxLayout()
        self._titre = QLabel()
        self._titre.setObjectName("titre_page")
        colonne_titre.addWidget(self._titre)
        self._sous_titre = QLabel("Par matière")
        self._sous_titre.setObjectName("sous_titre")
        colonne_titre.addWidget(self._sous_titre)
        entete.addLayout(colonne_titre, stretch=1)

        self._bouton_reviser_tout = QPushButton("▶️  Réviser tout")
        self._bouton_reviser_tout.setObjectName("bouton_accent")
        self._bouton_reviser_tout.setCursor(Qt.CursorShape.PointingHandCursor)
        self._bouton_reviser_tout.clicked.connect(self._reviser_tout)
        entete.addWidget(self._bouton_reviser_tout, alignment=Qt.AlignmentFlag.AlignTop)

        self._mise_en_page.addLayout(entete)

        self._zone_defilement = QScrollArea()
        self._zone_defilement.setWidgetResizable(True)
        self._conteneur_grille = QWidget()
        self._grille = QGridLayout(self._conteneur_grille)
        self._grille.setSpacing(14)
        self._zone_defilement.setWidget(self._conteneur_grille)
        self._mise_en_page.addWidget(self._zone_defilement)

        self.rafraichir()

    def rafraichir(self):
        total = lists.nombre_total_flashcards_a_reviser()
        total_general = sum(len(ids) for ids in lists.subjects.values())
        if total == 0:
            self._titre.setText("Aucune flashcard à réviser aujourd'hui 🎉")
        else:
            self._titre.setText(f"{total} flashcard{'s' if total != 1 else ''} à réviser !")

        # comme sur une matiere/un dossier : reste actif meme sans rien de
        # prevu, pour permettre une revision libre de tout ce qui existe
        self._bouton_reviser_tout.setEnabled(total_general > 0)
        if total > 0:
            self._bouton_reviser_tout.setText("▶️  Réviser tout")
        elif total_general > 0:
            self._bouton_reviser_tout.setText("🔁  Réviser quand même (rien de prévu)")
        else:
            self._bouton_reviser_tout.setText("Aucune flashcard pour l'instant")

        # vider la grille existante
        while self._grille.count():
            item = self._grille.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        noms_matieres = list(lists.subjects.keys())
        colonnes = 3
        for index, subject_name in enumerate(noms_matieres):
            nombre = lists.nombre_flashcards_a_reviser(subject_name)
            couleur = styles.badge_pour(subject_name, noms_matieres)
            carte = CarteMatiere(
                subject_name, nombre, couleur,
                on_click=lambda nom=subject_name: self._aller_a("matiere", subject_name=nom)
            )
            self._grille.addWidget(carte, index // colonnes, index % colonnes)

        if not noms_matieres:
            vide = QLabel("Crée un dossier puis une matière depuis la barre latérale pour commencer.")
            vide.setStyleSheet(f"color: {styles.TEXT_SECONDARY};")
            self._grille.addWidget(vide, 0, 0)

    def _reviser_tout(self):
        rien_de_prevu = lists.nombre_total_flashcards_a_reviser() == 0
        self._aller_a("revision", globale=True, toutes_les_flashcards=rien_de_prevu)

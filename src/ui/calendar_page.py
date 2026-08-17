"""Page calendrier : vue mensuelle indiquant, pour chaque jour, le nombre de
flashcards a reviser par matiere (d'apres lists.calendrier_revisions()).

Toute la grille (en-tetes de jours + cellules) vit dans UN SEUL QGridLayout a
l'interieur d'UNE SEULE carte : ca evite les soucis d'alignement/de deformation
au redimensionnement qu'on avait avec des cartes independantes par jour."""

import calendar
import datetime as dt

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QGridLayout,
    QSizePolicy, QDialog, QScrollArea
)

import lists
from ui import styles
from ui.apercu import resume_cote

NOMS_JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
NOMS_MOIS = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
]


class DetailJourDialog(QDialog):
    def __init__(self, parent, date_cible):
        super().__init__(parent)
        self.setWindowTitle(
            f"{NOMS_JOURS[date_cible.weekday()]} {date_cible.day} "
            f"{NOMS_MOIS[date_cible.month - 1]} {date_cible.year}"
        )
        self.setMinimumSize(420, 380)
        self.setStyleSheet(styles.generer_qss())

        racine = QVBoxLayout(self)
        racine.setContentsMargins(20, 20, 20, 20)
        racine.setSpacing(12)

        detail = lists.flashcards_prevues_le(date_cible)
        noms_matieres = list(lists.subjects.keys())

        zone = QScrollArea()
        zone.setWidgetResizable(True)
        conteneur = QWidget()
        mise_en_page = QVBoxLayout(conteneur)
        mise_en_page.setSpacing(14)

        if not detail:
            vide = QLabel("Rien de prévu ce jour-là.")
            vide.setStyleSheet(f"color: {styles.TEXT_SECONDARY};")
            mise_en_page.addWidget(vide)
        else:
            for subject_name, flashcard_ids in detail.items():
                fond, texte = styles.badge_pour(subject_name, noms_matieres)

                titre_matiere = QLabel(f"●  {subject_name}  ({len(flashcard_ids)})")
                titre_matiere.setStyleSheet(f"color: {texte}; font-weight: 600; font-size: 14px;")
                mise_en_page.addWidget(titre_matiere)

                for flashcard_id in flashcard_ids:
                    cote_1 = lists.flashcards[flashcard_id][0]
                    ligne = QLabel(f"— {resume_cote(cote_1)}")
                    ligne.setStyleSheet(f"color: {styles.TEXT_PRIMARY}; font-size: 12px;")
                    ligne.setWordWrap(True)
                    mise_en_page.addWidget(ligne)

        mise_en_page.addStretch()
        zone.setWidget(conteneur)
        racine.addWidget(zone)

        bouton_fermer = QPushButton("✕  Fermer")
        bouton_fermer.setObjectName("bouton_secondaire")
        bouton_fermer.clicked.connect(self.accept)
        racine.addWidget(bouton_fermer)


class CelluleJour(QWidget):
    def __init__(self, jour, date_cellule, est_aujourdhui, comptes_par_matiere, noms_matieres, on_clic):
        super().__init__()
        self.setObjectName("cellule_jour")
        self.setMinimumHeight(92)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._on_clic = on_clic if jour is not None else None
        if self._on_clic:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip("Cliquer pour voir le détail de ce jour")

        mise_en_page = QVBoxLayout(self)
        mise_en_page.setContentsMargins(8, 6, 8, 6)
        mise_en_page.setSpacing(3)

        if jour is not None:
            numero = QLabel(str(jour))
            style_numero = "font-size: 12px; font-weight: 600;"
            style_numero += f" color: {styles.ACCENT};" if est_aujourdhui else f" color: {styles.TEXT_SECONDARY};"
            numero.setStyleSheet(style_numero)
            mise_en_page.addWidget(numero)

            for subject_name, nombre in sorted(comptes_par_matiere.items(), key=lambda x: -x[1])[:3]:
                fond, texte = styles.badge_pour(subject_name, noms_matieres)
                badge = QLabel(f"{subject_name} · {nombre}")
                badge.setStyleSheet(
                    f"background-color: {fond}; color: {texte}; font-size: 10px; "
                    f"font-weight: 600; border-radius: 5px; padding: 2px 5px;"
                )
                mise_en_page.addWidget(badge)

        mise_en_page.addStretch()

        bordure = styles.BORDER
        fond_aujourdhui = f"border: 1.5px solid {styles.ACCENT};" if est_aujourdhui else ""
        self.setStyleSheet(
            f"QWidget#cellule_jour {{ border-right: 1px solid {bordure}; "
            f"border-bottom: 1px solid {bordure}; {fond_aujourdhui} }}"
        )

    def mousePressEvent(self, event):
        if self._on_clic:
            self._on_clic()
        super().mousePressEvent(event)


class CalendarPage(QWidget):
    def __init__(self, aller_a):
        super().__init__()
        self.setObjectName("page")
        self._aller_a = aller_a
        aujourdhui = lists.date_du_jour()
        self._annee = aujourdhui.year
        self._mois = aujourdhui.month

        racine = QVBoxLayout(self)
        racine.setContentsMargins(36, 32, 36, 32)
        racine.setSpacing(16)

        titre = QLabel("Calendrier des révisions")
        titre.setObjectName("titre_page")
        racine.addWidget(titre)

        barre_nav = QHBoxLayout()
        bouton_precedent = QPushButton("←")
        bouton_precedent.setObjectName("bouton_secondaire")
        bouton_precedent.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_precedent.setToolTip("Mois précédent")
        bouton_precedent.clicked.connect(self._mois_precedent)

        self._label_mois = QLabel()
        self._label_mois.setStyleSheet("font-size: 16px; font-weight: 600;")

        bouton_suivant = QPushButton("→")
        bouton_suivant.setObjectName("bouton_secondaire")
        bouton_suivant.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_suivant.setToolTip("Mois suivant")
        bouton_suivant.clicked.connect(self._mois_suivant)

        bouton_aujourdhui = QPushButton("📅  Aujourd'hui")
        bouton_aujourdhui.setObjectName("bouton_secondaire")
        bouton_aujourdhui.setCursor(Qt.CursorShape.PointingHandCursor)
        bouton_aujourdhui.clicked.connect(self._revenir_aujourdhui)

        barre_nav.addWidget(bouton_precedent)
        barre_nav.addWidget(self._label_mois)
        barre_nav.addWidget(bouton_suivant)
        barre_nav.addStretch()
        barre_nav.addWidget(bouton_aujourdhui)
        racine.addLayout(barre_nav)

        # -- UNE seule carte contenant UNE seule grille (en-tetes + cellules) --
        self._carte = QFrame()
        self._carte.setObjectName("carte")
        carte_layout = QVBoxLayout(self._carte)
        carte_layout.setContentsMargins(0, 0, 0, 0)
        carte_layout.setSpacing(0)

        self._grille = QGridLayout()
        self._grille.setSpacing(0)
        self._grille.setContentsMargins(0, 0, 0, 0)
        for colonne in range(7):
            self._grille.setColumnStretch(colonne, 1)

        conteneur_grille = QWidget()
        conteneur_grille.setLayout(self._grille)
        carte_layout.addWidget(conteneur_grille)

        racine.addWidget(self._carte, stretch=1)

        self.rafraichir()

    def _mois_precedent(self):
        self._mois -= 1
        if self._mois == 0:
            self._mois = 12
            self._annee -= 1
        self.rafraichir()

    def _mois_suivant(self):
        self._mois += 1
        if self._mois == 13:
            self._mois = 1
            self._annee += 1
        self.rafraichir()

    def _revenir_aujourdhui(self):
        aujourdhui = lists.date_du_jour()
        self._annee, self._mois = aujourdhui.year, aujourdhui.month
        self.rafraichir()

    def _ouvrir_detail(self, date_cellule):
        DetailJourDialog(self, date_cellule).exec()

    def rafraichir(self):
        self._label_mois.setText(f"{NOMS_MOIS[self._mois - 1]} {self._annee}")

        while self._grille.count():
            item = self._grille.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        for colonne, nom in enumerate(NOMS_JOURS):
            entete = QLabel(nom[:3])
            entete.setAlignment(Qt.AlignmentFlag.AlignCenter)
            entete.setStyleSheet(
                f"color: {styles.TEXT_SECONDARY}; font-size: 11px; font-weight: 600; "
                f"padding: 8px 0; border-bottom: 1px solid {styles.BORDER};"
            )
            self._grille.addWidget(entete, 0, colonne)

        calendrier_donnees = lists.calendrier_revisions()
        noms_matieres = list(lists.subjects.keys())
        aujourdhui = lists.date_du_jour()

        semaines = calendar.Calendar(firstweekday=0).monthdayscalendar(self._annee, self._mois)
        for numero_semaine, semaine in enumerate(semaines, start=1):
            for numero_jour, jour in enumerate(semaine):
                if jour == 0:
                    cellule = CelluleJour(None, None, False, {}, noms_matieres, None)
                else:
                    date_cellule = dt.date(self._annee, self._mois, jour)
                    comptes = calendrier_donnees.get(date_cellule, {})
                    cellule = CelluleJour(
                        jour, date_cellule, date_cellule == aujourdhui, comptes, noms_matieres,
                        on_clic=lambda d=date_cellule: self._ouvrir_detail(d)
                    )
                self._grille.addWidget(cellule, numero_semaine, numero_jour)

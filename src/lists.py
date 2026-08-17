import base64
import datetime as dt
import json
import os
import random
import shutil
import sys
import uuid
from pathlib import Path
from collections import deque

# Intervalles de repetition espacee, personnalisables par l'utilisateur (voir
# definir_intervalles_revision, page "Parametres"). INTERVALLES_PAR_DEFAUT
# sert de reference pour le bouton "reinitialiser" et pour completer les
# sauvegardes faites avant l'ajout de ce reglage.
INTERVALLES_PAR_DEFAUT = [1, 1, 2, 3, 7, 14, 28]
spaced_repetition = list(INTERVALLES_PAR_DEFAUT)

# Une journee de suivi de repetition espacee ne commence qu'a 5h du matin (et
# pas a minuit) : reviser tard le soir deborde tres souvent apres minuit, ce
# qui ferait sinon changer de "jour" en pleine session et decalerait tout le
# cycle (une carte revisee a 00h30 se retrouverait planifiee 1 jour plus tot
# que si elle avait ete revisee a 23h30 la veille, alors que c'est la meme
# soiree de revision).
HEURE_DEBUT_JOURNEE = 5

def date_du_jour():
    """Date "logique" du jour courant (a utiliser PARTOUT a la place de
    dt.date.today() des qu'il s'agit de suivi de repetition espacee ou
    d'affichage coherent avec lui - ex. le calendrier) : entre minuit et
    HEURE_DEBUT_JOURNEE, on considere qu'on est encore "hier"."""
    maintenant = dt.datetime.now()
    if maintenant.hour < HEURE_DEBUT_JOURNEE:
        return (maintenant - dt.timedelta(days=1)).date()
    return maintenant.date()

# Ce qui se passe sur une mauvaise reponse (voir reviser_flashcard) :
#   "zero"      : l'indice retombe a 0 (comportement historique)
#   "un_palier" : l'indice recule d'un seul palier (jamais sous 0)
#   "aucun"     : l'indice ne bouge pas du tout (pas de penalite)
COMPORTEMENTS_ECHEC = ("zero", "un_palier", "aucun")
comportement_echec = "zero"

# Reglages de repetition espacee personnalises par PORTEE (dossier / matiere /
# sous-dossier / sous-sous-dossier), en plus des reglages globaux ci-dessus qui
# servent de valeur par defaut. {cle_portee: {"intervalles": [...],
# "comportement_echec": "..."}} - une portee absente de ce dict n'a pas de
# personnalisation (elle herite). Voir _cle_portee_*, definir_reglages_portee,
# _reglages_effectifs_pour et reglages_effectifs_pour_portee plus bas.
reglages_par_portee = {}

if getattr(sys, "frozen", False):
    chemin_appimage = os.environ.get("APPIMAGE")
    if chemin_appimage:
        # execute depuis un AppImage (Linux) : sys.executable pointe DANS le
        # systeme de fichiers squashfs monte en lecture seule et ephemere
        # (/tmp/.mount_*, efface a la fermeture) -> les donnees doivent vivre
        # A COTE du vrai fichier .AppImage, dont le chemin est fourni par
        # AppRun via la variable d'environnement $APPIMAGE. Sinon tout
        # disparaitrait a chaque fermeture de l'app.
        DOSSIER_DATA = Path(chemin_appimage).resolve().parent / "data"
    elif sys.platform == "darwin":
        # macOS : PyInstaller --windowed produit un vrai bundle .app, et
        # sys.executable pointe DANS ce bundle (FlashBang.app/Contents/MacOS/
        # FlashBang). Comme pour l'AppImage, il ne faut PAS stocker les
        # donnees a l'interieur : un .app est traite comme un paquet
        # remplacable d'un bloc (glisser-deposer une nouvelle version dans
        # Applications supprime l'ancien .app en entier) -> tout ce qui est
        # dedans disparaitrait a la moindre mise a jour. Les donnees vivent
        # donc A COTE du .app (dans le dossier qui le contient, ex.
        # Applications ou le Bureau), en remontant Contents/MacOS/FlashBang.app.
        DOSSIER_DATA = Path(sys.executable).resolve().parents[3] / "data"
    else:
        # application empaquetee en .exe (PyInstaller, Windows) ou executable
        # Linux "onedir" lance directement (pas via AppImage) : les donnees
        # doivent vivre A COTE de l'executable, PAS dans son dossier temporaire
        # d'extraction (sys._MEIPASS), qui est efface a chaque fermeture ->
        # sinon toutes les flashcards disparaitraient a chaque redemarrage.
        DOSSIER_DATA = Path(sys.executable).resolve().parent / "data"

        if sys.platform == "win32" and not (DOSSIER_DATA / "sauvegarde.json").exists():
            # Filet de securite : avant correction, FlashBang.iss utilisait
            # {autopf} comme dossier d'installation, qui pointe vers "Program
            # Files" si l'installateur tourne en administrateur, ou vers
            # AppData\Local\Programs sinon - deux emplacements DIFFERENTS
            # possibles d'une installation a l'autre selon les droits du
            # moment (antivirus, clic droit "executer en tant qu'administrateur"...).
            # La sauvegarde n'etait alors pas supprimee, juste cherchee au
            # mauvais endroit (invisible, pas perdue). Desormais fixe a
            # {localappdata} (toujours le meme chemin, voir FlashBang.iss),
            # mais on verifie ici si d'anciennes donnees existent a l'un des
            # anciens emplacements possibles, et on les recupere automatiquement.
            _candidats_anciennes_donnees = []
            for _variable_env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432", "LOCALAPPDATA"):
                _base = os.environ.get(_variable_env)
                if not _base:
                    continue
                _candidats_anciennes_donnees.append(Path(_base) / "FlashBang" / "data")
                _candidats_anciennes_donnees.append(Path(_base) / "Programs" / "FlashBang" / "data")

            for _candidat in _candidats_anciennes_donnees:
                if _candidat != DOSSIER_DATA and (_candidat / "sauvegarde.json").exists():
                    shutil.copytree(_candidat, DOSSIER_DATA, dirs_exist_ok=True)
                    break
else:
    # dossier "data" a la racine du projet (a cote de src/), cree s'il n'existe pas
    DOSSIER_DATA = Path(__file__).resolve().parent.parent / "data"
DOSSIER_DATA.mkdir(exist_ok=True)
FICHIER_SAUVEGARDE = DOSSIER_DATA / "sauvegarde.json"

# les images choisies par l'utilisateur sont copiees ici (au lieu de rester
# referencees a leur emplacement d'origine, ex. Telechargements) : une
# flashcard ne depend alors plus d'un fichier externe qui pourrait etre
# deplace/supprime, et les exports de partage restent fiables
DOSSIER_IMAGES = DOSSIER_DATA / "images"
DOSSIER_IMAGES.mkdir(exist_ok=True)

FORMAT_EXPORT_V1 = "flashbang_partage_v1"
FORMAT_EXPORT = "flashbang_partage_v2"

folders = {}
subjects = {}
# sous_dossiers d'une matiere (ex. chapitres) : {subject_name: [nom_sous_dossier, ...]}
# c'est un REGISTRE (permet d'avoir un sous-dossier vide, cree a l'avance) ;
# quelle flashcard appartient a quel sous-dossier est stocke sur la flashcard
# elle-meme (element "sous_dossier" de flashcards[fid], None = a la racine de
# la matiere, pas dans un sous-dossier).
subject_subfolders = {}
# corbeille : liste d'elements supprimes (flashcard/matiere/dossier), avec un
# instantane COMPLET de leur contenu, pour pouvoir les restaurer integralement.
# Rien n'y est jamais purge automatiquement : un element n'en sort que si on le
# restaure ou qu'on le supprime definitivement, a la main.
# entree : {"id", "type": "flashcard"|"matiere"|"dossier", "nom", "supprime_le", "donnees"}
corbeille = []
flashcards = {}

total_created_flashcards = 0

def create_folder(folder_name):
    folders[folder_name] = []
    sauvegarder()

def create_subject(folder_name, subject_name):
    folders[folder_name].append(subject_name)
    subjects[subject_name] = []
    sauvegarder()

def create_flashcard(subject_name, sous_dossier=None):
    global total_created_flashcards
    total_created_flashcards += 1
    flashcard_id = f"{subject_name}_{total_created_flashcards}"
    subjects[subject_name].append(flashcard_id)
    flashcards[flashcard_id] = [
        [],           # cote 1 : liste de blocs {"type": "texte"/"katex"/"image", "contenu": ...}
        [],           # cote 2 : meme principe
        "one_side",   # mode : "one_side" ou "two_sides"
        None,         # derniere_revision (date de la derniere revision, None si jamais revisee)
        0,            # indice dans spaced_repetition
        sous_dossier, # nom du sous-dossier (chapitre) dans la matiere, None = a la racine
        None,         # cote_valide_en_attente (cartes "two_sides" uniquement) : 1 ou 2 si ce
                       # cote a deja ete valide dans une session interrompue, en attendant
                       # l'autre ; None sinon. Voir _construire_session / repondre.
        False         # apprise : True une fois que la carte a ete revisee avec succes au
                       # DERNIER palier de spaced_repetition (28 jours) - elle ne reapparait
                       # alors plus jamais dans l'agenda/les revisions automatiques (sauf en
                       # "revision libre", ou si elle est ratee, ce qui la remet en jeu).
                       # Voir reviser_flashcard / est_a_reviser.
    ]
    sauvegarder()

def definir_mode(flashcard_id, mode):
    flashcards[flashcard_id][2] = mode
    sauvegarder()

def definir_cote(flashcard_id, numero_cote, blocs):
    """
    numero_cote : 1 ou 2
    blocs : liste de dicts {"type": "texte"|"katex"|"image", "contenu": ...}
    remplace entierement le contenu du cote concerne (l'interface envoie la liste a jour
    apres chaque ajout/suppression/reordonnancement de bloc sur la page d'edition)
    """
    flashcards[flashcard_id][numero_cote - 1] = blocs
    sauvegarder()

def definir_image_legendee(flashcard_id, chemin_image, points):
    """
    Configure une flashcard de type "image a legender" : une image sur
    laquelle on a place des points, chacun associe a la legende correcte a
    trouver. Met aussi a jour le mode de la flashcard.

    points : liste de {"x": float 0-1, "y": float 0-1, "legende": str}
             x/y sont des coordonnees RELATIVES a l'image (0 = bord gauche/haut,
             1 = bord droit/bas), pour rester valides quelle que soit la taille
             d'affichage de l'image.
    """
    flashcards[flashcard_id][0] = [{
        "type": "image_legendee",
        "chemin": chemin_image,
        "points": points,
    }]
    flashcards[flashcard_id][1] = []
    flashcards[flashcard_id][2] = "legende_image"
    sauvegarder()

def stocker_image_locale(chemin_source):
    """Copie une image choisie par l'utilisateur dans data/images/, sous un nom
    unique, et renvoie ce nouveau chemin local. A appeler des qu'une image est
    ajoutee a une flashcard (au lieu de garder le chemin d'origine tel quel)."""
    source = Path(chemin_source)
    extension = source.suffix or ".png"
    destination = DOSSIER_IMAGES / f"{uuid.uuid4().hex}{extension}"
    shutil.copyfile(source, destination)
    return str(destination)

SEPARATEUR_SOUSDOSSIER = "/"

def _enregistrer_chemin_sousdossier(subject_name, chemin):
    """Enregistre un chemin de sous-dossier (ex. "Chapitre 1/Partie A") ET tous
    ses ancetres ("Chapitre 1"), pour que la hierarchie complete existe meme si
    on cree directement un sous-sous-dossier sans etre passe par son parent."""
    subject_subfolders.setdefault(subject_name, [])
    segments = chemin.split(SEPARATEUR_SOUSDOSSIER)
    chemin_cumule = ""
    for segment in segments:
        chemin_cumule = segment if not chemin_cumule else f"{chemin_cumule}{SEPARATEUR_SOUSDOSSIER}{segment}"
        if chemin_cumule not in subject_subfolders[subject_name]:
            subject_subfolders[subject_name].append(chemin_cumule)

def create_subfolder(subject_name, subfolder_path):
    """Cree un sous-dossier (chapitre), ou un sous-sous-dossier en donnant un
    chemin du type "Chapitre 1/Partie A" (SEPARATEUR_SOUSDOSSIER = "/"). Peut
    rester vide (sert juste a exister comme destination avant qu'on y deplace
    des flashcards)."""
    _enregistrer_chemin_sousdossier(subject_name, subfolder_path)
    sauvegarder()

def supprimer_sousdossier(subject_name, subfolder_path):
    """Supprime un sous-dossier ET tous ses sous-sous-dossiers (cascade sur la
    hierarchie declaree). Aucune flashcard n'est jamais supprimee : celles qui
    etaient dans ce sous-dossier OU un de ses sous-sous-dossiers remontent a la
    racine de la matiere (sous_dossier remis a None)."""
    prefixe = f"{subfolder_path}{SEPARATEUR_SOUSDOSSIER}"

    for flashcard_id in subjects.get(subject_name, []):
        valeurs = flashcards[flashcard_id]
        sous_dossier = valeurs[5] if len(valeurs) > 5 else None
        if sous_dossier == subfolder_path or (sous_dossier and sous_dossier.startswith(prefixe)):
            valeurs[5] = None

    if subject_name in subject_subfolders:
        subject_subfolders[subject_name] = [
            chemin for chemin in subject_subfolders[subject_name]
            if chemin != subfolder_path and not chemin.startswith(prefixe)
        ]
    sauvegarder()

def flashcards_par_sousdossier(subject_name):
    """Regroupe les flashcards d'une matiere par sous-dossier EXACT (pas de
    regroupement automatique des sous-sous-dossiers dans leur parent) :
    {None: [...a la racine...], "Chapitre 1": [...], "Chapitre 1/Partie A": [...]}.
    Inclut aussi les sous-dossiers declares mais encore vides."""
    groupes = {None: []}
    for chemin in subject_subfolders.get(subject_name, []):
        groupes.setdefault(chemin, [])

    for flashcard_id in subjects.get(subject_name, []):
        sous_dossier = flashcards[flashcard_id][5] if len(flashcards[flashcard_id]) > 5 else None
        groupes.setdefault(sous_dossier, [])
        groupes[sous_dossier].append(flashcard_id)

    return groupes

def _sous_dossier_de(flashcard_id):
    valeurs = flashcards[flashcard_id]
    return valeurs[5] if len(valeurs) > 5 else None

# ---------------------------------------------------------------------------
# Reglages de repetition espacee PAR PORTEE (dossier/matiere/sous-dossier).
#
# Une carte utilise le reglage de la portee la PLUS SPECIFIQUE qui en a un :
# sous-sous-dossier > sous-dossier > matiere > dossier > global (voir
# _reglages_effectifs_pour). Chaque portee a soit un reglage COMPLET
# (intervalles + comportement_echec), soit aucun (elle herite entierement du
# niveau au-dessus - pas de fusion partielle, plus simple a comprendre).
# ---------------------------------------------------------------------------

def _dossier_de_matiere(subject_name):
    for folder_name, subject_names in folders.items():
        if subject_name in subject_names:
            return folder_name
    return None

def _matiere_de_flashcard(flashcard_id):
    for subject_name, flashcard_ids in subjects.items():
        if flashcard_id in flashcard_ids:
            return subject_name
    return None

def cle_portee_dossier(folder_name):
    return f"dossier::{folder_name}"

def cle_portee_matiere(subject_name):
    return f"matiere::{subject_name}"

def cle_portee_sousdossier(subject_name, chemin):
    return f"sousdossier::{subject_name}::{chemin}"

def _cles_parentes(cle_portee):
    """Etant donne une cle de portee, renvoie la liste ORDONNEE (du plus
    specifique au plus general) des cles parentes a consulter si cette
    portee elle-meme n'a pas de reglage personnalise. Utilisee a la fois par
    _reglages_effectifs_pour (pour une carte precise) et par
    reglages_effectifs_pour_portee (pour pre-remplir le dialogue d'edition
    avec ce qui serait herite)."""
    type_portee, *reste = cle_portee.split("::")

    if type_portee == "sousdossier":
        subject_name, chemin = reste
        segments = chemin.split(SEPARATEUR_SOUSDOSSIER)
        cles = [
            cle_portee_sousdossier(subject_name, SEPARATEUR_SOUSDOSSIER.join(segments[:profondeur]))
            for profondeur in range(len(segments) - 1, 0, -1)
        ]
        cles.append(cle_portee_matiere(subject_name))
        folder_name = _dossier_de_matiere(subject_name)
        if folder_name:
            cles.append(cle_portee_dossier(folder_name))
        return cles

    if type_portee == "matiere":
        subject_name, = reste
        folder_name = _dossier_de_matiere(subject_name)
        return [cle_portee_dossier(folder_name)] if folder_name else []

    return []  # "dossier" : rien au-dessus, sauf le global

def reglages_effectifs_pour_portee(cle_portee):
    """Reglages qui s'appliqueraient a cette portee si ELLE-MEME n'avait pas
    de personnalisation (= ce qu'elle herite du niveau au-dessus). Sert a
    pre-remplir le dialogue d'edition avant toute personnalisation."""
    for cle in _cles_parentes(cle_portee):
        reglage = reglages_par_portee.get(cle)
        if reglage:
            return list(reglage["intervalles"]), reglage["comportement_echec"]
    return list(spaced_repetition), comportement_echec

def _reglages_effectifs_pour(flashcard_id):
    """(intervalles, comportement_echec) a utiliser pour CETTE carte precise,
    en cherchant un reglage personnalise du plus specifique au plus general :
    sous-sous-dossier > sous-dossier > matiere > dossier > global."""
    subject_name = _matiere_de_flashcard(flashcard_id)
    if subject_name is None:
        return list(spaced_repetition), comportement_echec

    chemin = _sous_dossier_de(flashcard_id)
    cle_depart = (
        cle_portee_sousdossier(subject_name, chemin) if chemin
        else cle_portee_matiere(subject_name)
    )

    reglage = reglages_par_portee.get(cle_depart)
    if reglage:
        return list(reglage["intervalles"]), reglage["comportement_echec"]
    return reglages_effectifs_pour_portee(cle_depart)

def definir_reglages_portee(cle_portee, reglage):
    """reglage=None efface la personnalisation de cette portee (retour a
    l'heritage). Sinon, reglage doit etre {"intervalles": [...],
    "comportement_echec": "..."} - valide avant d'etre enregistre."""
    if reglage is None:
        if cle_portee in reglages_par_portee:
            del reglages_par_portee[cle_portee]
            sauvegarder()
        return

    intervalles = [int(v) for v in reglage["intervalles"]]
    if not intervalles:
        raise ValueError("Il faut au moins un palier.")
    if any(v < 1 for v in intervalles):
        raise ValueError("Chaque intervalle doit etre d'au moins 1 jour.")
    comportement = reglage["comportement_echec"]
    if comportement not in COMPORTEMENTS_ECHEC:
        raise ValueError(f"Mode inconnu : {comportement!r} (attendu : {COMPORTEMENTS_ECHEC})")

    reglages_par_portee[cle_portee] = {
        "intervalles": intervalles,
        "comportement_echec": comportement,
    }
    sauvegarder()

def flashcards_du_sousarbre(subject_name, subfolder_path):
    """Liste les flashcards d'un sous-dossier ET de tous ses sous-sous-dossiers
    (utilise pour compter/deplacer/supprimer tout le contenu d'un coup)."""
    prefixe = f"{subfolder_path}{SEPARATEUR_SOUSDOSSIER}"
    return [
        flashcard_id for flashcard_id in subjects.get(subject_name, [])
        if _sous_dossier_de(flashcard_id) == subfolder_path
        or (_sous_dossier_de(flashcard_id) or "").startswith(prefixe)
    ]

def deplacer_contenu_sousdossier(subject_name, subfolder_path, subject_name_cible, sous_dossier_cible):
    """Deplace TOUTES les flashcards d'un sous-dossier (et de ses sous-sous-
    dossiers) vers une autre matiere/sous-dossier, en une seule fois, puis
    retire le sous-dossier source (et ses descendants) du registre de la
    matiere d'origine. Renvoie le nombre de flashcards deplacees."""
    prefixe = f"{subfolder_path}{SEPARATEUR_SOUSDOSSIER}"
    a_deplacer = flashcards_du_sousarbre(subject_name, subfolder_path)

    for flashcard_id in a_deplacer:
        subjects[subject_name].remove(flashcard_id)
        subjects.setdefault(subject_name_cible, [])
        subjects[subject_name_cible].append(flashcard_id)

        valeurs = flashcards[flashcard_id]
        while len(valeurs) < 6:
            valeurs.append(None)
        valeurs[5] = sous_dossier_cible

    if sous_dossier_cible is not None:
        _enregistrer_chemin_sousdossier(subject_name_cible, sous_dossier_cible)

    if subject_name in subject_subfolders:
        subject_subfolders[subject_name] = [
            chemin for chemin in subject_subfolders[subject_name]
            if chemin != subfolder_path and not chemin.startswith(prefixe)
        ]

    sauvegarder()
    return len(a_deplacer)

def supprimer_sousdossier_et_flashcards(subject_name, subfolder_path):
    """Supprime un sous-dossier ET toutes ses flashcards (sous-sous-dossiers
    compris) - mais comme pour le reste de l'app, "supprimer" veut dire les
    envoyer a la Corbeille, pas les detruire pour de bon : tout peut etre
    restaure d'un coup depuis la page Corbeille."""
    prefixe = f"{subfolder_path}{SEPARATEUR_SOUSDOSSIER}"
    flashcard_ids = flashcards_du_sousarbre(subject_name, subfolder_path)
    flashcards_snapshot = {}

    for flashcard_id in flashcard_ids:
        subjects[subject_name].remove(flashcard_id)
        flashcards_snapshot[flashcard_id] = flashcards.pop(flashcard_id)

    sous_dossiers_supprimes = []
    if subject_name in subject_subfolders:
        sous_dossiers_supprimes = [
            chemin for chemin in subject_subfolders[subject_name]
            if chemin == subfolder_path or chemin.startswith(prefixe)
        ]
        subject_subfolders[subject_name] = [
            chemin for chemin in subject_subfolders[subject_name]
            if chemin not in sous_dossiers_supprimes
        ]

    nom_affiche = subfolder_path.rsplit(SEPARATEUR_SOUSDOSSIER, 1)[-1]
    _ajouter_a_corbeille(
        "sousdossier",
        nom=f"{nom_affiche} (dans « {subject_name} »)",
        donnees={
            "subject_name": subject_name,
            "chemin_base": subfolder_path,
            "sous_dossiers": sous_dossiers_supprimes,
            "flashcard_ids": flashcard_ids,
            "flashcards": flashcards_snapshot,
        },
    )
    sauvegarder()

def deplacer_flashcard(flashcard_id, subject_name_cible, sous_dossier_cible=None):
    """Deplace une flashcard vers une (autre, ou meme) matiere et/ou un
    sous-dossier (eventuellement imbrique, ex. "Chapitre 1/Partie A")
    different. Fonctionne aussi bien pour reorganiser a l'interieur d'une
    matiere qu'entre deux matieres de dossiers principaux differents."""
    for flashcard_ids in subjects.values():
        if flashcard_id in flashcard_ids:
            flashcard_ids.remove(flashcard_id)
            break

    subjects.setdefault(subject_name_cible, [])
    subjects[subject_name_cible].append(flashcard_id)

    valeurs = flashcards[flashcard_id]
    while len(valeurs) < 6:
        valeurs.append(None)
    valeurs[5] = sous_dossier_cible

    if sous_dossier_cible is not None:
        _enregistrer_chemin_sousdossier(subject_name_cible, sous_dossier_cible)

    sauvegarder()

def _est_apprise(flashcard_id):
    # champ optionnel (ajoute apres coup) : absent = pas encore concernee -> False
    valeurs = flashcards[flashcard_id]
    return bool(valeurs[7]) if len(valeurs) > 7 else False

def date_prochaine_revision(flashcard_id):
    derniere_revision = flashcards[flashcard_id][3]
    intervalles, _ = _reglages_effectifs_pour(flashcard_id)
    # clamp defensif : si l'indice stocke depassait jamais la derniere case
    # des intervalles effectifs (donnee corrompue/ancienne, intervalles
    # personnalises raccourcis depuis...), on le ramene au dernier niveau
    # valide au lieu de planter avec un IndexError.
    indice = min(flashcards[flashcard_id][4], len(intervalles) - 1)
    if derniere_revision is None:
        # jamais revisee -> a reviser des aujourd'hui
        return date_du_jour()
    return derniere_revision + dt.timedelta(days=intervalles[indice])

def est_a_reviser(flashcard_id):
    if _est_apprise(flashcard_id):
        # carte apprise (dernier palier deja reussi une fois) : elle ne
        # revient plus jamais toute seule dans l'agenda/les revisions
        # automatiques, meme si sa date theorique est depassee - sinon elle
        # reapparaitrait indefiniment tous les 28 jours. Reste accessible via
        # "revision libre" (toutes_les_flashcards=True), qui ne passe pas par
        # cette fonction.
        return False
    return date_prochaine_revision(flashcard_id) <= date_du_jour()

def reviser_flashcard(flashcard_id, reussi):
    intervalles, mode_echec = _reglages_effectifs_pour(flashcard_id)
    indice = flashcards[flashcard_id][4]
    # la toute premiere revision d'une carte (juste apres sa creation,
    # derniere_revision encore None a cet instant) ne fait PAS avancer
    # l'indice : elle doit rester a 0 pour que la PROCHAINE echeance utilise
    # intervalles[0] (1 jour par defaut). Sans ce cas particulier, l'indice
    # sautait directement a 1 des la premiere reussite, et la suite des
    # revisions sautait carrement le premier palier de 1 jour (1, 2, 3, 7,
    # 14, 28 au lieu de 1, 1, 2, 3, 7, 14, 28).
    premiere_revision = flashcards[flashcard_id][3] is None
    indice_deja_au_max = indice >= len(intervalles) - 1
    if reussi:
        # avance dans les intervalles sans depasser le dernier indice
        if not premiere_revision and not indice_deja_au_max:
            flashcards[flashcard_id][4] += 1
        elif not premiere_revision and indice_deja_au_max:
            # la carte etait DEJA au dernier palier avant cette reponse :
            # cette reussite-la est celle qui la rend "apprise" - elle ne
            # repart plus jamais automatiquement en revision.
            while len(flashcards[flashcard_id]) < 8:
                flashcards[flashcard_id].append(None)
            flashcards[flashcard_id][7] = True
    elif mode_echec != "aucun":
        # "zero" ou "un_palier" (voir COMPORTEMENTS_ECHEC) : la carte redevient
        # active, elle perd donc son statut "apprise" si elle l'avait.
        if mode_echec == "un_palier":
            flashcards[flashcard_id][4] = max(0, indice - 1)
        else:
            flashcards[flashcard_id][4] = 0
        if len(flashcards[flashcard_id]) > 7:
            flashcards[flashcard_id][7] = False
    # comportement_echec == "aucun" : rien ne bouge (ni l'indice, ni le statut
    # "apprise") - seule la date de derniere revision avance (juste en dessous).
    flashcards[flashcard_id][3] = date_du_jour()

def definir_intervalles_revision(nouveaux_intervalles):
    """Remplace la liste des intervalles (en jours) entre chaque palier de
    repetition espacee. Doit contenir au moins une valeur, toutes des entiers
    d'au moins 1 jour. Les cartes deja en cours gardent leur indice actuel
    (clampe automatiquement si la nouvelle liste est plus courte que l'ancienne,
    voir le clamp defensif dans date_prochaine_revision)."""
    global spaced_repetition
    valeurs = [int(v) for v in nouveaux_intervalles]
    if not valeurs:
        raise ValueError("Il faut au moins un palier.")
    if any(v < 1 for v in valeurs):
        raise ValueError("Chaque intervalle doit etre d'au moins 1 jour.")
    spaced_repetition = valeurs
    sauvegarder()

def reinitialiser_intervalles_revision():
    definir_intervalles_revision(INTERVALLES_PAR_DEFAUT)

def definir_comportement_echec(mode):
    global comportement_echec
    if mode not in COMPORTEMENTS_ECHEC:
        raise ValueError(f"Mode inconnu : {mode!r} (attendu : {COMPORTEMENTS_ECHEC})")
    comportement_echec = mode
    sauvegarder()

def flashcards_a_reviser(subject_name):
    return [
        flashcard_id
        for flashcard_id in subjects[subject_name]
        if est_a_reviser(flashcard_id)
    ]

def deplacer_ordre_flashcard(subject_name, flashcard_id, direction):
    """Change la place d'une flashcard dans l'ordre de rangement de sa
    matiere, EN LA PERMUTANT avec sa voisine immediate DU MEME sous-dossier
    (direction = -1 pour la faire remonter, +1 pour la faire descendre). Cet
    ordre est celui utilise a l'affichage ET pendant la revision. Renvoie True
    si un deplacement a bien eu lieu (False si la carte etait deja au bord)."""
    ids = subjects.get(subject_name, [])
    if flashcard_id not in ids:
        return False

    sous_dossier_cible = _sous_dossier_de(flashcard_id)
    indices_groupe = [i for i, fid in enumerate(ids) if _sous_dossier_de(fid) == sous_dossier_cible]
    position = indices_groupe.index(ids.index(flashcard_id))
    nouvelle_position = position + direction
    if not (0 <= nouvelle_position < len(indices_groupe)):
        return False

    i1, i2 = indices_groupe[position], indices_groupe[nouvelle_position]
    ids[i1], ids[i2] = ids[i2], ids[i1]
    sauvegarder()
    return True

def deplacer_flashcard_vers_position(subject_name, flashcard_id, cible_id, apres=False):
    """Deplace flashcard_id pour qu'elle se retrouve juste avant (ou juste
    apres, si apres=True) cible_id dans l'ordre de rangement de la matiere -
    utilise par le glisser-deposer dans l'editeur de matiere (remplace
    l'ancien systeme de fleches monter/descendre, un pas a la fois). Les deux
    cartes doivent etre du meme sous-dossier (pas verifie ici : c'est deja
    garanti par l'interface, qui n'autorise le depot qu'a l'interieur d'un
    meme groupe visuel). Renvoie True si un deplacement a bien eu lieu."""
    ids = subjects.get(subject_name, [])
    if flashcard_id not in ids or cible_id not in ids or flashcard_id == cible_id:
        return False

    ids.remove(flashcard_id)
    index_cible = ids.index(cible_id)
    ids.insert(index_cible + 1 if apres else index_cible, flashcard_id)
    sauvegarder()
    return True

def melanger_ordre_flashcards(subject_name, sous_dossier=None):
    """Melange aleatoirement l'ordre de rangement/revision des flashcards
    d'une matiere. sous_dossier=None (defaut) melange TOUS les groupes de la
    matiere (racine + chaque sous-dossier), chacun independamment : les
    cartes ne changent jamais de sous-dossier, seul leur ordre a l'interieur
    change. Passer un chemin precis pour ne melanger QUE ce groupe-la."""
    ids = subjects.get(subject_name, [])

    groupes_indices = {}
    for i, fid in enumerate(ids):
        groupes_indices.setdefault(_sous_dossier_de(fid), []).append(i)

    cibles = [sous_dossier] if sous_dossier is not None else list(groupes_indices.keys())

    for chemin in cibles:
        indices = groupes_indices.get(chemin, [])
        if len(indices) < 2:
            continue
        valeurs = [ids[i] for i in indices]
        random.shuffle(valeurs)
        for i, valeur in zip(indices, valeurs):
            ids[i] = valeur

    sauvegarder()

def nombre_flashcards_a_reviser(subject_name):
    return len(flashcards_a_reviser(subject_name))

def nombre_total_flashcards_a_reviser():
    return sum(nombre_flashcards_a_reviser(subject_name) for subject_name in subjects)

def calendrier_revisions():
    """
    Retourne {date: {subject_name: nombre}} : pour chaque date de prochaine revision
    deja programmee, le nombre de flashcards concernees par matiere.
    Ne montre que la PROCHAINE echeance connue de chaque flashcard (on ne peut pas
    predire plus loin : la suite depend de la reussite ou non a cette revision-la).
    """
    calendrier = {}
    for subject_name, flashcard_ids in subjects.items():
        for flashcard_id in flashcard_ids:
            if _est_apprise(flashcard_id):
                # apprise -> plus jamais dans l'agenda (voir est_a_reviser)
                continue
            date_rev = date_prochaine_revision(flashcard_id)
            calendrier.setdefault(date_rev, {})
            calendrier[date_rev][subject_name] = calendrier[date_rev].get(subject_name, 0) + 1
    return calendrier

def flashcards_a_reviser_le(date_cible):
    """Nombre de flashcards, par matiere, dont la prochaine revision tombe exactement le date_cible."""
    return calendrier_revisions().get(date_cible, {})

def flashcards_prevues_le(date_cible):
    """
    Detail (pas juste le nombre) des flashcards dont la prochaine revision tombe
    exactement a date_cible, regroupees par matiere : {subject_name: [flashcard_id, ...]}.
    Utilise pour afficher le contenu quand on clique sur une case du calendrier.
    """
    resultat = {}
    for subject_name, flashcard_ids in subjects.items():
        concernees = [
            flashcard_id for flashcard_id in flashcard_ids
            if not _est_apprise(flashcard_id) and date_prochaine_revision(flashcard_id) == date_cible
        ]
        if concernees:
            resultat[subject_name] = concernees
    return resultat

def _resume_flashcard_corbeille(valeurs):
    """Petit texte pour identifier une flashcard dans la corbeille."""
    for bloc in valeurs[0]:
        if bloc.get("type") == "texte" and bloc.get("contenu"):
            return bloc["contenu"][:40]
        if bloc.get("type") == "image_legendee":
            return "🏷️ Image à légender"
        if bloc.get("type") == "image":
            return "🖼 Image"
    return "Flashcard sans contenu"

def _ajouter_a_corbeille(type_element, nom, donnees):
    corbeille.append({
        "id": uuid.uuid4().hex,
        "type": type_element,
        "nom": nom,
        "supprime_le": dt.datetime.now().isoformat(timespec="seconds"),
        "donnees": donnees,
    })

def supprimer_flashcard(flashcard_id):
    """Retire une flashcard de sa matiere et l'envoie a la corbeille (rien
    n'est perdu : on peut la restaurer depuis la page Corbeille)."""
    subject_name_trouve = None
    for subject_name, flashcard_ids in subjects.items():
        if flashcard_id in flashcard_ids:
            flashcard_ids.remove(flashcard_id)
            subject_name_trouve = subject_name
            break

    valeurs = flashcards.pop(flashcard_id, None)
    if valeurs is not None:
        _ajouter_a_corbeille(
            "flashcard",
            nom=_resume_flashcard_corbeille(valeurs),
            donnees={
                "flashcard_id": flashcard_id,
                "subject_name": subject_name_trouve,
                "flashcard": valeurs,
            },
        )
    sauvegarder()

def supprimer_matiere(subject_name):
    """Retire une matiere (et toutes ses flashcards) du dossier qui la
    contient et l'envoie a la corbeille."""
    folder_name_trouve = None
    for folder_name, noms_matieres in folders.items():
        if subject_name in noms_matieres:
            noms_matieres.remove(subject_name)
            folder_name_trouve = folder_name
            break

    flashcard_ids = subjects.pop(subject_name, [])
    flashcards_snapshot = {fid: flashcards.pop(fid, None) for fid in flashcard_ids}
    sous_dossiers_snapshot = subject_subfolders.pop(subject_name, [])

    _ajouter_a_corbeille(
        "matiere",
        nom=subject_name,
        donnees={
            "subject_name": subject_name,
            "folder_name": folder_name_trouve,
            "flashcard_ids": flashcard_ids,
            "flashcards": flashcards_snapshot,
            "sous_dossiers": sous_dossiers_snapshot,
        },
    )
    sauvegarder()

def supprimer_dossier(folder_name):
    """Retire un dossier entier (toutes ses matieres et toutes leurs
    flashcards) et l'envoie a la corbeille en un seul bloc."""
    noms_matieres = list(folders.get(folder_name, []))
    flashcard_ids_par_matiere = {}
    flashcards_snapshot = {}
    sous_dossiers_par_matiere = {}

    for subject_name in noms_matieres:
        flashcard_ids = subjects.pop(subject_name, [])
        flashcard_ids_par_matiere[subject_name] = flashcard_ids
        for fid in flashcard_ids:
            flashcards_snapshot[fid] = flashcards.pop(fid, None)
        sous_dossiers_par_matiere[subject_name] = subject_subfolders.pop(subject_name, [])

    folders.pop(folder_name, None)

    _ajouter_a_corbeille(
        "dossier",
        nom=folder_name,
        donnees={
            "folder_name": folder_name,
            "subjects": flashcard_ids_par_matiere,
            "flashcards": flashcards_snapshot,
            "sous_dossiers": sous_dossiers_par_matiere,
        },
    )
    sauvegarder()

# ---------------------------------------------------------------------------
# Corbeille : restauration / suppression definitive manuelle
# ---------------------------------------------------------------------------

def _dossier_secours():
    """Dossier utilise pour reloger une matiere/flashcard restauree dont le
    dossier d'origine n'existe plus (ex. supprime entre-temps)."""
    nom = "Éléments récupérés"
    if nom not in folders:
        folders[nom] = []
    return nom

def _flashcard_id_disponible(flashcard_id):
    """Evite d'ecraser une flashcard existante qui aurait recupere le meme id
    depuis la suppression (peu probable mais possible avec total_created_flashcards)."""
    if flashcard_id not in flashcards:
        return flashcard_id
    return f"{flashcard_id}_restaure_{uuid.uuid4().hex[:6]}"

def _trouver_dans_corbeille(id_corbeille):
    for entree in corbeille:
        if entree["id"] == id_corbeille:
            return entree
    return None

def restaurer_element(id_corbeille):
    """Restaure integralement un element de la corbeille (flashcard, matiere
    ou dossier, avec tout son contenu) et le retire de la corbeille. Si son
    emplacement d'origine (matiere/dossier) n'existe plus, il est replace dans
    un dossier "Éléments récupérés" plutot que d'echouer. Renvoie True si la
    restauration a eu lieu."""
    entree = _trouver_dans_corbeille(id_corbeille)
    if entree is None:
        return False

    type_element = entree["type"]
    donnees = entree["donnees"]

    if type_element == "flashcard":
        subject_name = donnees["subject_name"]
        if subject_name not in subjects:
            dossier_secours = _dossier_secours()
            subject_name = _nom_unique(subject_name or "Matière supprimée", subjects.keys())
            create_subject(dossier_secours, subject_name)

        fid_final = _flashcard_id_disponible(donnees["flashcard_id"])
        flashcards[fid_final] = donnees["flashcard"]
        subjects[subject_name].append(fid_final)

    elif type_element == "matiere":
        folder_name = donnees["folder_name"]
        if folder_name is None or folder_name not in folders:
            folder_name = _dossier_secours() if folder_name is None else folder_name
            if folder_name not in folders:
                create_folder(folder_name)

        nom_matiere_final = _nom_unique(donnees["subject_name"], subjects.keys())
        folders[folder_name].append(nom_matiere_final)
        subjects[nom_matiere_final] = []
        if donnees.get("sous_dossiers"):
            subject_subfolders[nom_matiere_final] = list(donnees["sous_dossiers"])
        for fid in donnees["flashcard_ids"]:
            fid_final = _flashcard_id_disponible(fid)
            flashcards[fid_final] = donnees["flashcards"][fid]
            subjects[nom_matiere_final].append(fid_final)

    elif type_element == "dossier":
        folder_name = donnees["folder_name"]
        if folder_name not in folders:
            create_folder(folder_name)

        sous_dossiers_par_matiere = donnees.get("sous_dossiers", {})
        for subject_name, flashcard_ids in donnees["subjects"].items():
            nom_matiere_final = _nom_unique(subject_name, subjects.keys())
            folders[folder_name].append(nom_matiere_final)
            if sous_dossiers_par_matiere.get(subject_name):
                subject_subfolders[nom_matiere_final] = list(sous_dossiers_par_matiere[subject_name])
            subjects[nom_matiere_final] = []
            for fid in flashcard_ids:
                fid_final = _flashcard_id_disponible(fid)
                flashcards[fid_final] = donnees["flashcards"][fid]
                subjects[nom_matiere_final].append(fid_final)

    elif type_element == "sousdossier":
        subject_name = donnees["subject_name"]
        if subject_name not in subjects:
            dossier_secours = _dossier_secours()
            subject_name = _nom_unique(subject_name or "Matière supprimée", subjects.keys())
            create_subject(dossier_secours, subject_name)

        for chemin in donnees.get("sous_dossiers", []):
            _enregistrer_chemin_sousdossier(subject_name, chemin)

        for fid in donnees["flashcard_ids"]:
            fid_final = _flashcard_id_disponible(fid)
            flashcards[fid_final] = donnees["flashcards"][fid]
            subjects.setdefault(subject_name, [])
            subjects[subject_name].append(fid_final)

    corbeille[:] = [e for e in corbeille if e["id"] != id_corbeille]
    sauvegarder()
    return True

def supprimer_definitivement_de_corbeille(id_corbeille):
    """Retire un element de la corbeille sans le restaurer : cette fois, c'est
    vraiment definitif. A n'appeler qu'apres confirmation cote interface."""
    corbeille[:] = [e for e in corbeille if e["id"] != id_corbeille]
    sauvegarder()

def vider_corbeille():
    """Supprime definitivement TOUT le contenu de la corbeille."""
    corbeille.clear()
    sauvegarder()

def _construire_session(flashcards_concernees):
    """Construit le dict de session commun a demarrer_session et
    demarrer_session_dossier, a partir d'une liste de flashcard_id.

    Ordre deterministe : tous les 1ers passages (cote 1) d'abord, DANS L'ORDRE
    DE RANGEMENT des flashcards (celui qu'on voit dans la matiere, modifiable
    via deplacer_ordre_flashcard), puis TOUS les 2emes passages (cote 2) des
    cartes "two_sides" a la toute fin, dans ce meme ordre.

    "cartes_dues" fige, UNE FOIS POUR TOUTES au debut de la session, quelles
    flashcards etaient reellement a reviser aujourd'hui (ou en retard). C'est
    la seule chose qui doit influencer le suivi de repetition espacee : une
    carte montree "en avance" (via "reviser quand meme") reste visible et
    comptee dans la session, mais reussir/rater ne doit PAS faire bouger son
    indice ni sa date de prochaine revision. Sans ca, reviser en avance
    ferait quand meme progresser l'indice, ce qui n'a pas de sens.

    Une carte "two_sides" dont un cote a deja ete valide dans une session
    precedente, interrompue avant que l'autre cote le soit (cote_valide_en_attente
    persiste sur la carte, voir repondre()), ne repropose PAS ce cote deja bon :
    seul le cote manquant est inclus dans la file. resultats_partiels est
    prerempli en consequence pour que la logique de repondre() (indice qui
    n'avance que quand les deux cotes sont bons) fonctionne sans changement.
    """
    cartes_dues = {fid for fid in flashcards_concernees if est_a_reviser(fid)}

    premiers_passages = []
    seconds_passages = []
    resultats_partiels_initiaux = {}
    for flashcard_id in flashcards_concernees:
        valeurs = flashcards[flashcard_id]
        mode = valeurs[2]
        if mode == "two_sides":
            cote_deja_valide = valeurs[6] if len(valeurs) > 6 else None
            if cote_deja_valide == 1:
                seconds_passages.append((flashcard_id, 2))
                resultats_partiels_initiaux[flashcard_id] = 1
            elif cote_deja_valide == 2:
                premiers_passages.append((flashcard_id, 1))
                resultats_partiels_initiaux[flashcard_id] = 2
            else:
                premiers_passages.append((flashcard_id, 1))
                seconds_passages.append((flashcard_id, 2))
        else:
            premiers_passages.append((flashcard_id, 1))

    occurrences = premiers_passages + seconds_passages

    return {
        "file": deque(occurrences),
        "resultats_partiels": resultats_partiels_initiaux,
        "total_initial": len(occurrences),  # fixe, ne bouge pas avec les reprises
        "traitees": 0,                       # cartes definitivement validees
        "a_rattraper": set(),                # flashcard_id ayant eu au moins un echec, pas encore rattrapees
        "historique": [],                    # snapshots pour pouvoir annuler la derniere reponse
        "cartes_dues": cartes_dues,
    }

def demarrer_session(subject_name, toutes_les_flashcards=False):
    """
    Construit une session de revision pour UNE matiere.

    toutes_les_flashcards=True : revision "libre", ignore les echeances et
    inclut TOUTES les flashcards de la matiere (utile quand il n'y a rien de
    prevu mais qu'on veut quand meme s'entrainer). Repondre a une carte qui
    n'etait pas due n'affecte pas sa planification (voir _construire_session).
    """
    flashcards_concernees = (
        list(subjects.get(subject_name, [])) if toutes_les_flashcards
        else flashcards_a_reviser(subject_name)
    )
    return _construire_session(flashcards_concernees)

def demarrer_session_dossier(folder_name, toutes_les_flashcards=False):
    """
    Construit une session de revision regroupant TOUTES les matieres d'un
    dossier en une seule session (ex. reviser toute une UE d'un coup).

    toutes_les_flashcards=True : inclut toutes les flashcards de toutes les
    matieres du dossier, meme celles pas encore dues (idem demarrer_session).
    """
    flashcards_concernees = []
    for subject_name in folders.get(folder_name, []):
        if toutes_les_flashcards:
            flashcards_concernees.extend(subjects.get(subject_name, []))
        else:
            flashcards_concernees.extend(flashcards_a_reviser(subject_name))
    return _construire_session(flashcards_concernees)

def flashcards_a_reviser_sousdossier(subject_name, subfolder_path):
    return [
        flashcard_id
        for flashcard_id in flashcards_du_sousarbre(subject_name, subfolder_path)
        if est_a_reviser(flashcard_id)
    ]

def nombre_flashcards_a_reviser_sousdossier(subject_name, subfolder_path):
    return len(flashcards_a_reviser_sousdossier(subject_name, subfolder_path))

def demarrer_session_sousdossier(subject_name, subfolder_path, toutes_les_flashcards=False):
    """
    Construit une session de revision limitee a UN sous-dossier (et ses
    eventuels sous-sous-dossiers, voir flashcards_du_sousarbre) d'une matiere,
    plutot que la matiere entiere.

    toutes_les_flashcards=True : inclut toutes les flashcards du sous-arbre,
    meme celles pas encore dues (idem demarrer_session).
    """
    flashcards_concernees = (
        flashcards_du_sousarbre(subject_name, subfolder_path) if toutes_les_flashcards
        else flashcards_a_reviser_sousdossier(subject_name, subfolder_path)
    )
    return _construire_session(flashcards_concernees)

def demarrer_session_globale(toutes_les_flashcards=False):
    """
    Construit une session de revision couvrant TOUTES les matieres de TOUS
    les dossiers en une seule fois, regroupees par matiere (dans l'ordre des
    dossiers puis des matieres tel qu'affiche dans la barre laterale), chaque
    matiere gardant son propre ordre de rangement.
    """
    flashcards_concernees = []
    for folder_name in folders:
        for subject_name in folders[folder_name]:
            if toutes_les_flashcards:
                flashcards_concernees.extend(subjects.get(subject_name, []))
            else:
                flashcards_concernees.extend(flashcards_a_reviser(subject_name))
    return _construire_session(flashcards_concernees)

def prochaine_carte(session):
    """Retourne (flashcard_id, numero_cote) a afficher, ou None si la session est terminee."""
    if not session["file"]:
        return None
    return session["file"][0]

def repondre(session, reussi):
    """
    A appeler avec la reponse de l'utilisateur a la carte actuellement affichee
    (celle renvoyee par prochaine_carte).

    - mauvaise reponse : l'indice retombe a 0 IMMEDIATEMENT, et cette carte (ce
      cote precis) repart a la toute fin de la file pour etre retentee, tant
      qu'elle n'a pas ete reussie.
    - carte "one_side" reussie : indice mis a jour tout de suite.
    - carte "two_sides" reussie : l'indice n'avance que quand les DEUX cotes ont
      ete reussis (pas forcement dans la meme tentative, a cause des reprises
      sur mauvaise reponse) ; en attendant, on memorise ce cote comme "bon", A
      LA FOIS dans la session ET sur la carte elle-meme (cote_valide_en_attente),
      pour ne pas avoir a le rerepondre si la revision est quittee puis reprise
      plus tard (voir _construire_session).
    """
    flashcard_id, numero_cote = session["file"][0]  # on regarde avant de retirer, pour l'instantane

    # Instantane de tout ce que cette reponse va modifier, pour pouvoir tout
    # restaurer exactement avec annuler_derniere_reponse().
    session["historique"].append({
        "file": deque(session["file"]),
        "resultats_partiels": dict(session["resultats_partiels"]),
        "traitees": session["traitees"],
        "a_rattraper": set(session["a_rattraper"]),
        "flashcard_id": flashcard_id,
        "flashcard_snapshot": list(flashcards[flashcard_id]),
    })

    session["file"].popleft()
    mode = flashcards[flashcard_id][2]
    # seules les cartes qui etaient reellement dues au debut de la session
    # doivent voir leur planification (indice / date) bouger - voir
    # _construire_session pour le detail du raisonnement.
    carte_due = flashcard_id in session["cartes_dues"]

    if not reussi:
        if carte_due:
            reviser_flashcard(flashcard_id, False)
        session["file"].append((flashcard_id, numero_cote))
        session["a_rattraper"].add(flashcard_id)
        return

    # Chaque occurrence (chaque cote montre une fois) compte pour 1 dans
    # "traitees" des qu'elle quitte la file avec succes -> "traitees" atteint
    # exactement "total_initial" au moment ou la session se termine (le seul
    # moyen de quitter la file definitivement est de reussir l'occurrence).
    session["traitees"] += 1
    session["a_rattraper"].discard(flashcard_id)

    if mode != "two_sides":
        if carte_due:
            reviser_flashcard(flashcard_id, True)
        return

    if flashcard_id in session["resultats_partiels"]:
        # l'autre cote avait deja ete valide -> les deux cotes sont bons
        del session["resultats_partiels"][flashcard_id]
        _definir_cote_valide_en_attente(flashcard_id, None)
        if carte_due:
            reviser_flashcard(flashcard_id, True)
    else:
        # ce cote est bon, on attend que l'autre le soit aussi : on le
        # memorise sur la carte elle-meme (pas seulement dans la session) pour
        # que ca survive a une revision interrompue puis reprise plus tard.
        session["resultats_partiels"][flashcard_id] = numero_cote
        _definir_cote_valide_en_attente(flashcard_id, numero_cote)

def _definir_cote_valide_en_attente(flashcard_id, numero_cote):
    """Persiste (ou efface, avec numero_cote=None) quel cote d'une carte
    "two_sides" vient d'etre valide en attendant l'autre. Complete la carte
    a 7 elements si besoin (compatibilite avec les cartes creees avant
    l'ajout de ce champ)."""
    valeurs = flashcards[flashcard_id]
    while len(valeurs) < 7:
        valeurs.append(None)
    valeurs[6] = numero_cote

def annuler_derniere_reponse(session):
    """
    Annule la toute derniere reponse donnee via repondre() : restaure
    integralement l'etat d'avant (file, indice de la carte, compteurs).
    Renvoie (flashcard_id, numero_cote) de la carte redevenue courante, ou
    None s'il n'y a rien a annuler (tout debut de session).
    """
    if not session["historique"]:
        return None

    instantane = session["historique"].pop()
    session["file"] = instantane["file"]
    session["resultats_partiels"] = instantane["resultats_partiels"]
    session["traitees"] = instantane["traitees"]
    session["a_rattraper"] = instantane["a_rattraper"]
    flashcards[instantane["flashcard_id"]][:] = instantane["flashcard_snapshot"]

    return session["file"][0]

def _serialiser_flashcard_valeurs(valeurs):
    # json ne sait pas stocker les objets date -> on les convertit en texte (isoformat)
    # le 6e element (sous_dossier), le 7e (cote_valide_en_attente) et le 8e
    # (apprise) sont optionnels pour rester compatible avec d'anciens
    # instantanes (corbeille) crees avant leur ajout
    cote_1, cote_2, mode, derniere_revision, indice = valeurs[:5]
    sous_dossier = valeurs[5] if len(valeurs) > 5 else None
    cote_valide_en_attente = valeurs[6] if len(valeurs) > 6 else None
    apprise = bool(valeurs[7]) if len(valeurs) > 7 else False
    return [
        cote_1,
        cote_2,
        mode,
        derniere_revision.isoformat() if derniere_revision is not None else None,
        indice,
        sous_dossier,
        cote_valide_en_attente,
        apprise
    ]

def _deserialiser_flashcard_valeurs(valeurs):
    # compatibilite ascendante : les sauvegardes faites avant l'ajout des
    # sous-dossiers/cote_valide_en_attente/apprise n'ont que 5, 6 ou 7
    # elements -> on complete avec None/False
    cote_1, cote_2, mode, derniere_revision, indice = valeurs[:5]
    sous_dossier = valeurs[5] if len(valeurs) > 5 else None
    cote_valide_en_attente = valeurs[6] if len(valeurs) > 6 else None
    apprise = bool(valeurs[7]) if len(valeurs) > 7 else False
    return [
        cote_1,
        cote_2,
        mode,
        dt.date.fromisoformat(derniere_revision) if derniere_revision is not None else None,
        indice,
        sous_dossier,
        cote_valide_en_attente,
        apprise
    ]

def _serialiser_corbeille():
    resultat = []
    for entree in corbeille:
        entree = dict(entree)
        donnees = dict(entree["donnees"])
        if entree["type"] == "flashcard":
            donnees["flashcard"] = _serialiser_flashcard_valeurs(donnees["flashcard"])
        else:
            donnees["flashcards"] = {
                fid: _serialiser_flashcard_valeurs(v) for fid, v in donnees["flashcards"].items()
            }
        entree["donnees"] = donnees
        resultat.append(entree)
    return resultat

def _deserialiser_corbeille(data_corbeille):
    resultat = []
    for entree in data_corbeille:
        entree = dict(entree)
        donnees = dict(entree["donnees"])
        if entree["type"] == "flashcard":
            donnees["flashcard"] = _deserialiser_flashcard_valeurs(donnees["flashcard"])
        else:
            donnees["flashcards"] = {
                fid: _deserialiser_flashcard_valeurs(v) for fid, v in donnees["flashcards"].items()
            }
        entree["donnees"] = donnees
        resultat.append(entree)
    return resultat

def sauvegarder(chemin=FICHIER_SAUVEGARDE):
    data = {
        "folders": folders,
        "subjects": subjects,
        "subject_subfolders": subject_subfolders,
        "flashcards": {
            flashcard_id: _serialiser_flashcard_valeurs(valeurs)
            for flashcard_id, valeurs in flashcards.items()
        },
        "total_created_flashcards": total_created_flashcards,
        "corbeille": _serialiser_corbeille(),
        "spaced_repetition": spaced_repetition,
        "comportement_echec": comportement_echec,
        "reglages_par_portee": reglages_par_portee,
    }

    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def charger(chemin=FICHIER_SAUVEGARDE):
    global total_created_flashcards, spaced_repetition, comportement_echec

    if not Path(chemin).exists():
        # premiere utilisation de l'app, rien a charger
        return

    with open(chemin, "r", encoding="utf-8") as f:
        data = json.load(f)

    folders.clear()
    folders.update(data["folders"])

    subjects.clear()
    subjects.update(data["subjects"])

    subject_subfolders.clear()
    # .get(..., {}) : les sauvegardes faites avant l'ajout des sous-dossiers n'ont pas cette cle
    subject_subfolders.update(data.get("subject_subfolders", {}))

    # .get(...) : les sauvegardes faites avant l'ajout de ce reglage n'ont pas
    # ces cles -> on garde les valeurs par defaut deja en place
    intervalles_sauvegardes = data.get("spaced_repetition")
    if intervalles_sauvegardes:
        spaced_repetition = list(intervalles_sauvegardes)
    mode_echec_sauvegarde = data.get("comportement_echec")
    if mode_echec_sauvegarde in COMPORTEMENTS_ECHEC:
        comportement_echec = mode_echec_sauvegarde

    reglages_par_portee.clear()
    # .get(..., {}) : les sauvegardes faites avant l'ajout de ce reglage n'ont pas cette cle
    reglages_par_portee.update(data.get("reglages_par_portee", {}))

    flashcards.clear()
    for flashcard_id, valeurs in data["flashcards"].items():
        flashcards[flashcard_id] = _deserialiser_flashcard_valeurs(valeurs)

    total_created_flashcards = data["total_created_flashcards"]

    corbeille.clear()
    # .get(..., []) : les sauvegardes faites avant l'ajout de la corbeille n'ont pas cette cle
    corbeille.extend(_deserialiser_corbeille(data.get("corbeille", [])))

# ---------------------------------------------------------------------------
# Partage : exporter/importer un dossier entier (matieres + flashcards) dans
# un fichier autonome, pour l'envoyer a quelqu'un d'autre. Les images ne sont
# PAS juste referencees par leur chemin (qui n'existerait pas chez le
# destinataire) : elles sont integrees directement dans le fichier, encodees
# en base64.
# ---------------------------------------------------------------------------

def _bloc_vers_export(bloc):
    """Convertit un bloc pour l'export : une image (type "image" ou
    "image_legendee") est lue sur disque et integree en base64 dans le bloc,
    a la place de son chemin local (qui n'a aucun sens chez quelqu'un d'autre)."""
    bloc = dict(bloc)
    if bloc.get("type") in ("image", "image_legendee"):
        cle_chemin = "contenu" if bloc["type"] == "image" else "chemin"
        chemin = bloc.pop(cle_chemin, None)
        if chemin:
            try:
                with open(chemin, "rb") as f:
                    bloc["_image_base64"] = base64.b64encode(f.read()).decode("ascii")
                bloc["_image_extension"] = Path(chemin).suffix or ".png"
            except OSError:
                bloc["_image_base64"] = None
    return bloc

def _bloc_depuis_import(bloc):
    """Inverse de _bloc_vers_export : decode l'image integree et la sauvegarde
    dans data/images/, pour obtenir un chemin local valide sur cette machine."""
    bloc = dict(bloc)
    donnees_base64 = bloc.pop("_image_base64", None)
    extension = bloc.pop("_image_extension", ".png")
    if bloc.get("type") in ("image", "image_legendee") and donnees_base64:
        destination = DOSSIER_IMAGES / f"{uuid.uuid4().hex}{extension}"
        with open(destination, "wb") as f:
            f.write(base64.b64decode(donnees_base64))
        cle_chemin = "contenu" if bloc["type"] == "image" else "chemin"
        bloc[cle_chemin] = str(destination)
    return bloc

def _nom_unique(nom, noms_existants):
    """Renvoie `nom` tel quel s'il n'est pas deja pris, sinon "nom (2)", "nom
    (3)", etc. Utilise pour eviter les collisions de noms de matiere a l'import."""
    if nom not in noms_existants:
        return nom
    compteur = 2
    while f"{nom} ({compteur})" in noms_existants:
        compteur += 1
    return f"{nom} ({compteur})"

def _combiner_chemin_sousdossier(base, relatif):
    """Recolle un chemin relatif (tel qu'enregistre dans un export) sur un
    chemin de base (la destination choisie a l'import). Les deux peuvent etre
    None (racine)."""
    if relatif is None:
        return base
    if base is None:
        return relatif
    return f"{base}{SEPARATEUR_SOUSDOSSIER}{relatif}"

def _construire_groupe_matiere(subject_name, chemin_racine=None):
    """Construit {"cartes": [...], "sous_dossiers_relatifs": [...]} pour tout
    ou partie d'une matiere : chemin_racine=None -> toute la matiere (chemins
    inchanges) ; chemin_racine="Chapitre 1" -> seulement ce sous-dossier et ses
    sous-sous-dossiers, avec des chemins RELATIFS a chemin_racine (pret a etre
    recolle sur une autre destination a l'import, voir _combiner_chemin_sousdossier)."""
    if chemin_racine is None:
        flashcard_ids = list(subjects.get(subject_name, []))
        chemins_declares = list(subject_subfolders.get(subject_name, []))
    else:
        flashcard_ids = flashcards_du_sousarbre(subject_name, chemin_racine)
        prefixe = f"{chemin_racine}{SEPARATEUR_SOUSDOSSIER}"
        chemins_declares = [
            c for c in subject_subfolders.get(subject_name, [])
            if c == chemin_racine or c.startswith(prefixe)
        ]

    def relatif(chemin_absolu):
        if chemin_racine is None or chemin_absolu is None:
            return chemin_absolu
        if chemin_absolu == chemin_racine:
            return None
        return chemin_absolu[len(chemin_racine) + len(SEPARATEUR_SOUSDOSSIER):]

    cartes = []
    for flashcard_id in flashcard_ids:
        cote_1, cote_2, mode, derniere_revision, indice, sous_dossier, *_ = flashcards[flashcard_id]
        cartes.append({
            "cote_1": [_bloc_vers_export(b) for b in cote_1],
            "cote_2": [_bloc_vers_export(b) for b in cote_2],
            "mode": mode,
            "sous_dossier_relatif": relatif(sous_dossier),
        })

    sous_dossiers_relatifs = sorted({
        r for r in (relatif(c) for c in chemins_declares) if r is not None
    })

    return {"cartes": cartes, "sous_dossiers_relatifs": sous_dossiers_relatifs}

def _importer_cartes(cartes, sous_dossiers_relatifs, subject_name_cible, sous_dossier_base):
    """Cree les flashcards d'un groupe importe dans subject_name_cible, en
    recollant chaque chemin relatif sur sous_dossier_base (peut etre None =
    a la racine de la matiere cible)."""
    if sous_dossier_base is not None:
        # meme si le groupe importe n'a aucun sous-sous-dossier declare, la
        # destination elle-meme doit exister dans le registre (sinon elle
        # n'apparait nulle part si elle vient d'etre creee a la volee et
        # qu'aucune carte/sous-dossier enfant ne la referencerait autrement)
        create_subfolder(subject_name_cible, sous_dossier_base)

    for chemin_relatif in sous_dossiers_relatifs:
        create_subfolder(subject_name_cible, _combiner_chemin_sousdossier(sous_dossier_base, chemin_relatif))

    for carte in cartes:
        sous_dossier_final = _combiner_chemin_sousdossier(sous_dossier_base, carte.get("sous_dossier_relatif"))
        create_flashcard(subject_name_cible, sous_dossier=sous_dossier_final)
        flashcard_id = subjects[subject_name_cible][-1]

        definir_mode(flashcard_id, carte["mode"])
        definir_cote(flashcard_id, 1, [_bloc_depuis_import(b) for b in carte["cote_1"]])
        definir_cote(flashcard_id, 2, [_bloc_depuis_import(b) for b in carte["cote_2"]])

def exporter_dossier(folder_name, chemin_export):
    """Exporte un dossier entier (toutes ses matieres et flashcards, images
    comprises) dans un fichier autonome que l'on peut envoyer a quelqu'un
    d'autre. Ce fichier n'a besoin d'aucun autre fichier a cote de lui."""
    matieres_export = {}
    for subject_name in folders.get(folder_name, []):
        groupe = _construire_groupe_matiere(subject_name)
        matieres_export[subject_name] = {
            "cartes": groupe["cartes"],
            "sous_dossiers": groupe["sous_dossiers_relatifs"],
        }

    bundle = {
        "format": FORMAT_EXPORT,
        "type": "dossier",
        "nom_partage": folder_name,
        "matieres": matieres_export,
    }
    with open(chemin_export, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False)

def exporter_matiere(subject_name, chemin_export):
    """Exporte UNE SEULE matiere (avec toutes ses flashcards et sous-dossiers)
    dans un fichier autonome."""
    groupe = _construire_groupe_matiere(subject_name)
    bundle = {
        "format": FORMAT_EXPORT,
        "type": "matiere",
        "nom_partage": subject_name,
        "cartes": groupe["cartes"],
        "sous_dossiers_relatifs": groupe["sous_dossiers_relatifs"],
    }
    with open(chemin_export, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False)

def exporter_sousdossier(subject_name, chemin_sous_dossier, chemin_export):
    """Exporte UN SEUL sous-dossier (et ses eventuels sous-sous-dossiers) d'une
    matiere dans un fichier autonome. A l'import, ce sous-dossier devient la
    "racine" de ce qui est place a la destination choisie."""
    groupe = _construire_groupe_matiere(subject_name, chemin_racine=chemin_sous_dossier)
    nom_affiche = chemin_sous_dossier.rsplit(SEPARATEUR_SOUSDOSSIER, 1)[-1]
    bundle = {
        "format": FORMAT_EXPORT,
        "type": "sousdossier",
        "nom_partage": nom_affiche,
        "cartes": groupe["cartes"],
        "sous_dossiers_relatifs": groupe["sous_dossiers_relatifs"],
    }
    with open(chemin_export, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False)

def exporter_selection(flashcard_ids, chemin_export, nom_partage="Sélection de flashcards"):
    """Exporte une selection LIBRE de flashcards (potentiellement de matieres/
    sous-dossiers differents) : elles perdent leur hierarchie d'origine et
    atterrissent toutes ensemble, a plat, a la destination choisie a l'import."""
    cartes = []
    for flashcard_id in flashcard_ids:
        cote_1, cote_2, mode, derniere_revision, indice, sous_dossier, *_ = flashcards[flashcard_id]
        cartes.append({
            "cote_1": [_bloc_vers_export(b) for b in cote_1],
            "cote_2": [_bloc_vers_export(b) for b in cote_2],
            "mode": mode,
            "sous_dossier_relatif": None,
        })

    bundle = {
        "format": FORMAT_EXPORT,
        "type": "selection",
        "nom_partage": nom_partage,
        "cartes": cartes,
        "sous_dossiers_relatifs": [],
    }
    with open(chemin_export, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False)

def lire_entete_partage(chemin_fichier):
    """Lit juste l'entete d'un fichier de partage (type + nom + un resume du
    contenu), SANS rien importer : sert a l'interface pour savoir quel
    dialogue de destination proposer avant de confirmer l'import."""
    with open(chemin_fichier, "r", encoding="utf-8") as f:
        bundle = json.load(f)

    if bundle.get("format") == FORMAT_EXPORT_V1:
        nombre_cartes = sum(len(cartes) for cartes in bundle.get("matieres", {}).values())
        return {"type": "dossier", "nom_partage": bundle.get("dossier", "?"), "nombre_cartes": nombre_cartes}

    if bundle.get("format") != FORMAT_EXPORT:
        raise ValueError("Ce fichier n'est pas un fichier de partage Flash Bang reconnu.")

    type_partage = bundle.get("type", "dossier")
    if type_partage == "dossier":
        nombre_cartes = sum(len(m["cartes"]) for m in bundle.get("matieres", {}).values())
    else:
        nombre_cartes = len(bundle.get("cartes", []))

    return {"type": type_partage, "nom_partage": bundle.get("nom_partage", "?"), "nombre_cartes": nombre_cartes}

def importer_dossier(chemin_fichier, folder_name=None):
    """Importe un fichier de type "dossier" (produit par exporter_dossier, y
    compris l'ancien format v1). Fusionne dans folder_name (ou le nom d'origine
    si non precise) s'il existe deja localement, sinon le cree ; renomme
    automatiquement les matieres en cas de collision de nom. Les flashcards
    importees demarrent avec une progression de revision vierge.
    Renvoie le nom du dossier local qui contient l'import."""
    with open(chemin_fichier, "r", encoding="utf-8") as f:
        bundle = json.load(f)

    if bundle.get("format") == FORMAT_EXPORT_V1:
        return _importer_dossier_v1(bundle, folder_name)

    if bundle.get("format") != FORMAT_EXPORT or bundle.get("type") != "dossier":
        raise ValueError("Ce fichier n'est pas un export de dossier Flash Bang reconnu.")

    folder_name = folder_name or bundle["nom_partage"]
    if folder_name not in folders:
        create_folder(folder_name)

    for subject_name, groupe in bundle["matieres"].items():
        nom_final = _nom_unique(subject_name, subjects.keys())
        create_subject(folder_name, nom_final)
        _importer_cartes(groupe["cartes"], groupe.get("sous_dossiers", []), nom_final, sous_dossier_base=None)

    sauvegarder()
    return folder_name

def _importer_dossier_v1(bundle, folder_name=None):
    """Compatibilite avec les fichiers .fbshare produits avant l'ajout du
    partage granulaire (matiere/sous-dossier/selection)."""
    folder_name = folder_name or bundle["dossier"]
    if folder_name not in folders:
        create_folder(folder_name)

    sous_dossiers_bundle = bundle.get("sous_dossiers", {})

    for subject_name, cartes in bundle["matieres"].items():
        nom_final = _nom_unique(subject_name, subjects.keys())
        create_subject(folder_name, nom_final)

        for nom_sous_dossier in sous_dossiers_bundle.get(subject_name, []):
            create_subfolder(nom_final, nom_sous_dossier)

        for carte in cartes:
            create_flashcard(nom_final, sous_dossier=carte.get("sous_dossier"))
            flashcard_id = subjects[nom_final][-1]
            definir_mode(flashcard_id, carte["mode"])
            definir_cote(flashcard_id, 1, [_bloc_depuis_import(b) for b in carte["cote_1"]])
            definir_cote(flashcard_id, 2, [_bloc_depuis_import(b) for b in carte["cote_2"]])

    sauvegarder()
    return folder_name

def importer_a_destination(chemin_fichier, folder_name, subject_name, sous_dossier=None):
    """Importe un fichier de type "matiere", "sousdossier" ou "selection" a un
    endroit precis choisi par l'utilisateur : folder_name/subject_name sont
    crees s'ils n'existent pas encore (subject_name est ajoute a folder_name
    s'il n'y est pas deja). sous_dossier est le sous-dossier de destination
    DANS subject_name (None = a la racine), lui aussi cree si besoin.
    Renvoie (folder_name, subject_name)."""
    with open(chemin_fichier, "r", encoding="utf-8") as f:
        bundle = json.load(f)

    if bundle.get("format") != FORMAT_EXPORT or bundle.get("type") not in ("matiere", "sousdossier", "selection"):
        raise ValueError("Ce fichier n'est pas un export de matière/sous-dossier/sélection Flash Bang reconnu.")

    if folder_name not in folders:
        create_folder(folder_name)
    if subject_name not in folders[folder_name]:
        if subject_name in subjects:
            # la matiere existe deja mais dans un AUTRE dossier : on l'utilise
            # telle quelle plutot que d'echouer (rare, mais possible si
            # l'utilisateur a choisi une matiere existante par erreur de dossier)
            pass
        else:
            create_subject(folder_name, subject_name)

    _importer_cartes(bundle["cartes"], bundle.get("sous_dossiers_relatifs", []), subject_name, sous_dossier_base=sous_dossier)

    sauvegarder()
    return folder_name, subject_name


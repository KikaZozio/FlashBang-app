"""Verification de mise a jour, via l'API publique de GitHub Releases (pas
besoin de cle/jeton, marche pour un depot public).

Principe : la page "Releases" du depot GitHub contient toujours, en plus des
notes de version, les fichiers binaires (.exe / .dmg / .AppImage) attaches
par le workflow de construction automatique (voir .github/workflows/). Ce
module interroge juste "quelle est la derniere release ?" et compare son
numero de version a celui de l'app (version.VERSION) ; si elle est plus
recente, il propose le lien de telechargement du bon fichier pour le systeme
d'exploitation courant.

La requete reseau tourne dans un QThread (VerificationMiseAJour) pour ne
jamais geler l'interface, meme sur une connexion lente ou absente - en cas
d'echec (pas d'internet, GitHub inaccessible, depot pas encore cree...), le
signal `resultat` renvoie juste {"erreur": ...} et l'appelant peut choisir de
l'ignorer silencieusement (verification automatique au demarrage) ou de
l'afficher (bouton "Verifier les mises a jour" dans Parametres)."""

import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

from PyQt6.QtCore import QThread, pyqtSignal

from version import VERSION

# Pseudo GitHub / nom du depot ou sont publiees les releases (installateurs +
# notes de version). A adapter si le depot est un jour renomme/deplace -
# c'est la SEULE ligne a changer.
DEPOT_GITHUB = "KikaZozio/FlashBang-App"

URL_API_DERNIERE_RELEASE = f"https://api.github.com/repos/{DEPOT_GITHUB}/releases/latest"
URL_PAGE_RELEASES = f"https://github.com/{DEPOT_GITHUB}/releases/latest"


def _version_vers_tuple(texte_version):
    """"1.2.10" -> (1, 2, 10) ; permet de comparer les versions numeriquement
    (et pas alphabetiquement, ou "1.9" serait juge "plus grand" que "1.10")."""
    nombres = re.findall(r"\d+", texte_version)
    return tuple(int(n) for n in nombres) if nombres else (0,)


def version_plus_recente(version_distante, version_locale=VERSION):
    return _version_vers_tuple(version_distante) > _version_vers_tuple(version_locale)


def _extension_pour_cette_plateforme():
    systeme = platform.system()
    if systeme == "Windows":
        return ".exe"
    if systeme == "Darwin":
        return ".dmg"
    return ".AppImage"


class VerificationMiseAJour(QThread):
    """.start() lance la requete en arriere-plan ; le signal `resultat` est
    emis une seule fois avec un dict :
    - mise a jour trouvee : {"disponible": True, "version": "1.2.0",
      "notes": "...", "url": "https://.../FlashBang_Installateur.exe"}
    - deja a jour : {"disponible": False}
    - echec (pas d'internet, depot introuvable...) : {"erreur": "..."}"""

    resultat = pyqtSignal(dict)

    def run(self):
        try:
            requete = urllib.request.Request(
                URL_API_DERNIERE_RELEASE,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "FlashBang-App"},
            )
            with urllib.request.urlopen(requete, timeout=6) as reponse:
                donnees = json.loads(reponse.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as erreur:
            self.resultat.emit({"erreur": str(erreur)})
            return

        tag = donnees.get("tag_name", "") or ""
        version_distante = tag.lstrip("vV") or "0"

        if not version_plus_recente(version_distante):
            self.resultat.emit({"disponible": False})
            return

        extension = _extension_pour_cette_plateforme()
        url_telechargement = None
        for actif in donnees.get("assets", []) or []:
            if actif.get("name", "").endswith(extension):
                url_telechargement = actif.get("browser_download_url")
                break

        self.resultat.emit({
            "disponible": True,
            "version": version_distante,
            "notes": (donnees.get("body") or "").strip(),
            # a defaut de trouver le bon fichier (release pas encore
            # terminee, nom de fichier inattendu...), on renvoie au moins la
            # page de la release, ou l'ami peut choisir lui-meme
            "url": url_telechargement or donnees.get("html_url") or URL_PAGE_RELEASES,
        })


# --------------------------------------------------------------------------
# Telechargement + installation automatique (derriere confirmation de
# l'utilisateur - voir SettingsPage._sur_resultat_maj)
# --------------------------------------------------------------------------

def _mode_installe():
    """True seulement si l'app tourne depuis un vrai executable construit
    (PyInstaller), PAS depuis le code source (python src/main.py). Lancer un
    installateur ou remplacer un fichier n'a de sens que dans le premier cas -
    en developpement, on se contente d'ouvrir le lien de telechargement."""
    return getattr(sys, "frozen", False)


class TelechargementMiseAJour(QThread):
    """Telecharge le fichier de mise a jour vers un dossier temporaire, avec
    suivi de progression. Signaux :
    - progression(int) : pourcentage 0-100 (ou -1 si la taille totale est
      inconnue, auquel cas l'appelant peut juste afficher un indicateur
      indetermine)
    - termine(dict) : {"chemin": "/chemin/vers/fichier"} ou {"erreur": "..."}
    """

    progression = pyqtSignal(int)
    termine = pyqtSignal(dict)

    def __init__(self, url):
        super().__init__()
        self._url = url

    def run(self):
        try:
            nom_fichier = os.path.basename(urllib.parse.urlparse(self._url).path) or "mise_a_jour"
            chemin_cible = os.path.join(tempfile.gettempdir(), nom_fichier)

            requete = urllib.request.Request(self._url, headers={"User-Agent": "FlashBang-App"})
            with urllib.request.urlopen(requete, timeout=15) as reponse:
                taille_totale = int(reponse.headers.get("Content-Length", 0))
                telecharge = 0
                with open(chemin_cible, "wb") as fichier:
                    while True:
                        morceau = reponse.read(1024 * 256)
                        if not morceau:
                            break
                        fichier.write(morceau)
                        telecharge += len(morceau)
                        if taille_totale:
                            self.progression.emit(int(telecharge * 100 / taille_totale))
                        else:
                            self.progression.emit(-1)
        except (urllib.error.URLError, TimeoutError, OSError) as erreur:
            self.termine.emit({"erreur": str(erreur)})
            return

        self.termine.emit({"chemin": chemin_cible})


def installer_mise_a_jour_telechargee(chemin_fichier):
    """A appeler une fois le fichier telecharge (voir TelechargementMiseAJour)
    et l'utilisateur ayant confirme vouloir l'installer. Renvoie un message a
    afficher a l'utilisateur, et gere elle-meme le lancement de l'etape
    suivante (installateur Windows, remplacement de l'AppImage, ouverture du
    .dmg) - PAS d'installation reellement silencieuse : sur Windows/macOS,
    une fenetre d'installation/Finder s'ouvre toujours, pour que la personne
    garde le controle de ce qui se passe sur son ordinateur.

    Renvoie (message, doit_fermer_app) : `doit_fermer_app` indique si l'appli
    doit se fermer tout de suite pour laisser la place a la mise a jour."""
    systeme = platform.system()

    if not _mode_installe():
        # lance depuis le code source : rien a "installer" au sens executable,
        # on se contente de dire ou le fichier a ete telecharge
        return (
            f"Fichier téléchargé ici (mode développement, pas d'installation "
            f"automatique) :\n{chemin_fichier}",
            False,
        )

    if systeme == "Windows":
        # lance l'installateur (Inno Setup) ; il se charge lui-meme de fermer
        # l'app en cours si besoin (CloseApplications=yes, voir FlashBang.iss)
        # puis de la relancer a la fin - Flash Bang doit donc se fermer
        # maintenant pour ne pas bloquer le remplacement de ses propres fichiers
        subprocess.Popen([chemin_fichier], shell=False)
        return ("L'installateur de la mise à jour va s'ouvrir. Flash Bang va se fermer.", True)

    if systeme == "Darwin":
        # pas de mode silencieux possible sans signature Apple (payante) :
        # on ouvre le .dmg telecharge dans le Finder (equivalent d'un
        # double-clic), la personne n'a plus qu'a glisser l'app dans
        # Applications comme d'habitude - au moins, elle n'a plus besoin
        # d'aller chercher le fichier elle-meme sur GitHub
        subprocess.Popen(["open", chemin_fichier])
        return (
            "Le fichier de mise à jour (.dmg) vient de s'ouvrir dans le Finder. "
            "Glisse Flash Bang dans le dossier Applications pour terminer, "
            "comme la première fois.",
            False,
        )

    # Linux (AppImage) : remplacement direct du fichier en place, possible
    # car Linux autorise de remplacer un executable pendant qu'il tourne
    # (contrairement a Windows) - on ne le fait que si on arrive a retrouver
    # le VRAI fichier .AppImage d'origine (variable d'environnement APPIMAGE,
    # positionnee automatiquement par le runtime AppImage au lancement)
    chemin_appimage_actuel = os.environ.get("APPIMAGE")
    if not chemin_appimage_actuel:
        return (
            f"Fichier téléchargé ici :\n{chemin_fichier}\n\n"
            f"Remplace ton ancien fichier .AppImage par celui-ci (et rends-le "
            f"exécutable si besoin).",
            False,
        )

    try:
        os.chmod(chemin_fichier, 0o755)
        os.replace(chemin_fichier, chemin_appimage_actuel)
    except OSError as erreur:
        return (f"Le remplacement automatique a échoué ({erreur}).\n"
                 f"Le nouveau fichier est ici : {chemin_fichier}", False)

    # relance automatiquement la nouvelle version, puis ferme l'ancienne
    subprocess.Popen([chemin_appimage_actuel])
    return ("Mise à jour installée. Flash Bang va redémarrer.", True)

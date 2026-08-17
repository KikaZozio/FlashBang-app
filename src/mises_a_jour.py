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
import platform
import re
import urllib.error
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

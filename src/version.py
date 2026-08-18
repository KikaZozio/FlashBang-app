"""Numero de version de Flash Bang - SOURCE UNIQUE DE VERITE.

A incrementer avant chaque nouvelle publication (voir DISTRIBUTION.md,
section "Publier une nouvelle version"). Cette meme valeur est :
- affichee dans l'app (page Parametres) ;
- comparee a la derniere version publiee sur GitHub par le verificateur de
  mise a jour (voir mises_a_jour.py) ;
- reprise automatiquement par build_installateur.bat pour l'installateur
  Windows (transmise a Inno Setup via la variable d'environnement
  FLASHBANG_VERSION, lue dans FlashBang.iss) ;
- ce que tu dois transformer en tag Git (prefixe "v", ex. "v1.1.0") pour
  declencher une publication automatique via GitHub Actions.

Format libre mais recommande : MAJEUR.MINEUR.CORRECTIF (ex. "1.2.0"), suivi
du versionnage semantique habituel.
"""

VERSION = "1.1.1"

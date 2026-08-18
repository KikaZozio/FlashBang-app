# Distribuer Flash Bang

Quatre façons de partager l'app selon le système de tes amis :

- **L'installateur Windows** (`FlashBang_Installateur.exe`) — recommandé sous Windows. Tes amis double-cliquent, suivent un assistant graphique classique (Suivant → Suivant → Installer), et récupèrent une icône dans le menu Démarrer et sur le Bureau, avec un vrai désinstalleur dans "Applications". Aucune invite de commande, jamais.
- **L'exécutable Windows portable** (dossier `FlashBang\`) — plus simple à fabriquer pour toi (une seule étape), mais tes amis doivent décompresser un dossier et double-cliquer sur `FlashBang.exe` à chaque fois, sans raccourci ni désinstalleur propre.
- **L'AppImage** (`FlashBang-x86_64.AppImage`) — pour tes amis sous Linux. Un seul fichier, fonctionne sur (quasiment) toutes les distributions sans rien installer ni droits admin.
- **Le `.dmg`** (`FlashBang.dmg`) — pour tes amis sous macOS. Ils l'ouvrent et glissent `FlashBang.app` dans leur dossier Applications, comme n'importe quelle app Mac.

## Fabriquer l'installateur Windows (recommandé sous Windows)

Il faut construire **sur Windows** (ça ne peut pas se faire depuis ailleurs) :

1. **Une seule fois**, installe Inno Setup (gratuit, ~5 Mo) : [jrsoftware.org/isdl.php](https://jrsoftware.org/isdl.php) — laisse toutes les options par défaut.
2. Double-clique sur `build_installateur.bat`, à la racine du projet.
3. Laisse-le installer les dépendances, construire l'app, puis fabriquer l'installateur — ça prend quelques minutes la première fois.
4. Une fois terminé, ton installateur est dans `installer_output\FlashBang_Installateur.exe`.

Si tu lances `build_installateur.bat` avant d'avoir installé Inno Setup, il te le signale simplement et te dit quoi faire — pas d'erreur cryptique.

## Fabriquer juste l'exécutable Windows portable (alternative plus simple)

1. Double-clique sur `build_exe.bat`, à la racine du projet.
2. Laisse-le installer les dépendances puis construire.
3. Ton application est dans le dossier `dist\FlashBang\` — compresse ce dossier entier en `.zip` avant de l'envoyer (clic droit → Envoyer vers → Dossier compressé). Tes amis décompressent le `.zip` et lancent `FlashBang.exe` à l'intérieur, sans rien installer — mais il faut garder tous les fichiers du dossier ensemble (pas juste l'exe tout seul).

## Fabriquer l'AppImage (pour tes amis sous Linux)

Contrairement aux scripts Windows, celui-ci se construit **depuis Linux** (impossible depuis Windows) :

1. Ouvre un terminal à la racine du projet et lance : `bash build_appimage.sh`
2. Laisse-le créer un environnement Python isolé (`venv_linux\`), installer les dépendances, construire l'app, puis télécharger `appimagetool` (une seule fois, ~10 Mo) et fabriquer l'AppImage — quelques minutes la première fois.
3. Une fois terminé, ton AppImage est dans `installateur_linux/FlashBang-x86_64.AppImage`.

Ce script a besoin d'une connexion internet la première fois (pour télécharger `appimagetool`, mis en cache ensuite à côté du script) et de `python3`/`python3-venv` installés (`sudo apt install python3 python3-venv` sur Ubuntu/Debian si besoin).

Tes amis sous Linux reçoivent ce **seul fichier** (`FlashBang-x86_64.AppImage`) : ils doivent juste le rendre exécutable une fois — clic droit → Propriétés → Autorisations → "Autoriser l'exécution du fichier comme un programme" (ou en terminal : `chmod +x FlashBang-x86_64.AppImage`) — puis double-cliquer dessus. Aucune installation, aucun droit admin.

**Si les emojis des boutons s'affichent comme des cases vides** : la distribution n'a pas de police d'emoji installée (courant sur WSL et les installations minimales, plus rare sur un Ubuntu/Fedora de bureau classique). Ton ami peut corriger ça avec : `sudo apt install fonts-noto-color-emoji` (Ubuntu/Debian) puis `fc-cache -f`, avant de relancer l'AppImage.

## Fabriquer le .dmg (pour tes amis sous macOS)

Un vrai Mac est nécessaire pour construire une app macOS (impossible depuis Windows ou Linux) :

1. Copie tout le dossier du projet sur le Mac (clé USB, drive partagé...) — **sauf le dossier `data\`** si tu ne veux pas y transférer tes flashcards personnelles.
2. Ouvre le Terminal (Cmd+Espace, tape "Terminal"), va dans le dossier du projet (`cd chemin/vers/App_Flashcards`), et lance : `bash build_dmg.sh`
3. Laisse-le créer un environnement Python isolé, installer les dépendances, fabriquer l'icône puis l'app et le `.dmg` — quelques minutes la première fois.
4. Une fois terminé, ton fichier est dans `installateur_macos/FlashBang.dmg`.

Ce script a besoin de `python3` installé (depuis [python.org](https://python.org) ou via Homebrew : `brew install python3` si besoin).

Ce `.dmg` n'est pas signé numériquement (une signature Apple coûte 99$/an, pas nécessaire entre amis) : au premier lancement, macOS affichera un avertissement ("app non identifiée" ou "app endommagée"). Ton ami doit faire un clic droit sur `FlashBang.app` → "Ouvrir" → confirmer "Ouvrir quand même" (au lieu d'un double-clic classique), une seule fois. Si ça ne suffit pas (macOS récent), il peut aussi passer par Réglages Système → Confidentialité et sécurité, où un bouton "Ouvrir quand même" apparaît après la première tentative.

*(Un dépôt GitHub avec construction automatique dans le cloud est aussi possible — voir `.github/workflows/build-macos.yml` — mais inutile si tu as un accès direct à un Mac.)*

## Partager le fichier

Que ce soit l'installateur Windows, l'exécutable Windows portable (zippé), l'AppImage Linux ou le `.dmg` macOS, le fichier est trop gros pour un mail ou la plupart des messageries (~150-250 Mo, à cause de PyQt6 et matplotlib). Le plus simple :

- **Un drive partagé** (Google Drive, OneDrive, Dropbox...) : dépose le fichier, partage le lien de téléchargement.
- **WeTransfer** (wetransfer.com) : gratuit jusqu'à 2 Go, pas de compte nécessaire, lien valable quelques jours.

## Ce que voit ton ami au premier lancement

Windows affichera probablement un avertissement SmartScreen ("Windows a protégé votre ordinateur") car le fichier n'est pas signé numériquement (une signature coûte de l'argent et n'est pas nécessaire pour un usage entre amis). Il suffit de cliquer sur **"Informations complémentaires"** puis **"Exécuter quand même"** — que ce soit pour l'installateur ou l'exécutable portable, une seule fois. Sous Linux, il n'y a pas d'avertissement équivalent : juste l'étape "rendre exécutable" mentionnée plus haut. Sous macOS, l'avertissement Gatekeeper est décrit plus haut (clic droit → Ouvrir).

Avec l'installateur Windows, aucun mot de passe administrateur n'est demandé : il s'installe dans un dossier personnel, pas dans "Program Files". Pareil pour l'AppImage sous Linux : aucun mot de passe/sudo requis. Sous macOS, glisser `FlashBang.app` dans Applications ne demande en général pas non plus de mot de passe (sauf configuration particulière du Mac).

L'app crée automatiquement un dossier `data` (ses flashcards, images, etc. y sont stockées) juste à côté de l'exécutable :
- Avec l'installateur Windows, `data` vit dans le dossier d'installation, géré automatiquement.
- Avec l'exécutable Windows portable, si tu déplaces le dossier `FlashBang\`, `data` (qui est dedans) suit avec lui — ne déplace jamais `FlashBang.exe` tout seul en dehors de son dossier.
- Avec l'AppImage, `data` est créé à côté du fichier `.AppImage` lui-même (pas à l'intérieur, qui est un système de fichiers en lecture seule remonté à chaque lancement) — ne déplace jamais un `.AppImage` sans son dossier `data` s'il en a déjà un.
- Avec le `.dmg`, `data` est créé à côté de `FlashBang.app` (dans le dossier Applications si c'est là qu'il a été glissé) — pas à l'intérieur du `.app`, qui est remplacé en bloc à chaque mise à jour.

## Démarrage lent : --onedir plutôt que --onefile

Les scripts construisent l'app en mode **--onedir** (un dossier avec l'exe + ses dépendances) plutôt que **--onefile** (un seul .exe). Avec --onefile, Windows doit ré-extraire tout le contenu dans un dossier temporaire à *chaque* lancement, ce qui rend l'app lente à démarrer en permanence, pas juste la première fois. --onedir élimine cette ré-extraction : démarrage rapide à chaque fois, au prix d'un dossier avec plusieurs fichiers au lieu d'un seul .exe (ce qui ne change rien pour l'installateur, qui embarque tout ce dossier).

## Partager des flashcards (pas besoin de reconstruire quoi que ce soit !)

Ça, c'est indépendant de l'exécutable : dans l'app, un bouton **📤** permet d'exporter un dossier, une matière, un sous-dossier ou une sélection de flashcards en fichier `.fbshare` (autonome, images comprises). Envoie ce fichier comme n'importe quel fichier (mail, Discord...), et ton ami l'importe avec le bouton **📥 Importer un partage**. Cela fonctionne aussi bien entre deux personnes qui ont déjà l'app qu'entre deux personnes qui utilisent l'app depuis le code source.

## Mettre à jour l'app plus tard

Deux façons de faire, du plus simple au plus automatique :

### À la main (comme avant)

Relance simplement `build_installateur.bat` (ou `build_exe.bat`, `bash build_appimage.sh` sous Linux, `bash build_dmg.sh` sur Mac) : il régénère tout avec les changements. Renvoie le nouveau fichier à tes amis pour qu'ils aient la dernière version — avec l'installateur Windows, ils réinstallent par-dessus ; avec l'AppImage, ils remplacent juste l'ancien fichier `.AppImage` par le nouveau ; avec le `.dmg`, ils glissent le nouveau `FlashBang.app` dans Applications en remplaçant l'ancien (le dossier `data` à côté n'est concerné dans aucun cas).

### Automatiquement, via GitHub (recommandé)

L'app intègre maintenant un vérificateur de mise à jour (voir `src/mises_a_jour.py`) : à chaque lancement, elle regarde discrètement si une nouvelle version a été publiée sur GitHub, et propose à tes amis de télécharger la bonne (le `.exe`, le `.dmg` ou l'`.AppImage` selon leur système) — un bouton **« 🔄 Vérifier les mises à jour »** dans **Paramètres** permet aussi de le faire à la demande.

Pour que ça marche, il faut publier tes versions sur GitHub au lieu de renvoyer le fichier toi-même :

1. **Une seule fois** : crée un dépôt GitHub **public** pour le projet (gratuit), et pousse le code dedans :
   ```
   git init
   git remote add origin https://github.com/KikaZozio/FlashBang-App.git
   git add .
   git commit -m "Premiere version"
   git branch -M main
   git push -u origin main
   ```
   Le dossier `data/` (tes flashcards personnelles) n'est jamais envoyé, il est déjà exclu via `.gitignore`.

2. **Déjà fait** : `src/mises_a_jour.py` pointe vers `KikaZozio/FlashBang-App`.

3. **À chaque nouvelle version** :
   - Ouvre `src/version.py` et augmente `VERSION` (ex. `"1.0.0"` → `"1.1.0"`).
   - Envoie un tag Git correspondant, préfixé par `v` :
     ```
     git add .
     git commit -m "Description des changements"
     git tag v1.1.0
     git push && git push --tags
     ```
   - Le workflow `.github/workflows/release.yml` se déclenche automatiquement : il construit les 3 installateurs (Windows/macOS/Linux) sur les machines gratuites de GitHub (~10-15 minutes), puis les publie tout seul dans une **Release** GitHub avec des notes de version auto-générées. Tu peux suivre la progression dans l'onglet **Actions** du dépôt.
   - Dès que c'est fini, l'app de tes amis détecte la nouvelle version au prochain lancement et leur propose de la télécharger — plus besoin de leur envoyer le fichier à la main.

Rien ne se télécharge ni ne s'installe sans que tes amis cliquent sur "Oui" à une fenêtre de confirmation. Une fois validé :
- **Windows** : le nouvel installateur est téléchargé puis lancé automatiquement (Flash Bang se ferme pour le laisser faire).
- **macOS** : le `.dmg` est téléchargé puis ouvert dans le Finder — il ne reste qu'à glisser l'app dans Applications, comme la première fois (impossible d'automatiser complètement cette étape sans signature Apple payante : macOS refuse qu'une app remplace son propre `.app` en cours d'exécution sans cette signature).
- **Linux (AppImage)** : le nouveau fichier remplace automatiquement l'ancien, puis Flash Bang redémarre tout seul dans la nouvelle version.

En cas de coupure internet, d'échec de téléchargement, ou si le dépôt n'est pas encore configuré, l'app propose de rouvrir le lien de téléchargement dans le navigateur à la place — et la vérification silencieuse au démarrage échoue simplement sans rien afficher si aucune mise à jour n'est trouvée.

**Le dossier `data` (flashcards, images, fichier de sauvegarde) n'est jamais touché par une mise à jour**, sur aucune des plateformes. Côté Windows, l'installateur ne connaît qu'un seul fichier : `FlashBang.exe` lui-même (voir `[Files]` dans `FlashBang.iss`) — `data` n'y est mentionné nulle part, ni à l'installation, ni à la mise à jour, ni à la désinstallation. Côté Linux, l'AppImage est un fichier unique et autonome : remplacer l'ancien fichier par le nouveau ne touche à rien d'autre sur le disque, et `data` vit explicitement en dehors de ce fichier. Côté macOS, `FlashBang.app` est remplacé en bloc à chaque mise à jour (glisser-déposer écrase tout son contenu interne), donc `data` vit explicitement à côté, jamais dedans. C'est garanti par la façon dont chacun est construit, pas juste par précaution.

Avant de reconstruire ou réinstaller, **ferme bien Flash Bang** (et toute fenêtre de l'installateur encore ouverte) : sinon Windows verrouille l'ancien `FlashBang.exe` et la nouvelle version ne peut pas le remplacer (ça s'est déjà produit : la nouvelle icône n'apparaissait pas parce que l'ancien fichier était resté verrouillé). `build_installateur.bat` et `build_exe.bat` le détectent maintenant automatiquement et te préviennent si c'est le cas. Côté installateur, si un ami réinstalle une mise à jour par-dessus une version en cours d'utilisation, Windows lui proposera lui-même de fermer l'app avant de continuer.

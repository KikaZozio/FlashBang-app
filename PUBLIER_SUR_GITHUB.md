# Publier Flash Bang sur GitHub (guide grand débutant)

Ce guide suppose que tu n'as **jamais utilisé Git ni GitHub**. On va tout faire avec **GitHub Desktop**, une application avec des boutons (pas de ligne de commande à taper), sauf pour lancer les scripts de construction que tu connais déjà.

À la fin : tes amis auront une page où télécharger l'app, et l'app détectera toute seule les futures mises à jour (en leur demandant confirmation avant de faire quoi que ce soit).

---

## Étape 1 — Installer GitHub Desktop

1. Va sur **[desktop.github.com](https://desktop.github.com)** et clique sur le gros bouton de téléchargement.
2. Installe-le comme n'importe quel logiciel (double-clic, Suivant, Suivant...).
3. Au premier lancement, clique sur **« Sign in to GitHub.com »** et connecte-toi avec ton compte (une fenêtre de navigateur s'ouvre, c'est normal — pas besoin de taper de mot de passe ou de jeton dans l'appli elle-même).

## Étape 2 — Créer le dépôt à partir de ton dossier de projet

1. Dans GitHub Desktop, menu **File → Add local repository...**
2. Clique sur **Choose...** et sélectionne ton dossier `App_Flashcards` (celui qui contient `src`, `data`, `build_installateur.bat`, etc.).
3. GitHub Desktop va te dire que ce dossier n'est pas encore un dépôt Git, avec un lien du genre **« create a repository »** — clique dessus.
4. Une fenêtre de création apparaît :
   - **Name** : mets `FlashBang-App` (important — c'est le nom déjà configuré dans l'app pour vérifier les mises à jour).
   - Laisse le reste par défaut.
   - Clique sur **Create Repository**.

À ce stade, le dépôt existe **seulement sur ton ordinateur** (rien n'est encore envoyé sur internet).

## Étape 3 — Vérifier que `data/` ne sera pas envoyé

En bas à gauche de GitHub Desktop, une liste de fichiers modifiés apparaît (c'est ta liste de fichiers à publier). **Le dossier `data/` (tes flashcards personnelles) ne doit PAS y figurer** — c'est normal et voulu, il est déjà exclu automatiquement (fichier `.gitignore`). Si par hasard tu le vois dans la liste, dis-le-moi avant de continuer.

## Étape 4 — Publier le dépôt sur GitHub.com

1. En haut de la fenêtre GitHub Desktop, écris un petit résumé dans la case **Summary** (ex. : `Premiere version`), puis clique sur **Commit to main**.
2. Clique ensuite sur le bouton bleu **Publish repository** en haut.
3. Dans la fenêtre qui s'ouvre :
   - **Décoche** la case *« Keep this code private »* — le dépôt doit être **public** pour que tes amis puissent télécharger les fichiers sans avoir de compte GitHub.
   - Vérifie que le nom est bien `FlashBang-App`.
   - Clique sur **Publish Repository**.

Ton code est maintenant en ligne, à l'adresse `https://github.com/KikaZozio/FlashBang-App`. Tu peux aller vérifier dans ton navigateur.

## Étape 5 — Publier une première version (déclenche la construction automatique)

C'est cette étape qui fabrique réellement les 3 fichiers (`.exe`, `.dmg`, `.AppImage`) et les met à disposition de tes amis, via un **tag** (une étiquette de version).

1. Toujours dans GitHub Desktop, va dans l'onglet **History** (à côté de "Changes").
2. Fais un **clic droit sur ton dernier commit** (celui tout en haut, "Premiere version") → **Create Tag...**
3. Tape `v1.0.0` (le `v` devant est important) et valide.
4. Un bouton apparaît te proposant d'envoyer ce tag en ligne (**Push origin** ou une pastille "1 tag to push") — clique dessus.

À partir de là, tout est automatique : GitHub construit les 3 installateurs sur ses propres machines (10-15 minutes), puis crée une **Release** avec les 3 fichiers dedans. Tu peux suivre ça en direct sur `https://github.com/KikaZozio/FlashBang-App/actions`.

## Étape 6 — Envoyer le lien à tes amis

Une fois la construction terminée, la page `https://github.com/KikaZozio/FlashBang-App/releases` liste les fichiers téléchargeables. C'est **ce lien** que tu envoies à tes amis : ils cliquent sur le fichier qui correspond à leur système (`FlashBang_Installateur.exe` pour Windows, `FlashBang.dmg` pour Mac, `FlashBang-x86_64.AppImage` pour Linux) et l'installent comme décrit dans `DISTRIBUTION.md`.

## Comment marchent les mises à jour automatiques (avec confirmation)

Une fois qu'un ami a l'app installée :

- À chaque lancement, l'app vérifie discrètement en ligne s'il existe une version plus récente que la sienne.
- Si oui, **une fenêtre lui demande confirmation** ("Une nouvelle version est disponible... Veux-tu la télécharger et l'installer maintenant ?") — rien ne se télécharge ni ne s'installe sans qu'il clique sur "Oui".
- S'il clique "Oui", le fichier se télécharge (avec une barre de progression), puis :
  - **Windows** : l'installateur se lance tout seul, Flash Bang se ferme pour le laisser faire.
  - **macOS** : le `.dmg` s'ouvre dans le Finder — il glisse l'app dans Applications comme la première fois (une vraie automatisation complète nécessiterait une signature Apple payante).
  - **Linux (AppImage)** : le fichier est remplacé automatiquement et l'app redémarre toute seule dans la nouvelle version.
- Il peut aussi vérifier à tout moment depuis **Paramètres → 🔄 Vérifier les mises à jour**, sans attendre le prochain lancement.

Rien ne se déclenche en arrière-plan sans cette confirmation explicite — c'est fait exprès, pour que personne n'ait de surprise.

## Pour publier une prochaine mise à jour (une fois que tout ça est en place)

Une fois les étapes 1 à 4 faites (elles ne se refont qu'une seule fois), voici la routine à chaque nouvelle version :

1. Modifie le code comme d'habitude (avec mon aide).
2. Ouvre `src/version.py` et augmente le numéro, ex. `"1.0.0"` → `"1.1.0"`.
3. Dans GitHub Desktop : écris un résumé des changements, **Commit to main**, puis **Push origin**.
4. Onglet **History** → clic droit sur le dernier commit → **Create Tag...** → tape `v1.1.0` → **Push** le tag.
5. Attends ~10-15 min (onglet **Actions** sur github.com pour suivre), puis c'est en ligne — tes amis seront notifiés automatiquement au prochain lancement de leur app.

Plus besoin de reconstruire les 3 fichiers toi-même ni de les renvoyer un par un : GitHub s'en charge, et l'app de tes amis s'occupe de leur proposer la mise à jour.

"""Petites fonctions partagees pour resumer le contenu d'un cote de flashcard
en une ligne de texte lisible (utilise dans la liste des matieres et le detail
du calendrier)."""


def resume_bloc(bloc):
    if bloc["type"] == "texte":
        return bloc["contenu"][:40]
    if bloc["type"] == "katex":
        return f"∑ {bloc['contenu'][:30]}"
    if bloc["type"] == "image":
        return "🖼 image"
    if bloc["type"] == "image_legendee":
        nombre_points = len(bloc.get("points", []))
        return f"🏷️ image à légender ({nombre_points})"
    return ""


def resume_cote(blocs):
    if not blocs:
        return "(vide)"
    return "  ·  ".join(resume_bloc(b) for b in blocs if resume_bloc(b)) or "(vide)"

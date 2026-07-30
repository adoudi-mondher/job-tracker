from typing import TypedDict


class LMState(TypedDict):
    candidature_id: int
    poste: str
    entreprise_nom: str
    secteur: str
    resume_offre: str
    stack_technique: str
    analyse: dict            # output Analyste
    lm_courante: str         # output Rédacteur (body uniquement)
    message_email: str       # output Rédacteur (corps mail d'accompagnement)
    motifs_rejet: list[str]  # feedback Vérificateur vers Rédacteur
    nb_iterations: int
    verification: dict       # {conforme: bool, motifs: list[str]}

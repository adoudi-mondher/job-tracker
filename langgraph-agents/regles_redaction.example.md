# [Prénom Nom] — Contexte candidature

> Copier ce fichier en `regles_redaction.md` et compléter avec ton profil réel.
> Ce fichier est chargé au démarrage du service LangGraph et injecté dans les prompts
> des agents Rédacteur et Vérificateur.

---

## Identité

- **Nom :** Prénom Nom
- **Email :** prenom@domaine.fr
- **Portfolio :** ton-site.fr
- **Mobilité :** Région 1 · Région 2 · Région 3

---

## Profil

[Résumé en 2-3 phrases — positionnement, différenciateurs, double culture éventuelle]

---

## Formation

| Diplôme | École | Période |
|---|---|---|
| [Diplôme Bac+5] | [École] | [Date début] → [Date fin] |
| [Diplôme Bac+3] | [École] | [Date début] → [Date fin] |

**Rythme alternance :** [Préciser si majoritairement en entreprise, rythme semaine/mois, etc.]

---

## Expérience professionnelle

### [Entreprise] — [Poste] ([dates])
[Description en bullet points des missions et réalisations clés]

**Utilisation :** [Comment valoriser cette expérience selon le secteur ciblé]

### [Stage/Emploi 2] — [dates]
[Description]

---

## Projets personnels

| Projet | Statut | Description |
|---|---|---|
| **[Projet 1]** | ✅ En production | [Description courte] |
| **[Projet 2]** | 🔧 En cours | [Description courte — NE PAS présenter comme en production si ce n'est pas le cas] |

---

## Stack technique

[Liste des technologies maîtrisées par domaine]

---

## Cibles professionnelles

### Postes visés
1. [Poste prioritaire 1]
2. [Poste prioritaire 2]

### Secteurs priorisés
[Secteur 1] · [Secteur 2] · [Secteur 3]

---

## Règles de rédaction (LM)

### Style
- Direct, factuel, sobre — pas de formules génériques
- Commencer par l'entreprise ou le secteur, jamais par soi
- Terminer par "Cordialement," sans bloc signature étendu
- 250-320 mots

### Type de contrat de l'offre → adapter le ton
Si tu cibles un seul type de contrat (ex. alternance exclusivement), précise-le ici et explique
comment le Rédacteur doit réagir si une offre CDI/Freelance apparaît malgré tout (ex. donner plus
de poids aux stages tout en gardant le mot "stage", ne jamais se positionner comme senior).
Ce champ est détecté automatiquement par l'Analyste (analyse.type_contrat) et transmis au Rédacteur.

### Interdit
- [Formule interdite 1]
- [Formule interdite 2]
- Tiret em (—) → utiliser "-" ou reformuler

### Gaps techniques → règle d'honnêteté
Si l'offre mentionne une stack absente du profil : nommer le gap, montrer le domaine
adjacent maîtrisé, affirmer la capacité de montée en compétence rapide.

### Contextualisation secteur
- **[Secteur 1]** → [Expérience à valoriser]
- **[Secteur 2]** → [Expérience à valoriser]
- **[Secteur 3]** → [Expérience à valoriser]

### Points de vigilance spécifiques
- [Règle spécifique 1 — ex: ne jamais présenter tel projet comme en production]
- [Règle spécifique 2 — ex: toujours mentionner telle date pour tel diplôme]

---

## Langues

- [Langue 1] : [niveau]
- [Langue 2] : [niveau]

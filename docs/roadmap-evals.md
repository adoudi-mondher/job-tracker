# Roadmap — Évaluation du pipeline LangGraph (evals)

Doc vivant : on coche au fur et à mesure, on complète les sections au fil de l'avancement. Ne pas réécrire l'historique déjà coché — ajouter, pas remplacer.

## Pourquoi ce chantier

L'évaluation (evals) est identifiée comme la compétence pivot du marché IA actuel : savoir mesurer si un système marche, pas seulement le construire. Job Tracker est le meilleur candidat pour porter cet artefact : projet personnel, possédé à 100%, déjà multi-agents, déjà en production réelle avec du trafic. L'objectif n'est pas de reconstruire le pipeline mais d'ajouter la couche qui manque : mesure de coût, jeu de test, capture du signal humain, rapport.

Contexte complet de la démarche : conversation `yt-strategic-watch`, analyse `le-recruteur-ne-sait-pas-mieux-que-vous-ce-qu'est`, 2026-08-11.

## État des lieux (constaté le 2026-08-11)

**Ce qui existe déjà :**
- Deux graphes LangGraph : `lm_graph` (analyste → rédacteur → vérificateur, boucle max 2 itérations) et `entretien_graph` (analyste → coach) — `langgraph-agents/graph.py`
- Split de coût déjà pertinent : Haiku 4.5 pour analyste/vérificateur, Sonnet 5 pour rédacteur/coach
- Le vérificateur est déjà un mini système d'éval : checks déterministes (`_check_programmatique` dans `nodes/verificateur.py`) + LLM-as-judge sur le ton. Son verdict sert uniquement à boucler, jamais persisté comme métrique.
- Table `lm_generation_runs` (`db.py`) : logge déjà chaque run (analyse, LM finale, statut, motifs, nb itérations). Écrite mais jamais lue/agrégée.

**Ce qui manque :**
- Aucun coût tracé (tokens/$ par appel LLM)
- Aucun jeu de test sur `_check_programmatique` ni sur la qualité des sorties
- Le champ `lettre_motivation` (`app/models.py`) est écrasé sans historique : une correction humaine post-génération est perdue, alors que c'est le signal le plus précieux
- Aucun rapport agrégé sur `lm_generation_runs`

---

## Phase 1 — Tracer le coût par appel LLM

Recherche déjà faite le 2026-07-31, reprise ici (anciennement dans `todo-list.md`).

- [x] Passer `redacteur.py` et `coach.py` en `with_structured_output(Model, include_raw=True)` (sinon pas d'`AIMessage`, donc pas d'usage disponible) — `analyste.py` et `verificateur.py` n'ont pas ce problème (appel direct)
- [x] Créer la table `llm_calls` (un enregistrement par appel LLM, pas par run de graphe) :
  ```sql
  CREATE TABLE llm_calls (
      id SERIAL PRIMARY KEY,
      candidature_id INTEGER,
      node VARCHAR(50),          -- "analyste", "redacteur", "verificateur", "coach"
      model VARCHAR(50),         -- "claude-haiku-4-5", "claude-sonnet-5"
      input_tokens INTEGER,
      output_tokens INTEGER,
      cost_usd NUMERIC(10,6),
      created_at TIMESTAMP DEFAULT NOW()
  );
  ```
- [x] Écrire un wrapper d'appel LLM commun (helper qui log automatiquement dans `llm_calls` après chaque `invoke`) pour éviter de dupliquer la logique dans chaque node
- [x] Hardcoder le pricing courant (pas d'API de pricing live) :

  | Modèle | Input /1M tokens | Output /1M tokens |
  |---|---|---|
  | `claude-sonnet-5` | $3.00 (intro $2.00 jusqu'au 2026-08-31) | $15.00 (intro $10.00) |
  | `claude-haiku-4-5` | $1.00 | $5.00 |

  Pas d'API Anthropic pour un solde/crédit en temps réel — au mieux on calcule la dépense cumulée nous-mêmes et on la compare à un budget saisi manuellement.
- [x] Petit widget dashboard : dépense du jour / semaine / cumul, éventuellement par candidature sur la page détail — fait sous forme de page dédiée `/evals` (pas un widget sur `/`, voir Phase 4)

## Phase 2 — Jeu de test / régression sur le vérificateur

- [ ] Extraire `_check_programmatique` (`nodes/verificateur.py`) dans un module testable, indépendant du node LangGraph
- [ ] Constituer un jeu de 15-20 cas réels à partir de LM déjà générées (conformes et non conformes), en fixtures pytest
- [ ] Ajouter ces tests au pipeline de test existant du projet
- [ ] Relancer ce jeu de test à chaque modification de `regles_redaction.md` ou des prompts des nodes — objectif : détecter une régression avant qu'elle parte en candidature réelle

## Phase 3 — Capturer le signal humain (LM éditée après génération)

- [ ] Ajouter un champ de traçabilité côté Flask (`app/models.py`) pour distinguer LM générée vs LM éditée manuellement après coup
- [ ] Stocker la version générée ET la version finale envoyée (diff simple, pas besoin d'un historique complet type versioning)
- [ ] Ce signal devient la vérité terrain la plus fiable : si le vérificateur dit "conforme" mais que l'humain corrige quand même, c'est un faux négatif du vérificateur à investiguer

## Phase 4 — Rapport d'éval

- [x] Décider du format de sortie : markdown généré, ou petite page dans le dashboard Job Tracker
  → tranché le 2026-08-18 : page `/evals` dans le dashboard Flask (pas de script séparé)
- [~] Script `eval_report.py` — en grande partie couvert par `/evals` (`app/routes/evals.py`), pas de script séparé nécessaire :
  - [x] % conforme au premier coup (sans itération) — et taux conforme global
  - [x] Coût cumulé / 7 jours / jour, ventilé par node (tokens input/output inclus)
  - [x] Top motifs de rejet du vérificateur
  - [ ] Coût moyen par candidature (actuellement : cumul par node, pas de moyenne par candidature)
  - [ ] Évolution dans le temps (dérive après modification d'un prompt) — pas de vue temporelle pour l'instant, seulement cumul/7j/jour

---

## Journal

- **2026-08-11** — Création du doc. État des lieux fait après lecture de `graph.py`, `state.py`, `main.py`, `db.py`, `nodes/*.py`. Recherche coût du 2026-07-31 (ex-`todo-list.md`) intégrée en Phase 1.
- **2026-08-18** — Phase 1 : tracing du coût implémenté. `redacteur.py`/`coach.py` passés en `with_structured_output(..., include_raw=True)` (gestion de `parsing_error` ajoutée pour garder le comportement fail-loud d'origine). Table `llm_calls` créée dans `db.py` (`ensure_table()` la crée aussi désormais). Nouveau module `nodes/llm_tracking.py` : helper `track_llm_call()` commun aux 4 nodes, pricing hardcodé avec bascule automatique sur la date de fin du tarif d'intro sonnet-5 (2026-08-31).
- **2026-08-18 (suite)** — Page `/evals` créée côté Flask (`app/routes/evals.py`, `app/templates/evals/index.html`) : modèles SQLAlchemy `LlmCall`/`LmGenerationRun` en lecture seule sur les tables gérées par `langgraph-agents/db.py` (fallback silencieux si absentes — dev local sqlite ou service jamais lancé contre la base). Couvre le widget Phase 1 (coût cumul/7j/jour, coût+tokens par node) et l'essentiel de Phase 4 (taux conforme, taux conforme au premier coup, top motifs de rejet, dernières générations) sans script séparé. À l'occasion, remplacé le bloc "relances à faire" du dashboard principal (`/`) par un widget "taux de conversion" (% candidatures avec réponse, taux d'entretien) — demande explicite de l'utilisateur, plus utilisé.

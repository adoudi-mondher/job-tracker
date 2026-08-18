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

- [x] Extraire `_check_programmatique` (`nodes/verificateur.py`) dans un module testable, indépendant du node LangGraph → `langgraph-agents/verification.py` (`check_programmatique`), zéro import LangChain/LangGraph
- [x] Constituer un jeu de cas en fixtures pytest — **21 cas synthétiques**, pas des LM réelles extraites de la base (pas d'accès à la base de prod depuis cet environnement) : une règle par cas + cas conforme + bornes 249/250/320/321 mots + combinaison de violations. `langgraph-agents/tests/test_verification.py`
- [x] Ajouter ces tests au pipeline de test existant du projet → `langgraph-agents/pytest.ini` dédié (`cd langgraph-agents && pytest tests/`), séparé du `pytest.ini` racine (Playwright/UI, nécessite un serveur Flask vivant) pour rester rapide et sans dépendance externe. Documenté dans `README.md` §Tests
- [x] Relancer ce jeu de test à chaque modification des prompts des nodes — objectif : détecter une régression avant qu'elle parte en candidature réelle. Automatisé via GitHub Actions (`.github/workflows/tests-verificateur.yml`, sur push/PR vers `main`), badge dans `README.md`. Choix délibéré (2026-08-18) : pas de hook git pre-commit (redondant, friction locale pour peu de gain), pas de bouton UI dans le dashboard (le terminal donne déjà un résultat lisible en <1s ; un endpoint qui exécute pytest en sous-processus ajoutait de la surface pour un gain surtout esthétique) — ce chantier evals est avant tout un artefact de portfolio (voir "Pourquoi ce chantier" en tête de doc), la CI publique sert directement cet objectif. **Limite assumée :** `regles_redaction.md` est exclu du dépôt public (`.gitignore`), donc la CI ne se déclenche jamais sur ses modifications — seuls les changements de `nodes/*.py`/`verification.py` le font. Relance manuelle (`pytest tests/`) requise après édition de `regles_redaction.md`, avant le SCP vers le VPS.

## Phase 3 — Capturer le signal humain (LM éditée après génération)

- [x] Ajouter un champ de traçabilité côté Flask (`app/models.py`) pour distinguer LM générée vs LM éditée manuellement après coup → `Candidature.lettre_motivation_generee` (snapshot) + propriété `lm_editee_manuellement` (diff simple, texte trimé)
- [x] Stocker la version générée ET la version finale envoyée (diff simple, pas besoin d'un historique complet type versioning) → `lettre_motivation_generee` figé au PATCH de génération (`api.py::patch_candidature`, seul appelant = write-back langgraph-agents), `lettre_motivation` reste la version courante éditable via le form UI (`candidatures.py`, route inchangée)
- [x] Ce signal devient la vérité terrain la plus fiable : si le vérificateur dit "conforme" mais que l'humain corrige quand même, c'est un faux négatif du vérificateur à investiguer → surfacé sur `/evals` (dernier run "conforme" par candidature + `lm_editee_manuellement` == True), pas de nouvelle page, réutilise la page Phase 4 existante
- [ ] **Migration prod requise, pas encore exécutée** : `db.create_all()` ne modifie jamais une table existante, la colonne doit être ajoutée manuellement sur le Postgres du VPS avant que le signal soit fiable en prod (voir commande dans le journal du jour)

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
- **2026-08-18 (suite)** — Page `/evals` créée côté Flask (`app/routes/evals.py`, `app/templates/evals/index.html`) : modèles SQLAlchemy `LlmCall`/`LmGenerationRun` en lecture seule sur les tables gérées par `langgraph-agents/db.py` (fallback silencieux si absentes — dev local sqlite ou service jamais lancé contre la base). Couvre le widget Phase 1 (coût cumul/7j/jour, coût+tokens par node) et l'essentiel de Phase 4 (taux conforme, taux conforme au premier coup, top motifs de rejet, dernières générations) sans script séparé. À l'occasion, remplacé le bloc "relances à faire" du dashboard principal (`/`) par un widget "taux de conversion" (% candidatures avec réponse, taux d'entretien) — demande explicite de l'utilisateur, plus utilisé. Déployé et vérifié en prod le même jour.
- **2026-08-18 (Phase 2)** — Extraction de `check_programmatique` dans `langgraph-agents/verification.py`, 21 cas de test dans `langgraph-agents/tests/test_verification.py` (`pytest.ini` dédié dans `langgraph-agents/`, indépendant du `pytest.ini` racine Playwright). Cas synthétiques, pas des LM réelles (pas d'accès DB prod depuis cet environnement) — à noter si une vraie extraction depuis `lm_generation_runs` est souhaitée plus tard.
- **2026-08-18 (Phase 2, suite — automatisation)** — Avant de construire quoi que ce soit, clarifié le "pourquoi" avec l'utilisateur : ce chantier existe comme artefact de portfolio/entretien (cf. tête de doc), pas pour un besoin opérationnel fort (un seul utilisateur qui relit chaque LM avant envoi). Décision : GitHub Actions seul (`.github/workflows/tests-verificateur.yml`, zéro dépendance tierce car `test_verification.py` n'importe que `verification.py` — install `pip install pytest` uniquement, pas tout `requirements.txt`), badge README. Écartés délibérément : hook git pre-commit (redondant avec la CI, friction locale, aucune audience) et bouton UI pour lancer les tests depuis le dashboard (le terminal suffit, l'endpoint d'exécution ajoutait de la surface pour un gain cosmétique).
- **2026-08-18 (Phase 3)** — `Candidature.lettre_motivation_generee` ajouté (`app/models.py`), figé dans `api.py::patch_candidature` au moment du write-back de génération (seul appelant de ce PATCH sur ce champ — n8n retiré). Propriété `lm_editee_manuellement`. Signal surfacé sur `/evals` : nb LM conformes avec snapshot, % corrigées par l'humain malgré tout, liste des candidatures concernées avec lien. Testé de bout en bout (PATCH génération → édition manuelle via form → vérification que le snapshot ne bouge pas → `/evals` affiche bien le faux négatif). **Non fait :** migration Postgres prod (`ALTER TABLE candidature ADD COLUMN lettre_motivation_generee TEXT;`) — `db.create_all()` ne touche jamais une table existante, à exécuter manuellement sur le VPS avant que `/evals` remonte un vrai signal en prod :
  ```bash
  docker compose exec job-tracker-db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "ALTER TABLE candidature ADD COLUMN IF NOT EXISTS lettre_motivation_generee TEXT;"'
  ```
  Migration exécutée et vérifiée le même jour (`\d candidature` sur le VPS).
- **2026-08-18 (test réel — bug trouvé)** — Test de bout en bout demandé par l'utilisateur : régénération d'une vraie LM en prod (candidature Olky #204, statut Abandonné → À envoyer via navigateur piloté). Génération confirmée (nouveau texte). Mais `/evals` affichait "7 derniers jours" et "Aujourd'hui" à $0.0000 alors que "Coût cumulé" ($0.0268) était correct. **Cause :** `LlmCall.created_at`/`LmGenerationRun.created_at` dans `app/models.py` utilisaient `default=datetime.utcnow` (Python-side, appliqué seulement par l'ORM Flask) au lieu de `server_default=` (DDL). `llm_calls` étant une table neuve créée cette session, si `db.create_all()` (Flask) l'a créée avant `ensure_table()` (langgraph-agents), la colonne s'est retrouvée sans défaut SQL — les INSERT bruts de `db.py::log_llm_call()` (qui ne précisent jamais `created_at`, comptant sur `DEFAULT NOW()`) ont alors écrit `NULL`. `lm_generation_runs` n'a pas ce problème car la table existait déjà avant cette session (créée à l'origine par langgraph-agents seul). **Fix :** `server_default=db.func.now()` sur les deux modèles (portable sqlite/postgres, vérifié en local). **Reste à exécuter sur le VPS** (table déjà créée, le fix du modèle ne s'applique pas rétroactivement) :
  ```bash
  docker compose exec job-tracker-db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "ALTER TABLE llm_calls ALTER COLUMN created_at SET DEFAULT NOW();"'
  docker compose exec job-tracker-db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "UPDATE llm_calls SET created_at = NOW() WHERE created_at IS NULL;"'
  ```

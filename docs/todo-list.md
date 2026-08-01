# TODO / idées — Job Tracker

Idées de fonctionnalités identifiées mais pas (encore) implémentées. Chaque entrée documente le contexte et les recherches déjà faites pour ne pas repartir de zéro.

---

## Suivi des coûts API Anthropic (tokens + $ par génération)

**Statut :** à faire, priorité basse — idée notée le 2026-07-31, pas encore planifiée.

**Objectif :** avoir un compteur de consommation API Anthropic (job-tracker + éventuellement Fretexia, CesedaIA) — coût par génération individuelle, et un total cumulé affiché quelque part dans l'app (dashboard ou page dédiée).

### Ce qui est faisable

**1. Récupérer l'usage tokens par appel LLM**

LangChain expose l'usage sur chaque réponse `ChatAnthropic` :
- `response.usage_metadata` → `{input_tokens, output_tokens, total_tokens}`
- `response.response_metadata["usage"]` → dict brut Anthropic (inclut aussi `cache_creation_input_tokens` / `cache_read_input_tokens`)

**Piège identifié sur le code actuel** : `redacteur.py` et `coach.py` utilisent `_llm.with_structured_output(Model)`, qui par défaut ne retourne que l'objet Pydantic parsé — pas d'`AIMessage`, donc pas d'usage disponible. Il faut passer `with_structured_output(Model, include_raw=True)`, qui retourne `{"raw": AIMessage, "parsed": Model}` : lire l'usage sur `raw`, le résultat sur `parsed`. `analyste.py` et `verificateur.py` (appel direct sans structured output) n'ont pas ce problème.

**2. Stockage proposé**

Plutôt qu'ajouter 2 colonnes à `lm_generation_runs` (qui logue un run de graphe entier, donc plusieurs appels LLM), créer une table dédiée par **appel** individuel :

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

Permet d'agréger par candidature, par jour, ou en cumul total. Même pattern réutilisable tel quel dans les autres projets IA (Fretexia, CesedaIA).

**3. Pricing actuel (à hardcoder, pas d'API de pricing live)**

| Modèle | Input /1M tokens | Output /1M tokens |
|---|---|---|
| `claude-sonnet-5` | $3.00 (intro $2.00 jusqu'au 2026-08-31) | $15.00 (intro $10.00) |
| `claude-haiku-4-5` | $1.00 | $5.00 |

⚠️ Penser à mettre à jour ces tarifs si Anthropic les change — aucune API ne les expose dynamiquement.

### Ce qui n'est PAS faisable

**Solde/crédit restant en temps réel : pas d'API publique Anthropic pour ça.** Le solde prépayé ne se consulte que dans la Console Anthropic (page Billing). Le "compteur" dans Job Tracker ne pourra donc jamais interroger Anthropic pour un vrai solde live — au mieux on calcule la **dépense cumulée** nous-mêmes (via le point 1) et on la compare à un budget qu'on renseigne manuellement dans l'app. C'est une estimation basée sur nos logs, pas une vérité serveur Anthropic.

### Pistes d'implémentation (non détaillées)

- Wrapper d'appel LLM commun (helper qui log automatiquement dans `llm_calls` après chaque `invoke`) pour éviter de dupliquer la logique dans chaque node.
- Petit widget dashboard Job Tracker : dépense du jour / de la semaine / cumul total, éventuellement par candidature sur la page détail.
- Si réutilisé sur Fretexia/CesedaIA : voir si ça vaut le coup d'exposer ce logging comme un petit module partagé plutôt que de le dupliquer.

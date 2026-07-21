# Job Tracker 🎯

Dashboard de suivi de candidatures en alternance — Flask + PostgreSQL + HTMX, avec pipeline de génération IA via LangGraph.

Développé dans le cadre d'une recherche d'alternance MSc IA.  
Fork-friendly : clone, configure, lance.

---

## Stack

| Couche | Technologie |
|--------|------------|
| Backend | Flask 3 + SQLAlchemy + Flask-Migrate |
| Frontend | Jinja2 + HTMX + Chart.js |
| Base de données | SQLite (dev) / PostgreSQL (prod) |
| Déploiement | Gunicorn + Docker + Nginx Proxy Manager |
| Agents IA | LangGraph + Claude AI (Haiku + Sonnet) |

---

## Fonctionnalités

### Suivi des candidatures
- Dashboard avec stats en temps réel (répartition par statut, candidatures par semaine)
- Suivi complet : entreprises, candidatures, interactions chronologiques
- Changement de statut en un clic sans rechargement (HTMX)
- Alertes relances automatiques à J+7
- Archivage en masse pour clôturer une campagne et en démarrer une nouvelle
- Export CSV (candidatures actives ou archivées)

### Découverte d'offres
- Page **Découvrir (LBA)** : offres et recruteurs via l'[API La Bonne Alternance](https://api.apprentissage.beta.gouv.fr), recherche automatique sur 6 zones cibles (Île-de-France, Lyon, Marseille, Metz, Nancy, Strasbourg), filtre Apprentissage / Professionnalisation
- Page **France Travail** : offres alternance IA via l'[API France Travail](https://francetravail.io), filtrage par mots-clés et type de contrat, import manuel sélectif au pipeline
- Marquage **✅ Déjà dans le pipeline** sur les deux pages pour éviter les doublons

### Génération de lettres de motivation (LangGraph)

Pipeline multi-agents déclenché automatiquement à la création ou au changement de statut vers "À envoyer".

| Agent | Modèle | Rôle |
|-------|--------|------|
| **Analyste** | claude-haiku-4-5 | Extrait poste, secteur, stack et mots-clés depuis le texte de l'offre |
| **Rédacteur** | claude-sonnet-5 | Génère la LM en appliquant les règles de style et contextualisation sectorielle |
| **Vérificateur** | claude-haiku-4-5 | Contrôle programmatique + LLM (interdits, longueur, ton, honnêteté des gaps) |

Boucle de correction automatique (max 2 itérations) si le Vérificateur rejette. Résultat écrit directement dans la candidature via l'API REST. Chaque run est loggué dans `lm_generation_runs` (PostgreSQL).

---

## Installation locale

```bash
git clone https://github.com/adoudi-mondher/job-tracker.git
cd job-tracker

python -m venv .venv
source .venv/bin/activate  # Windows : .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Édite .env avec tes valeurs

python run.py
```

Ouvre `http://localhost:5000`.

---

## Variables d'environnement

```env
# Obligatoires
SECRET_KEY=change-this-long-random-secret-key
APP_PASSWORD=change-this-password          # Protège l'accès et l'API REST

# PostgreSQL (prod — remplacé par SQLite en dev)
POSTGRES_USER=jobtracker
POSTGRES_PASSWORD=change-this-db-password
POSTGRES_DB=jobtracker

# API La Bonne Alternance (optionnel — page Découvrir)
# Jeton sur : https://api.apprentissage.beta.gouv.fr/fr/compte/profil
LBA_API_KEY=ton-token-lba

# API France Travail (optionnel — page France Travail)
# Inscription gratuite : https://francetravail.io/data/api
FT_CLIENT_ID=PAR_xxx
FT_CLIENT_SECRET=xxx

# LangGraph — génération LM (optionnel — désactive la génération si absent)
ANTHROPIC_API_KEY=sk-ant-...
LM_AGENT_URL=http://langgraph-agents:8001/generate-lm
```

---

## Structure

```
job-tracker/
├── app/
│   ├── __init__.py           # Factory Flask + enregistrement blueprints
│   ├── models.py             # Entreprise / Candidature / Interaction
│   ├── webhooks.py           # Fire-and-forget webhooks sortants
│   ├── routes/
│   │   ├── main.py           # Dashboard + authentification
│   │   ├── entreprises.py    # CRUD entreprises
│   │   ├── candidatures.py   # CRUD candidatures + HTMX statut + archivage
│   │   ├── interactions.py   # Historique interactions
│   │   ├── offres.py         # Pages Découvrir (LBA) + France Travail
│   │   └── api.py            # API REST (LangGraph write-back)
│   ├── templates/
│   └── static/
├── langgraph-agents/
│   ├── main.py               # FastAPI — POST /generate-lm
│   ├── graph.py              # StateGraph LangGraph
│   ├── state.py              # LMState TypedDict
│   ├── nodes/
│   │   ├── analyste.py       # Extraction structurée de l'offre
│   │   ├── redacteur.py      # Génération LM
│   │   └── verificateur.py   # Contrôle qualité + boucle correction
│   ├── db.py                 # Logging PostgreSQL lm_generation_runs
│   ├── regles_redaction.md   # Profil candidat + règles de style
│   ├── requirements.txt
│   └── Dockerfile
├── config.py
├── run.py
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## Modèle de données

```
Entreprise          Candidature                    Interaction
──────────          ───────────                    ───────────
id             ←─── entreprise_id            ←─── candidature_id
nom                 poste                          date
secteur             type_contrat                   type_interaction
localisation        date_envoi                     notes
site_web            statut
contact_nom         lien_offre
contact_email       date_relance
notes               source                 ← "manual" | "lba"
                    resume_offre           ← texte complet de l'offre (saisi)
                    stack_technique        ← extrait par l'Analyste LangGraph
                    lettre_motivation      ← généré par le Rédacteur LangGraph
                    archived_at            ← soft delete
```

**Statuts :** `À envoyer` → `Envoyée` → `Relance` → `Entretien` → `Refus` → `Abandonné`

---

## API REST

Toutes les routes `/api/*` nécessitent :
```
Authorization: Bearer <APP_PASSWORD>
```

| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/api/candidatures` | Liste les candidatures actives |
| POST | `/api/candidatures` | Crée une candidature |
| GET | `/api/candidatures/<id>` | Détail d'une candidature |
| PATCH | `/api/candidatures/<id>` | Mise à jour partielle (write-back LangGraph) |
| GET | `/api/candidatures/relances` | Candidatures avec relance due |
| GET | `/api/candidatures/digest` | Données agrégées (digest hebdomadaire) |
| POST | `/api/scrape` | Sonde France Travail — compte les nouvelles offres |

---

## Page Découvrir — La Bonne Alternance

La page `/offres` interroge l'[API La Bonne Alternance](https://api.apprentissage.beta.gouv.fr) sur **6 zones en parallèle** (Île-de-France, Lyon, Marseille, Metz, Nancy, Strasbourg).

**Filtres disponibles :** Codes ROME · Type de contrat (Apprentissage / Professionnalisation) · Rayon

**Codes ROME par défaut :**

| Code | Métier |
|------|--------|
| M1806 | Conseil et maîtrise d'ouvrage SI |
| M1803 | Direction des systèmes d'information |
| M1805 | Études et développement informatique |

**Obtenir un token LBA :**
1. Crée un compte sur [api.apprentissage.beta.gouv.fr](https://api.apprentissage.beta.gouv.fr/fr/compte/profil)
2. Va dans **Mon compte → Jetons d'accès API → Générer un jeton**
3. Ajoute `LBA_API_KEY=ton-token` dans ton `.env`

---

## Page France Travail

La page `/offres/france-travail` interroge l'[API France Travail](https://francetravail.io/data/api) avec OAuth2.

**Filtres disponibles :** Mots-clés · Type de contrat (Apprentissage E2 / Professionnalisation FS / Les deux)

Les résultats sont filtrés sur les zones cibles. L'import au pipeline est **manuel et sélectif** — pas de bulk-create automatique.

**Obtenir les credentials :**
1. Crée un compte sur [francetravail.io](https://francetravail.io/data/api)
2. Crée une application et souscris à l'API **"Offres d'emploi v2"** (gratuit)
3. Récupère `client_id` et `client_secret`
4. Ajoute `FT_CLIENT_ID` et `FT_CLIENT_SECRET` dans ton `.env`

---

## Déploiement

### Local

```bash
python run.py
# → http://localhost:5000
```

### VPS avec Docker

```bash
cd /opt/docker
git clone https://github.com/adoudi-mondher/job-tracker.git
cd job-tracker
cp .env.example .env
nano .env  # Configure les variables
docker compose up -d --build
```

Alias pratique pour les mises à jour (`~/.bashrc`) :

```bash
alias deploy='git pull && docker compose down && docker compose up -d --build'
```

---

## Licence

MIT — fork librement.

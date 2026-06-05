# Job Tracker 🎯

Dashboard de suivi de candidatures en alternance — Flask + PostgreSQL + HTMX, avec pipeline d'automation IA via n8n.

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
| Automation | n8n self-hosted + Claude AI (optionnel) |

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

### Automation IA (optionnel — nécessite n8n)

| Workflow | Déclencheur | Action |
|----------|-------------|--------|
| **W1** | Cron 7h/jour | Sonde France Travail → notif Telegram avec lien vers la page |
| **W2** | Ajout d'une candidature avec URL | Fetch de la page, extraction IA (poste, stack, résumé) |
| **W3** | Statut → "À envoyer" | Génération automatique d'une lettre de motivation par Claude |
| **W4** | Cron lundi 8h | Digest Telegram hebdomadaire (nouvelles offres, relances dues, entretiens) |

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

# Webhooks n8n sortants (optionnel — workflows W2 et W3)
N8N_WEBHOOK_ENRICH=https://ton-n8n/webhook/enrich
N8N_WEBHOOK_LM=https://ton-n8n/webhook/lettre-motivation
```

---

## Structure

```
job-tracker/
├── app/
│   ├── __init__.py           # Factory Flask + enregistrement blueprints
│   ├── models.py             # Entreprise / Candidature / Interaction
│   ├── webhooks.py           # Fire-and-forget webhooks n8n
│   ├── routes/
│   │   ├── main.py           # Dashboard + authentification
│   │   ├── entreprises.py    # CRUD entreprises
│   │   ├── candidatures.py   # CRUD candidatures + HTMX statut + archivage
│   │   ├── interactions.py   # Historique interactions
│   │   ├── offres.py         # Pages Découvrir (LBA) + France Travail
│   │   └── api.py            # API REST (automation n8n)
│   ├── templates/
│   └── static/
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
notes               source                 ← "manual" | "auto"
                    stack_technique        ← rempli par W2 (IA)
                    resume_offre           ← rempli par W2 (IA)
                    lettre_motivation      ← rempli par W3 (IA)
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
| POST | `/api/candidatures` | Crée une candidature (scraping W1) |
| GET | `/api/candidatures/<id>` | Détail d'une candidature |
| PATCH | `/api/candidatures/<id>` | Mise à jour partielle (enrichissement W2/W3) |
| GET | `/api/candidatures/relances` | Candidatures avec relance due |
| GET | `/api/candidatures/digest` | Données agrégées pour digest Telegram (W4) |
| POST | `/api/scrape` | Sonde France Travail — compte les nouvelles offres sans créer |

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

## Automation n8n (optionnel)

L'app est conçue pour fonctionner standalone ou couplée à **n8n self-hosted** pour automatiser une partie du process.

### W2 — Enrichissement automatique

Déclenché à l'ajout d'une candidature avec URL. n8n fetch la page de l'offre, Claude extrait le poste, la stack technique et un résumé, et patch la candidature via `PATCH /api/candidatures/<id>`.

### W3 — Lettre de motivation IA

Déclenché quand le statut passe à "À envoyer". Claude génère une lettre de motivation personnalisée basée sur le profil et les infos de l'offre, stockée dans `lettre_motivation`.

### W4 — Digest Telegram hebdomadaire

Chaque lundi à 8h : résumé des nouvelles candidatures, relances dues et entretiens en cours.

### W1 — Sonde quotidienne France Travail

Chaque matin à 7h : compte les nouvelles offres disponibles et envoie une notification Telegram avec lien direct vers la page France Travail.

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

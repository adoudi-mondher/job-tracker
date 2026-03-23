# Job Tracker 🎯

Dashboard de suivi de candidatures — Flask + SQLite + HTMX.

Développé dans le cadre d'une recherche d'alternance MOA/PO.  
Fork-friendly : clone, configure, lance.

## Stack

- **Backend** : Flask 3 + SQLAlchemy + Flask-Migrate
- **Frontend** : Jinja2 + HTMX + Chart.js
- **BDD** : SQLite (dev) / PostgreSQL (prod)
- **Déploiement** : Gunicorn + Nginx Proxy Manager sur Debian (optionnel)
- **Automation** : API REST intégrée — compatible n8n ou tout autre outil (optionnel)

## Fonctionnalités

- Dashboard avec stats en temps réel et graphiques (répartition par statut, candidatures par semaine)
- Suivi complet : entreprises, candidatures, interactions
- Changement de statut en un clic sans rechargement de page (HTMX)
- Alertes relances dues automatiques (J+7)
- Pagination sur la liste des entreprises
- Responsive — fonctionne sur mobile
- Page **Découvrir** : recherche d'offres et recruteurs via l'API La Bonne Alternance, avec import direct au pipeline
- API REST pour automatiser relances, statuts et interactions (n8n, Make, ou autre)

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

Ouvre `http://localhost:5000` — c'est tout.

## Variables d'environnement

```env
SECRET_KEY=change-this-long-random-secret-key
APP_PASSWORD=change-this-password

# PostgreSQL (prod uniquement)
POSTGRES_USER=jobtracker
POSTGRES_PASSWORD=change-this-db-password
POSTGRES_DB=jobtracker

# API La Bonne Alternance (optionnel — page Découvrir)
LBA_API_KEY=ton-token-lba-ici
```

## Structure

```
job_tracker/
├── app/
│   ├── __init__.py           # Factory Flask
│   ├── models.py             # Entreprise / Candidature / Interaction
│   ├── routes/
│   │   ├── main.py           # Dashboard + auth
│   │   ├── entreprises.py    # CRUD entreprises + pagination
│   │   ├── candidatures.py   # CRUD candidatures + HTMX statut
│   │   ├── interactions.py   # Historique interactions
│   │   ├── offres.py         # Intégration API La Bonne Alternance
│   │   └── api.py            # Endpoints REST pour automation
│   ├── templates/
│   └── static/
├── config.py
├── run.py
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Modèle de données

```
Entreprise          Candidature              Interaction
──────────          ───────────              ───────────
id             ←─── entreprise_id       ←─── candidature_id
nom                 poste                    date
secteur             type_contrat             type_interaction
localisation        date_envoi               notes
site_web            statut
notes               lien_offre
contact_nom         lm_fichier
contact_email       date_relance
                    notes
```

**Statuts :** `À envoyer` → `Envoyée` → `Relance` → `Entretien` → `Refus` → `Abandonné`

## API REST

Toutes les routes `/api/*` nécessitent :
```
Authorization: Bearer <APP_PASSWORD>
```

| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/api/candidatures` | Liste toutes les candidatures |
| GET | `/api/candidatures/relances` | Candidatures avec relance due |
| PUT | `/api/candidatures/<id>/statut` | Modifier le statut |
| POST | `/api/candidatures/<id>/interactions` | Ajouter une interaction |

## API La Bonne Alternance (optionnel)

La page **Découvrir** intègre l'API publique [La Bonne Alternance](https://api.apprentissage.beta.gouv.fr) pour afficher des offres d'alternance et des recruteurs potentiels autour de ta localisation, avec import direct au pipeline en un clic.

### Obtenir un token

1. Crée un compte sur [api.apprentissage.beta.gouv.fr](https://api.apprentissage.beta.gouv.fr/fr/compte/profil)
2. Va dans **Mon compte → Jetons d'accès API**
3. Clique sur **Générer un nouveau jeton d'accès**
4. Ajoute `LBA_API_KEY=ton-token` dans ton `.env`

### Codes ROME utilisés par défaut

| Code | Métier |
|------|--------|
| M1806 | Conseil et maîtrise d'ouvrage SI |
| M1803 | Direction des systèmes d'information |
| M1805 | Études et développement informatique |

Modifiables directement depuis l'interface de recherche.

> L'utilisation de cette API est gratuite et réservée à des usages non lucratifs.

## Automation (optionnel)

L'app expose une API REST qui permet d'automatiser le suivi des candidatures — relances automatiques, changements de statut, notifications.

Personnellement j'utilise **n8n self-hosted** couplé à de l'IA pour automatiser une partie de ce process. Si ça t'intéresse, ça peut te donner des idées pour construire ta propre stack d'automation par-dessus ce projet.

## Déploiement

L'app fonctionne parfaitement en local — c'est le cas d'usage le plus simple.

### Usage local (recommandé pour démarrer)

```bash
python run.py
```

### Déploiement VPS (optionnel)

Si tu veux accéder à ton tracker depuis n'importe où ou activer l'automation, tu peux le déployer sur un VPS.

Pour ma part j'utilise **Docker + Nginx Proxy Manager sur Debian**, mais n'importe quelle infra compatible Python/Docker convient.

```bash
cd /opt/docker
git clone https://github.com/adoudi-mondher/job-tracker.git
cd job-tracker
cp .env.example .env
nano .env
docker compose up -d --build
```

Pour les mises à jour, j'utilise un alias `deploy` défini dans `~/.bashrc` :

```bash
alias deploy='git pull && docker compose down && docker compose up -d --build'
```

Usage : `cd /opt/docker/job-tracker && deploy`

## Roadmap

- [ ] Automation relances via n8n self-hosted
- [ ] Notifications Telegram/email sur relances dues
- [ ] Export CSV des candidatures
- [ ] Graphiques stats avancés

## Licence

MIT — fork librement.
# Job Tracker 🎯

Dashboard de suivi de candidatures — Flask + SQLite + HTMX.

Développé dans le cadre d'une recherche d'alternance MOA/PO.  
Fork-friendly : clone, configure, lance.

## Stack

- **Backend** : Flask 3 + SQLAlchemy + Flask-Migrate
- **Frontend** : Jinja2 + HTMX
- **BDD** : SQLite (dev) / PostgreSQL (prod)
- **Déploiement** : Gunicorn + Nginx sur Debian

## Automation (optionnel)

L'app expose une API REST qui permet d'automatiser le suivi des candidatures — relances automatiques, changements de statut, notifications.

Personnellement j'utilise **n8n self-hosted** couplé à de l'IA pour automatiser une partie de ce process. Si ça t'intéresse, ça peut te donner des idées pour construire ta propre stack d'automation par-dessus ce projet.

## Installation

```bash
git clone https://github.com/ton-repo/job-tracker
cd job-tracker

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Édite .env avec tes valeurs

python run.py
```

## Structure

```
job_tracker/
├── app/
│   ├── __init__.py          # Factory Flask
│   ├── models.py            # Entreprise / Candidature / Interaction
│   ├── routes/
│   │   ├── main.py          # Dashboard + auth
│   │   ├── entreprises.py
│   │   ├── candidatures.py
│   │   ├── interactions.py
│   │   └── api.py           # Endpoints REST pour n8n
│   ├── templates/
│   └── static/
├── config.py
├── run.py
└── requirements.txt
```

## API REST (pour n8n)

Toutes les routes `/api/*` nécessitent le header :
```
Authorization: Bearer <APP_PASSWORD>
```

| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/api/candidatures` | Liste toutes les candidatures |
| GET | `/api/candidatures/relances` | Candidatures avec relance due |
| PUT | `/api/candidatures/<id>/statut` | Modifier le statut |
| POST | `/api/candidatures/<id>/interactions` | Ajouter une interaction |

## Statuts disponibles

`À envoyer` → `Envoyée` → `Relance` → `Entretien` → `Refus` → `Abandonné`

## Déploiement VPS

Stack : Docker + Nginx Proxy Manager sur Debian.

### Premier déploiement
```bash
cd /opt/docker
git clone https://github.com/adoudi-mondher/job-tracker.git
cd job-tracker
cp .env.example .env
nano .env
docker compose up -d --build
```

### Mises à jour
```bash
cd /opt/docker/job-tracker && deploy
```

> `deploy` est un alias défini dans `~/.bashrc` :
> `alias deploy='git pull && docker compose down && docker compose up -d --build'`

## Licence

MIT — fork librement.

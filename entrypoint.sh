#!/bin/bash
set -e

echo "Initialisation de la base de données..."
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all(); print('DB OK')"

echo "Démarrage de Gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 --workers 2 run:app

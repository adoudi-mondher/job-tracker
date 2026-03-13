from app import create_app, db

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

# Appelé par Gunicorn — init DB au premier démarrage
with app.app_context():
    db.create_all()

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config

db = SQLAlchemy()
migrate = Migrate()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Init extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Enregistrement des blueprints
    from app.routes.main import main_bp
    from app.routes.entreprises import entreprises_bp
    from app.routes.candidatures import candidatures_bp
    from app.routes.interactions import interactions_bp
    from app.routes.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(entreprises_bp, url_prefix='/entreprises')
    app.register_blueprint(candidatures_bp, url_prefix='/candidatures')
    app.register_blueprint(interactions_bp, url_prefix='/interactions')
    app.register_blueprint(api_bp, url_prefix='/api')

    return app

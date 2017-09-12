from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from config import config



db = SQLAlchemy()


def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    db.init_app(app)

    from . import models
    from .app import main
    app.register_blueprint(main)

    @app.route('/test')
    def hello_world():
        return 'Listings scraped: %s' % db.session.query(models.ApartmentListing).count()

    return app
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap

from config import config


db = SQLAlchemy()


def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    db.init_app(app)
    Bootstrap(app)

    from . import models, filters, views

    @app.context_processor
    def setup_navbar_and_footer():
        return {
            'active_hoods': models.Neighborhoods.get_active(),
            'last_scrape': models.ScrapeLog.latest_stamp()
        }

    @app.route('/test')
    def hello_world():
        return 'Listings scraped: %s' % db.session.query(
            models.ApartmentListing).count()

    app.add_url_rule('/', view_func=views.ShowHome.as_view('home'))
    app.add_url_rule('/hoods/<int:neighborhood_id>/<slug>', 
                     view_func=views.ShowNeighborhood.as_view('hood'))

    app.jinja_env.filters['price'] = lambda x: '${:7,.0f}'.format(x)
    app.jinja_env.filters['price_per_sqft'] = lambda x: '${:5.2f}'.format(x)
    app.jinja_env.filters['timesince'] = filters.timesince

    return app

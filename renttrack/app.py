from datetime import datetime, timedelta
import statistics

from flask import Blueprint, render_template, abort, jsonify, request, redirect, url_for

from sqlalchemy import func
import pandas as pd

from . import models, db
from .models import ApartmentListing, Neighborhoods, ListingPriceStatistics, ScrapeLog


main = Blueprint('main', __name__)


HOODS = [
    'SOMA / south beach',
    'nob hill',
    'mission district',
    'lower nob hill',
    'downtown / civic / van ness',
    'hayes valley',
    'pacific heights',
    'marina / cow hollow',
    'potrero hill',
    'financial district',
    'lower pac hts',
    'richmond / seacliff',
    'castro / upper market',
    'russian hill',
    'inner sunset / UCSF',
    'sunset / parkside',
    'ingleside / SFSU / CCSF',
    'north beach / telegraph hill',
    'noe valley',
    'alamo square / nopa',
 ]


@main.context_processor
def setup_navbar_and_footer():
    return {
        'active_hoods':  Neighborhoods.get_active(),
        'last_scrape': ScrapeLog.latest_stamp()
    }


@main.route('/test-bootstrap')
def hello():
    return render_template('base.html')

@main.route('/123')
def index():
    recent_listings = (ApartmentListing.query.order_by(ApartmentListing.posted.desc())
                       .limit(20)
                       .all())

    post_date = func.DATE(ApartmentListing.posted)
    listings_56d = (db.session.query(post_date, models.ApartmentListing.bedrooms, func.count(models.ApartmentListing.id))
                      .group_by(models.ApartmentListing.bedrooms, post_date)
                      .filter(post_date > datetime.now().date() - timedelta(56))
                      .all())
    listings_56d = _format_listings_json(_listings_to_dataframe(listings_56d))


    table_listings = (db.session.query(models.ApartmentListing.location, models.ApartmentListing.bedrooms, func.count(models.ApartmentListing.id))
                       .group_by(models.ApartmentListing.location, models.ApartmentListing.bedrooms)
                       .filter(post_date > datetime.now().date() - timedelta(56))
                       .filter(models.ApartmentListing.location.in_(HOODS))
                       .all())
    table_listings = _listings_to_dataframe2(table_listings)
    

    revenue_listings = ListingPriceStatistics.query.filter(ListingPriceStatistics.location.in_(HOODS)).all()
    revenue_listings = _listings_to_dataframe3(revenue_listings)

    return render_template('home.html', recent_listings=recent_listings, data=listings_56d, 
                            table_listings=table_listings, revenue_listings=revenue_listings)





import json

def _listings_to_dataframe(listings):
    df = pd.DataFrame(listings, columns=['post_date', 'bedrooms', 'listings'])
    df['post_date'] = pd.to_datetime(df['post_date'])
    df = df.set_index(['post_date', 'bedrooms'])['listings'].unstack('bedrooms').resample('1d').max().fillna(0)
    return df

def _listings_to_dataframe2(listings):
    df = pd.DataFrame(listings, columns=['location', 'bedrooms', 'listings'])
    df = df.set_index(['location', 'bedrooms'])['listings'].unstack('bedrooms').fillna(0)
    df = df.rename(columns={0: 'Studio', 1: '1B1B', 2: '2B2B'})
    return df

def _listings_to_dataframe3(listings):
    rows = [(l.location, l.bedrooms, l.left_price, l.median_price, l.right_price) for l in listings]
    df = pd.DataFrame(rows, columns=['location', 'bedrooms', 'left', 'median', 'right'])
    df = df.set_index(['location', 'bedrooms'])['median'].unstack('bedrooms')
    df = df.rename(columns={0: 'Studio', 1: '1B1B', 2: '2B2B'})
    return df


def _format_listings_json(df):    
    data = []
    
    names = {0: 'Studio', 1: '1B1B', 2: '2B2B'}
    dts = df.index.map(lambda x: x.timestamp() * 1000)
    for col in df.columns:
        d = {'key': names[col]}
        d['values'] = [{'x': x, 'y': y} for x,y in zip(dts, df[col].values.tolist())]
        data.append(d)
    return json.dumps(data)



def get_object_or_404(model, id):
    obj = db.session.query(model).get(id)
    if obj is None:
        abort(404)
    return obj

@main.route('/hoods/<int:hood_id>')
def redirect_hood(hood_id):
    hood = get_object_or_404(Neighborhoods, hood_id)
    return redirect(url_for('main.hood', hood_id=hood.id, slug=hood.slug_text))


@main.route('/hoods/<int:hood_id>/<slug>')
def hood(hood_id, slug):
    hood = get_object_or_404(Neighborhoods, hood_id)
    listings = ApartmentListing.latest_listings(days=28, location=hood.name)
    return render_template('neighborhood.html', listings=listings)



    
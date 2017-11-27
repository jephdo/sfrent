import json
from datetime import datetime, timedelta

from flask import Blueprint, render_template, abort, jsonify, request, \
                  redirect, url_for
from flask.views import View

from sqlalchemy import func
import pandas as pd

from . import models, db
from .models import ApartmentListing, Neighborhoods, ListingPriceStatistics, \
                    ScrapeLog


BEDROOM_TYPES = {
    0: 'Studio',
    1: '1B1B',
    2: '2B2B'
}


def get_object_or_404(model, id):
    obj = db.session.query(model).get(id)
    if obj is None:
        abort(404)
    return obj


class ShowHome(View):

    def dispatch_request(self):
        active_neighborhoods = [n.name for n in Neighborhoods.get_active()]
        recent_listings = (ApartmentListing.query.order_by(
            ApartmentListing.posted.desc()).limit(20).all())

        post_date = func.DATE(ApartmentListing.posted)
        
        tseries = self.create_tseries()
        postings = self.create_postings(active_neighborhoods)
        revenue = self.create_revenue(active_neighborhoods)


        return render_template('home.html', recent_listings=recent_listings,
                tseries_data=tseries, table_listings=postings, 
                revenue_listings=revenue)

    def create_tseries(self):
        post_date = func.DATE(ApartmentListing.posted)
        since = datetime.now().date() - timedelta(56)
        postings = (db.session.query(post_date, ApartmentListing.bedrooms, 
                                     func.count(ApartmentListing.id)) 
                      .group_by(post_date, ApartmentListing.bedrooms) 
                      .filter(post_date > since)
                      .all())

        # format data into a DataFrame since it's easier to manipualte
        # timeseries data
        df = pd.DataFrame(postings, 
                          columns=['post_date', 'bedrooms', 'listings'])
        df['post_date'] = pd.to_datetime(df['post_date'])
        df = (df.set_index(['post_date', 'bedrooms'])['listings']
                .unstack('bedrooms')
                .resample('1d')
                .max()
                .fillna(0))

        # breakdown DataFrame into JSON string
        data = []
        dts = df.index.map(lambda x: x.timestamp() * 1000)
        for col in df.columns:
            d = {'key': BEDROOM_TYPES[col]}
            d['values'] = [{'x': x, 'y': y}
                           for x, y in zip(dts, df[col].values.tolist())]
            data.append(d)
        return json.dumps(data)

    def create_postings(self, active_neighborhoods):
        post_date = func.DATE(ApartmentListing.posted)
        since = datetime.now().date() - timedelta(56)
        postings = (db.session.query(ApartmentListing.location,
                                    ApartmentListing.bedrooms,
                                    func.count(models.ApartmentListing.id))
                      .group_by(ApartmentListing.location,
                                ApartmentListing.bedrooms) 
                      .filter(post_date > since) 
                      .filter(ApartmentListing.location.in_(active_neighborhoods)) 
                      .all())

        df = pd.DataFrame(postings, columns=['location', 'bedrooms', 'listings'])
        df = (df.set_index(['location', 'bedrooms'])['listings']
                .unstack('bedrooms')
                .fillna(0)
                .rename(columns=BEDROOM_TYPES))

        return df

    def create_revenue(self, active_neighborhoods):
        postings = ListingPriceStatistics.query.filter(
            ListingPriceStatistics.location.in_(active_neighborhoods)).all()
        rows = [(p.location,
                 p.bedrooms,
                 p.left_price,
                 p.median_price,
                 p.right_price) for p in postings]
        df = pd.DataFrame(rows,columns=[
                'location','bedrooms','left', 'median','right'])
        df = (df.set_index(['location', 'bedrooms'])['median']
                .unstack('bedrooms')
                .rename(columns=BEDROOM_TYPES))
        return df


class ShowNeighborhood(View):

    def dispatch_request(self, neighborhood_id, slug):
        neighborhood = get_object_or_404(Neighborhoods, neighborhood_id)
        if neighborhood.slug_text != slug:
            redirect(url_for('hood', neighborhood_id=neighborhood.id, 
                             slug=neighborhood.slug_text))

        recent_listings = ApartmentListing.latest_listings(
                            days=28, 
                            location=neighborhood.name
                          )
        scatter = self.create_scatter(neighborhood)
        return render_template('neighborhood.html', hood=neighborhood,
                               recent_listings=recent_listings,
                               scatter_data=scatter)

    def create_scatter(self, neighborhood):
        post_date = func.DATE(ApartmentListing.posted)
        since = datetime.now().date() -timedelta(56)
        postings = (ApartmentListing.query
                     .filter(ApartmentListing.area > 0) 
                     .filter(ApartmentListing.area < 4000) 
                     .filter(post_date > since) 
                     .filter(ApartmentListing.location == neighborhood.name) 
                     .order_by(ApartmentListing.posted.desc()) 
                     .limit(250)
                     .all())

        data = {k: [] for k in BEDROOM_TYPES}
        for listing in postings:
            data[listing.bedrooms].append({
                'x': listing.area, 
                'y': listing.price / listing.area
            })
        data = [{'key': BEDROOM_TYPES[k], 'values': v} for k, v in data.items()]
        return json.dumps(data)


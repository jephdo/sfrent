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
    1: '1BR',
    2: '2BR'
}


def get_object_or_404(model, id):
    obj = db.session.query(model).get(id)
    if obj is None:
        abort(404)
    return obj


def dump_json(dataframe):
    data = []
    dts = dataframe.index.map(lambda x: x.timestamp())
    for col in dataframe.columns:
        d = {'key': BEDROOM_TYPES[col]}
        d['values'] = [{'x': x, 'y': y}
                       for x, y in zip(dts, dataframe[col].values.tolist())]
        data.append(d)
    return json.dumps(data)


class ShowHome(View):

    def dispatch_request(self):
        active_neighborhoods = [n.name for n in Neighborhoods.get_active()]
        recent_listings = (ApartmentListing.query.order_by(
            ApartmentListing.posted.desc()).limit(20).all())
  
        postings = self.create_postings(active_neighborhoods)
        revenue = self.create_revenue(active_neighborhoods)
        tseries = self.create_tseries()

        return render_template('home.html', recent_listings=recent_listings,
                 table_listings=postings, tseries_data=tseries,
                revenue_listings=revenue)

    def create_postings(self, active_neighborhoods):
        post_date = func.DATE(ApartmentListing.posted)
        since = datetime.now().date() - timedelta(28)
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
        latest_dt = db.session.query(func.max(ListingPriceStatistics.date)).all()[0][0] - timedelta(1)
        stats = (ListingPriceStatistics.query
                     .filter(ListingPriceStatistics.date == latest_dt)
                     .filter(ListingPriceStatistics.location.in_(active_neighborhoods))
                     .all())

        rows = [(s.location, s.mean0, s.mean1, s.mean2) for s in stats]
        df = pd.DataFrame(rows, columns=['location', 0, 1, 2])
        df = df.melt('location', [0,1,2], var_name='bedrooms', 
                     value_name='price')
        df = (df.set_index(['location', 'bedrooms'])['price']
                .unstack('bedrooms')
                .rename(columns=BEDROOM_TYPES)
                .sort_index())
        return df

    def create_tseries(self):
        model = ListingPriceStatistics
        since = datetime.now().date() - timedelta(180)
        tseries = model.query.filter(model.date > since).filter(model.location == None).all()

        df = pd.DataFrame([(t.date, t.mean0,  t.mean1, t.mean2) for t in tseries], 
                          columns=['date', 0, 1, 2])
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        return dump_json(df)


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
        tseries = self.create_tseries(neighborhood)
        return render_template('neighborhood.html', hood=neighborhood,
                               recent_listings=recent_listings,
                               scatter_data=scatter,
                               tseries_data=tseries)

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

    def create_tseries(self, neighborhood):
        model = ListingPriceStatistics
        since = datetime.now().date() - timedelta(180)
        tseries = model.query.filter(model.date > since).filter(model.location == neighborhood.name).all()

        df = pd.DataFrame([(t.date, t.mean0,  t.mean1, t.mean2) for t in tseries], 
                          columns=['date', 0, 1, 2])
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        return dump_json(df)


class ShowScrapes(View):

    def dispatch_request(self):
        recent_scrapes = ScrapeLog.query.order_by(ScrapeLog.scrape_time.desc()).limit(36)
        total_postings = ApartmentListing.query.count()
        first_posting = ApartmentListing.query.order_by(ApartmentListing.posted).first().posted
        avg_scrapes = self.get_average_scrapes()
        tseries = self.create_tseries()
        return render_template('scrapes.html', recent_scrapes=recent_scrapes, 
                               total_postings=total_postings, first_posting=first_posting,
                               tseries_data=tseries, avg_scrapes=avg_scrapes)

    def get_average_scrapes(self):
        post_date = func.DATE(ApartmentListing.posted)
        num_postings = (ApartmentListing.query
                           .filter(post_date > datetime.now() - timedelta(7))
                           .count())
        return num_postings / 7.

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

        return dump_json(df)


import logging

from datetime import datetime, timedelta

import pytz

from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Date, Float, Boolean, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import func


from . import scrape
from . import db
from . import utils


logger = logging.getLogger(__name__)


class ApartmentListing(db.Model):
    __tablename__ = 'apartmentlistings'
    id = Column(Integer, primary_key=True)
    post_id = Column(BigInteger)
    name = Column(String(256))
    price = Column(Integer)
    url = Column(String(256))
    location = Column(String(64))
    area = Column(Integer)
    bedrooms = Column(Integer)
    posted = Column(DateTime(timezone=True))
    latitude = Column(Float)
    longitude = Column(Float)
    has_image = Column(Boolean)
    has_map = Column(Boolean)

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, self.url)

    @classmethod
    def bulk_insert(cls, listings):
        num_inserts = 0

        for listing in listings:
            inserted_listing = db.session.query(ApartmentListing).filter_by(post_id=listing.post_id).first()
            if inserted_listing:
                logger.info("Listing already inserted: %s" % listing.url)
                continue
            db.session.add(cls(
                post_id=listing.post_id, 
                name=listing.name, 
                price=listing.price,
                url=listing.url,
                location=listing.location,
                area=listing.area,
                bedrooms=listing.bedrooms,
                posted=listing.posted,
                latitude=listing.latitude,
                longitude=listing.longitude,
                has_image=listing.has_image,
                has_map=listing.has_map 
            ))
            num_inserts += 1
        db.session.commit()
        logger.info("Inserted %s new listings" % num_inserts)
        return num_inserts

    @classmethod
    def latest_listings(cls, days=28, location=None):
        post_date = func.DATE(ApartmentListing.posted)
        query = db.session.query(ApartmentListing).filter(post_date > datetime.now().date() - timedelta(days))
        if location:
            query = query.filter(ApartmentListing.location == location)
        return query.all()


class Neighborhoods(db.Model):
    __tablename__ = 'neighborhoods'
    id = Column(Integer, primary_key=True)
    name = Column(String(256))
    slug_text = Column(String(256))
    is_active = Column(Boolean)

    @classmethod
    def create_hoods(cls):
        query = db.session.query(ApartmentListing.location.distinct().label("location"))
        neighborhoods = [row.location for row in query.all() if row.location]

        num_inserts = 0
        for hood in neighborhoods:
            inserted_hood = db.session.query(Neighborhoods).filter_by(name=hood).first()
            if inserted_hood:
                logger.info("Neighborhood already inserted: %s" % hood)
                continue
            db.session.add(cls(
                name=hood,
                slug_text=utils.slugify(hood),
                is_active=False
            ))
            num_inserts += 1
        db.session.commit()
        logger.info("Inserted %s new neighborhoods" % num_inserts)

    @classmethod
    def set_active(cls, threshold_28d=100):
        # everyday set neighborhoods active only if has at least 100 listings in past 28d
        # TODO: create this groupby query
        post_date = func.DATE(ApartmentListing.posted)
        hood_counts = (db.session.query(ApartmentListing.location, func.count(ApartmentListing.location))
                                 .filter(post_date > datetime.now().date() - timedelta(28))
                                 .group_by(ApartmentListing.location)
                                 .having(func.count(ApartmentListing.location) > threshold_28d)
                                 .all())

        for hood, count in hood_counts:
            neighborhood = db.session.query(Neighborhoods).filter_by(name=hood).first()
            if neighborhood:
                neighborhood.is_active = True
        db.session.commit()

    @classmethod
    def get_active(cls):
        return db.session.query(cls).filter(cls.is_active == True).order_by(cls.name).all()


class ScrapeLog(db.Model):
    __tablename__ = 'scrapelog'
    id = Column(Integer, primary_key=True)
    scrape_time = Column(DateTime(timezone=True))
    listings_added = Column(Integer)

    @classmethod
    def add_stamp(cls, listings_added):
        scrape_time = datetime.now().replace(tzinfo=pytz.timezone('US/Pacific'))
        db.session.add(cls(scrape_time=scrape_time, listings_added=listings_added))
        db.session.commit()

    @classmethod
    def latest_stamp(cls):
        return db.session.query(func.max(cls.scrape_time)).all()[0][0]


class ListingPriceStatistics(db.Model):
    __tablename__ = 'listingpricestatistics'
    id = Column(Integer, primary_key=True)
    location = Column(String(64))
    bedrooms = Column(Integer)
    min_price = Column(Float)
    max_price = Column(Float)
    median_price = Column(Float)
    first_quartile_price = Column(Float)
    third_quartile_price = Column(Float)
    left_price = Column(Float)
    right_price = Column(Float)
    std = Column(Float)

    @classmethod
    def run_bootstrap(cls, neighborhoods=None):
        if neighborhoods is None:
            neighborhoods = [n.name for n in Neighborhoods.get_active()]

        post_date = func.DATE(ApartmentListing.posted)

        for location in neighborhoods:
            listings = (ApartmentListing.query
                            .filter(post_date > datetime.now().date() - timedelta(56))
                            .filter(ApartmentListing.location == location)
                            .all())
            for bedrooms in (0, 1, 2):
                prices = [listing.price for listing in listings if listing.bedrooms == bedrooms]
                assert len(prices) > 10, 'Need at least 10 listings to run bootstrap.'
                logger.info(f"Generating bootstrap statistics for {location} and bedrooms={bedrooms}")
                bootstrap = utils.bootstrap(utils.trim_outliers(prices))
                stats = bootstrap.describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.95])
                logger.info(f"Statistics generated: {stats}")

                stats = {
                            'location': location, 
                            'bedrooms': bedrooms,
                            'min_price': stats['min'], 
                            'max_price': stats['max'], 
                            'median_price': stats['50%'], 
                            'first_quartile_price': stats['25%'],
                            'third_quartile_price': stats['75%'],
                            'left_price': stats['5%'],
                            'right_price': stats['95%'],
                            'std': stats['std']
                        }

                obj = db.session.query(cls).filter(cls.location == location).filter(cls.bedrooms == bedrooms).first()
                if obj is None:
                    db.session.add(cls(**stats))
                else:
                    for key, value in stats.items():
                        setattr(obj, key, value)

        db.session.commit()
        logger.info("Successfully ran bootstrap for all locations. Data committed to database.")



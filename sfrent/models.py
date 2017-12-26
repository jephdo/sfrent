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

    @property
    def price_per_sqft(self):
        return self.price / self.area

    @classmethod
    def bulk_insert(cls, listings):
        num_inserts = 0

        for listing in listings:
            # use the ID given by craigslist to dedupe listings:
            inserted_listing = db.session.query(
                ApartmentListing).filter_by(post_id=listing.post_id).first()
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
    def latest_listings(cls, days=28, location=None, limit=50):
        """Returns the latest postings available in the database that've
        been scraped from Craigslist.

        days: how many days back to look
        location: filter for particular neighborhood/location
        limit: Maximum number of results to return
        """
        post_date = func.DATE(ApartmentListing.posted)
        query = db.session.query(ApartmentListing).filter(
            post_date > datetime.now().date() - timedelta(days))
        if location:
            query = query.filter(ApartmentListing.location == location)
        return query.order_by(cls.posted.desc()).limit(limit=limit).all()


class Neighborhoods(db.Model):
    __tablename__ = 'neighborhoods'
    id = Column(Integer, primary_key=True)
    name = Column(String(256))
    slug_text = Column(String(256))
    is_active = Column(Boolean)

    @classmethod
    def create_hoods(cls):
        """Inserts a row for every unique neighborhood name that exists 
        in the database."""
        query = db.session.query(
            ApartmentListing.location.distinct().label("location"))
        neighborhoods = [row.location for row in query.all() if row.location]

        num_inserts = 0
        for hood in neighborhoods:
            inserted_hood = db.session.query(
                Neighborhoods).filter_by(name=hood).first()
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
        """Sets any neighborhood's `is_active` field to true depending on how 
        many postings there have been in the past 28 days."""
        latest_dt = db.session.query(func.max(ListingPriceStatistics.date)).all()[0][0] - timedelta(1)
        active_locations = (db.session.query(ListingPriceStatistics.location.distinct())
                              .filter(ListingPriceStatistics.date == latest_dt)
                              .all())
        active_locations = set([l[0] for l in active_locations])

        neighborhoods = cls.query.all()
        for neighborhood in neighborhoods:
            if neighborhood.name in active_locations:
                neighborhood.is_active = True
            else:
                neighborhood.is_active = False


        db.session.commit()

    @classmethod
    def get_active(cls):
        return db.session.query(cls).filter(
            cls.is_active).order_by(
            cls.name).all()


class ScrapeLog(db.Model):
    __tablename__ = 'scrapelog'
    id = Column(Integer, primary_key=True)
    scrape_time = Column(DateTime(timezone=True))
    listings_added = Column(Integer)
    is_success = Column(Boolean)

    @classmethod
    def add_stamp(cls, listings_added, is_success=True):
        """Adds a row to the scrapelog table signaling that a craigslist
        scraped occurred.

        listings_added: number of listings added in the most recent scrape
        is_success: false if scrape failed for whatever reason, true otherwse
        """
        scrape_time = datetime.utcnow().replace(tzinfo=pytz.utc)
        db.session.add(cls(scrape_time=scrape_time,
                           listings_added=listings_added,
                           is_success=is_success))
        db.session.commit()

    @classmethod
    def latest_stamp(cls):
        return db.session.query(func.max(cls.scrape_time)).all()[0][0]


class ListingPriceStatistics(db.Model):
    """Running table of bootstrapped mean prices for studios, 1 bedrooms and 
    2 bedrooms. I run bootstrap simulations nightly and store the data in
    this table so I can display it as time series.

    lower0 = bootstrapped 5th percentile of mean prices for studios
    mean0 = bootstrapped median of mean prices for studios
    upper0 = bootstrapped 95th percentile of mean prices for studios
    ...
    """

    __tablename__ = 'listingpricestatistics'
    id = Column(Integer, primary_key=True)
    date = Column(Date)
    location = Column(String(64), nullable=True)
    lower0 = Column(Float)
    mean0 = Column(Float)
    upper0 = Column(Float)
    lower1 = Column(Float)
    mean1 = Column(Float)
    upper1 = Column(Float)
    lower2 = Column(Float)
    mean2 = Column(Float)
    upper2 = Column(Float)

    @classmethod
    def run_bootstrap(cls, date, trials=1000):
        post_date = func.DATE(ApartmentListing.posted)
        listings =  (ApartmentListing.query
                        .filter(post_date > date - timedelta(28))
                        .filter(post_date <= date)
                        .all())
        # For the bootstrap simulation run across all SF listings, use 
        # the location=NULL
        stats = cls._create_statistics(date, location=None, listings=listings,
                                       trials=trials)
        obj = cls(**stats)
        cls.override_if_exists(obj)

        neighborhoods = {}
        for listing in listings:
            if listing.location not in neighborhoods:
                neighborhoods[listing.location] = []
            neighborhoods[listing.location].append(listing)

        for neighborhood, _listings in neighborhoods.items():
            # if sample size is too small, probably not worth running
            # bootstraps for this neighborhood
            if len(_listings) < 100:
                continue
            stats = cls._create_statistics(date, neighborhood, _listings, 
                                           trials=trials)
            obj = cls(**stats)
            cls.override_if_exists(obj)

        db.session.commit()
        logger.info(
            "Successfully ran bootstrap for all locations. Data committed to database.")

    @classmethod
    def override_if_exists(cls, obj):
        # it's easier to just delete and add the object rather than do
        # an update statement:
        existing_obj = (db.session.query(cls)
                          .filter(cls.location == obj.location)
                          .filter(cls.date == obj.date)
                          .first())
        if existing_obj:
            db.session.delete(existing_obj)
        db.session.add(obj)
        db.session.commit()

    @classmethod
    def _create_statistics(cls, date, location, listings, trials=1000):
        """Runs the bootstrap simulation for given listings and location and
        returns the bootstrap statistics."""
        data = {
            'date': date,
            'location': location
        }

        for bedrooms in (0, 1, 2):
            logger.info(f"Generating bootstrap statistics for {location} and bedrooms={bedrooms} on {date}")
            prices = [l.price for l in listings if l.bedrooms == bedrooms]
            bootstrap = utils.bootstrap(utils.trim_outliers(prices), trials=trials)

            stats = bootstrap.describe(percentiles=[0.05, 0.5, 0.95])
            logger.info(f"Statistics generated: {stats}")
            bedrooms = str(bedrooms)
            data['lower' + bedrooms] = stats['5%']
            data['mean' + bedrooms] = stats['50%']
            data['upper' + bedrooms] = stats['95%']
        return data

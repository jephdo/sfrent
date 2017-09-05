import logging

from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Date, Float, Boolean, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship


from . import scrape
from . import db


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


from datetime import datetime, timedelta

from flask import Blueprint, render_template, abort, jsonify, request, redirect, url_for

from sqlalchemy import func

from . import models, db
from .models import ApartmentListing


main = Blueprint('main', __name__)


@main.route('/')
def index():
    recent_listings = (ApartmentListing.query.order_by(ApartmentListing.posted.desc())
                       .limit(20)
                       .all())

    post_date = func.DATE(ApartmentListing.posted)
    scrape_counts = (db.session.query(post_date, func.count(ApartmentListing.id))
                       .group_by(post_date)
                       .order_by(post_date)
                       .filter(post_date > datetime.now().date() - timedelta(30))
                       .all())


    return render_template('home.html', recent_listings=recent_listings, scrape_counts=scrape_counts)
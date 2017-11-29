from datetime import datetime

import pytz
from craigslist import CraigslistHousing


def scrape_craigslist(max_price=10000, min_price=1000, limit=None):
    cl = CraigslistHousing(
        site='sfbay',
        area='sfc',
        category='apa',
        filters={
            'max_price': max_price,
            'min_price': min_price,
            'private_room': True,
            'posted_today': True})
    listings = []
    for result in cl.get_results(
            sort_by='newest',
            geotagged=True,
            limit=limit):
        bedrooms = int(
            result['bedrooms']) if result['bedrooms'] is not None else 0
        location = result['bedrooms']
        # filter for only studios or 1 bedrooms or 2 bedrooms
        if bedrooms > 2:
            continue
        listings.append(ApartmentListing.from_dict(result))
    return listings


class ApartmentListing:

    def __init__(self, post_id, name, price, url, location, area,
                 bedrooms, posted, latitude, longitude, has_image, has_map):
        self.post_id = post_id
        self.name = name
        self.price = price
        self.url = url
        self.location = location
        self.area = area
        self.bedrooms = bedrooms
        self.posted = posted
        self.latitude = latitude
        self.longitude = longitude
        self.has_image = has_image
        self.has_map = has_map

    @classmethod
    def from_dict(cls, data):
        post_id = int(data['id'])
        name = data['name']
        price = int(data['price'].replace('$', ''))
        url = data['url']
        location = data['where']
        area = int(data['area'].replace('ft2', '')
                   ) if data['area'] is not None else None
        bedrooms = int(data['bedrooms']) if data['bedrooms'] else 0
        posted = datetime.strptime(data['datetime'], '%Y-%m-%d %H:%M')
        posted = posted.replace(tzinfo=pytz.timezone('US/Pacific'))
        latitude, longitude = data['geotag'] if data['geotag'] else (
            None, None)
        has_image = data['has_image']
        has_map = data['has_map']
        return cls(post_id, name, price, url, location, area, bedrooms,
                   posted, latitude, longitude, has_image, has_map)

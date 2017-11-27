import logging
from datetime import datetime, date, timedelta

import click


from renttrack import models, db
from renttrack.scrape import scrape_craigslist


logger = logging.getLogger(__name__)


@click.group()
@click.option('--verbose', is_flag=True, help="Increase logging output")
def cli(verbose):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    if verbose:
        logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)


@cli.command()
@click.option('--drop', '-d', is_flag=True, help="Recreate database and soft reset using only teams data.")
def createdb(drop):
    if drop:
        db.drop_all()
    logger.info("Creating database tables %s", db)
    db.create_all()


@cli.command()
def scrape():
    listings = scrape_craigslist()
    listings_added = models.ApartmentListing.bulk_insert(listings)
    models.ScrapeLog.add_stamp(listings_added)


@cli.command()
@click.option('--threshold', '-t', default=100, type=int, 
              help="Minimum number of listings in the past 28 days to be considered active")
def update_neighborhoods(threshold):
    models.Neighborhoods.create_hoods()
    models.Neighborhoods.set_active(threshold)


@cli.command()
@click.option('--date', '-d')
def run_bootstraps(date):
    models.ListingPriceStatistics.run_bootstraps()



if __name__ == '__main__':
    from manage import app
    # see http://stackoverflow.com/a/19438054
    # for why you need to do this
    app.app_context().push()
    cli()
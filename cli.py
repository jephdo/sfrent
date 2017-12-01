import logging
import time
import random
from datetime import datetime, date, timedelta

import click
import pandas as pd


from sfrent import models, db
from sfrent.scrape import scrape_craigslist


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
@click.option('--hidescrape', is_flag=True)
def scrape(hidescrape):
    # Heroku's scheduler is really limited and you can only scrape every hour
    # or every day. I think scraping Craigslist is against their terms of
    # service so `hidescrape` will try to obscure how often I'm scraping and 
    # make sure it doesnt scrape at the exact same minute of each hour.

    if hidescrape:
        logger.info("--hidescrape activated.")
        # skip 80% of the scrapes
        if random.random() < 0.8:
            logger.info("Choosing not to scrape")
            return
        # randomly sleep between 0-10 minutes.
        sleep = int((random.random() * 10) * 60)
        logger.info(f"Sleeping for {sleep} seconds before scraping.")
        time.sleep(sleep)

    try:
        listings = scrape_craigslist()
    except Exception:
        listings_added = None
        models.ScrapeLog.add_stamp(listings_added, is_success=False)
        raise
    else:
        listings_added = models.ApartmentListing.bulk_insert(listings)
        models.ScrapeLog.add_stamp(listings_added)    


@cli.command()
@click.option('--threshold', '-t', default=100, type=int, 
              help="Minimum number of listings in the past 28 days to be considered active")
def update_neighborhoods(threshold):
    models.Neighborhoods.create_hoods()
    models.Neighborhoods.set_active(threshold)


@cli.command()
@click.option('--date')
@click.option('--trials', '-t', type=int, default=1000)
def run_bootstraps(date, trials):
    if date is not None:
        date = datetime.strptime(date, '%Y-%m-%d').date()
    else:
        date = datetime.now().date() - timedelta(1)
    models.ListingPriceStatistics.run_bootstrap(date, trials=trials)


@cli.command()
@click.argument('start_date')
@click.argument('end_date')
@click.option('--trials', '-t', type=int, default=1000)
def backfill_bootstraps(start_date, end_date, trials):
    for dt in pd.date_range(start_date, end_date):
        click.echo(dt)
        models.ListingPriceStatistics.run_bootstrap(dt.date(), trials=trials)



if __name__ == '__main__':
    from manage import app
    # see http://stackoverflow.com/a/19438054
    # for why you need to do this
    # app.app_context().push()
    with app.app_context():
        cli()
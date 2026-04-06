import logging

from sqlalchemy import delete, func, select

from app.database.models import ScrapedPage
from app.database.session import async_session
from app.scrapers.product_api import ProductAPIScraper

# Firecrawl scrapers (kept as fallback, currently disabled)
# from app.scrapers.hilmabiocare import HilmaBiocareScraper
# from app.scrapers.hilmabiocareshop import HilmaBiocareShopScraper

logger = logging.getLogger(__name__)


async def has_data() -> bool:
    """Check if we already have scraped products in the database."""
    async with async_session() as session:
        result = await session.execute(select(func.count()).select_from(ScrapedPage))
        count = result.scalar()
        return count > 0


async def run_scrapers(force: bool = False):
    """Fetch products from the API and store in the database.

    Args:
        force: If True, sync even if data already exists.
    """
    if not force and await has_data():
        logger.info("Database already has product data — skipping sync. Use POST /scrape to force.")
        return 0

    all_products = []

    # Primary: Product API
    logger.info("Fetching from product API...")
    api_scraper = ProductAPIScraper()
    api_products = await api_scraper.scrape_all()
    all_products.extend(api_products)
    logger.info(f"Product API: {len(api_products)} products fetched")

    # Fallback: Firecrawl scrapers (disabled)
    # if not api_products:
    #     logger.warning("API returned no products — falling back to Firecrawl")
    #     scraper1 = HilmaBiocareScraper()
    #     products1 = await scraper1.scrape_all()
    #     all_products.extend(products1)

    # Store in database
    async with async_session() as session:
        # Clear old data
        await session.execute(delete(ScrapedPage))

        # Insert new data
        for product in all_products:
            page = ScrapedPage(**product)
            session.add(page)

        await session.commit()
        logger.info(f"Stored {len(all_products)} products in database")

    return len(all_products)

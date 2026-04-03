import asyncio
import logging
from functools import partial

from app.scrapers.base import firecrawl

logger = logging.getLogger(__name__)

BASE_URL = "https://hilmabiocareshop.com"


def _map_url_sync():
    return firecrawl.map_url(BASE_URL)


def _scrape_url_sync(url):
    return firecrawl.scrape_url(url, params={"formats": ["markdown"]})


class HilmaBiocareShopScraper:
    """Scraper for hilmabiocareshop.com using Firecrawl."""

    source = "hilmabiocareshop"

    async def scrape_all(self) -> list[dict]:
        """Discover and scrape all product pages."""
        loop = asyncio.get_event_loop()

        logger.info("Mapping hilmabiocareshop.com for product URLs...")
        try:
            map_result = await loop.run_in_executor(None, _map_url_sync)
        except Exception as e:
            logger.error(f"Failed to map hilmabiocareshop.com: {e}")
            return []

        if not map_result:
            logger.warning("No links found on hilmabiocareshop.com")
            return []

        product_urls = [
            url for url in map_result
            if "/product/" in url and "/product-category/" not in url and BASE_URL in url
        ]
        product_urls = list(set(product_urls))
        logger.info(f"Found {len(product_urls)} product URLs")

        products = []
        for i, url in enumerate(product_urls):
            logger.info(f"Scraping product {i + 1}/{len(product_urls)}: {url}")
            try:
                result = await loop.run_in_executor(None, partial(_scrape_url_sync, url))

                if result and result.get("markdown"):
                    metadata = result.get("metadata", {})
                    image_url = metadata.get("og:image", metadata.get("image", ""))
                    products.append({
                        "source": self.source,
                        "url": url,
                        "title": metadata.get("title", "Unknown"),
                        "content": result["markdown"],
                        "image_url": image_url,
                        "page_type": "product",
                    })
            except Exception as e:
                logger.error(f"Failed to scrape {url}: {e}")

        logger.info(f"Successfully scraped {len(products)} products from hilmabiocareshop.com")
        return products

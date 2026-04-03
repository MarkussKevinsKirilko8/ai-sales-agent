import asyncio
import logging
import re
from functools import partial

from app.scrapers.base import firecrawl

logger = logging.getLogger(__name__)

BASE_URL = "https://hilmabiocare.com"

# Junk patterns to remove from scraped content
JUNK_PATTERNS = [
    r"This site is protected by \*\*reCAPTCHA\*\*.*",
    r"This product is protected by.*?Verification.*?\)",
    r"\[Privacy\].*?\[Terms\].*",
    r"!\[.*?\]\(https://.*?\)",  # Image markdown links
    r"\[Hilma Biocare.*?Verification\].*?\)",
    r"\[Download\].*?\)",
    r"\[Become a Partner\].*?\)",
    r"Want to be Hilma Biocare.*?Reseller\?",
    r"products Reseller\?",
    r"Product Test",
    r"reCAPTCHA.*",
    r"Recaptcha requires verification\.",
    r"Copyright.*?Hilma Biocare.*",
    r"^\s*Injectable\s*$",  # Standalone category labels
    r"^\s*Oral tablets\s*$",
    r"^\s*Peptides\s*$",
    r"^\s*/\)\s*$",
    r"^\s*;\s*$",
]


def clean_content(markdown: str) -> str:
    """Remove navigation, footer, reCAPTCHA, and other junk from markdown."""
    for pattern in JUNK_PATTERNS:
        markdown = re.sub(pattern, "", markdown, flags=re.IGNORECASE | re.MULTILINE)

    # Remove lines that are just whitespace or single characters
    lines = markdown.split("\n")
    cleaned_lines = [line for line in lines if len(line.strip()) > 3 or line.strip() == ""]

    markdown = "\n".join(cleaned_lines)
    # Remove excessive blank lines
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.strip()


def _map_url_sync():
    """Synchronous Firecrawl map call."""
    return firecrawl.map_url(BASE_URL)


def _scrape_url_sync(url):
    """Synchronous Firecrawl scrape call."""
    return firecrawl.scrape_url(url, params={
        "formats": ["markdown"],
        "waitFor": 3000,
    })


class HilmaBiocareScraper:
    """Scraper for hilmabiocare.com using Firecrawl."""

    source = "hilmabiocare"

    async def scrape_all(self) -> list[dict]:
        """Discover and scrape all product pages."""
        loop = asyncio.get_event_loop()

        # Step 1: Use map to discover all product URLs
        logger.info("Mapping hilmabiocare.com for product URLs...")
        map_result = await loop.run_in_executor(None, _map_url_sync)

        if not map_result:
            logger.error("Failed to map hilmabiocare.com")
            return []

        # Handle both dict and list responses
        if isinstance(map_result, dict):
            urls = map_result.get("links", map_result.get("urls", []))
        elif isinstance(map_result, list):
            urls = map_result
        else:
            urls = list(map_result) if hasattr(map_result, '__iter__') else []

        logger.info(f"Total URLs discovered: {len(urls)}")

        product_urls = [
            url for url in urls
            if "/product/" in url
        ]
        # Deduplicate
        product_urls = list(set(product_urls))
        logger.info(f"Found {len(product_urls)} product URLs")

        # Step 2: Scrape each product page (non-blocking)
        products = []
        for i, url in enumerate(product_urls):
            logger.info(f"Scraping product {i + 1}/{len(product_urls)}: {url}")
            try:
                result = await loop.run_in_executor(None, partial(_scrape_url_sync, url))

                if result and result.get("markdown"):
                    metadata = result.get("metadata", {})
                    image_url = metadata.get("og:image", metadata.get("image", ""))
                    content = clean_content(result["markdown"])
                    products.append({
                        "source": self.source,
                        "url": url,
                        "title": metadata.get("title", "Unknown"),
                        "content": content,
                        "image_url": image_url,
                        "page_type": "product",
                    })
            except Exception as e:
                logger.error(f"Failed to scrape {url}: {e}")

        logger.info(f"Successfully scraped {len(products)} products from hilmabiocare.com")
        return products

import asyncio
import logging
from functools import partial

import httpx

from app.config.settings import settings

logger = logging.getLogger(__name__)


def _get_text(field, lang="en") -> str:
    """Extract text from a field that might be a dict (multilingual) or a string."""
    if isinstance(field, dict):
        return field.get(lang, field.get("en", ""))
    if isinstance(field, str):
        return field
    return ""


def _get_all_langs(field) -> str:
    """Get all language versions of a field, combined."""
    if isinstance(field, dict):
        parts = []
        for lang, text in field.items():
            if text:
                parts.append(text)
        return " | ".join(parts)
    if isinstance(field, str):
        return field
    return ""


def _fetch_products_sync() -> list[dict]:
    """Synchronous API call to fetch products."""
    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            settings.product_api_url,
            headers={"Authorization": settings.product_api_token},
        )
        response.raise_for_status()
        return response.json().get("data", [])


def _build_product_content(product: dict) -> str:
    """Build a clean content string from API product data."""
    parts = []

    # Title in all languages
    title_en = _get_text(product.get("title"), "en")
    title_ru = _get_text(product.get("title"), "ru")
    parts.append(f"Product: {title_en}")
    if title_ru and title_ru != title_en:
        parts.append(f"Название: {title_ru}")

    # Basic specs
    dose = product.get("Dose per unit")
    if dose and dose is not False:
        parts.append(f"Dose: {dose}")

    measure = _get_text(product.get("Measure", ""))
    if measure:
        parts.append(f"Measure: {measure}")

    form = _get_text(product.get("Form", ""))
    if form:
        parts.append(f"Form: {form}")

    usage = _get_text(product.get("Usage", ""))
    if usage:
        parts.append(f"Usage: {usage}")

    category = product.get("Category", "")
    if category:
        parts.append(f"Category: {category}")

    brand = _get_text(product.get("Brand", ""))
    if brand:
        parts.append(f"Brand: {brand}")

    storage = product.get("°C storage", "")
    if storage:
        parts.append(f"Storage: {storage}")

    in_package = product.get("In package", "")
    if in_package:
        parts.append(f"In package: {in_package}")

    # Price and stock
    price = product.get("price")
    if price:
        parts.append(f"Price: {price}")
    price_disc = product.get("price_with_discount")
    if price_disc:
        parts.append(f"Discounted price: {price_disc}")
    balance = product.get("balance")
    if balance is not None:
        parts.append(f"Stock: {balance}")

    # Descriptions
    short_desc = _get_all_langs(product.get("Short description", ""))
    if short_desc:
        parts.append(f"\nDescription: {short_desc}")

    effects = _get_all_langs(product.get("Main effects", ""))
    if effects:
        parts.append(f"\nMain effects: {effects}")

    side_effects = _get_all_langs(product.get("Side-Effects", ""))
    if side_effects:
        parts.append(f"\nSide effects: {side_effects}")

    objectives = _get_all_langs(product.get("Main objectives", ""))
    if objectives:
        parts.append(f"\nMain objectives: {objectives}")

    features = _get_all_langs(product.get("Features of the drug", ""))
    if features:
        parts.append(f"\nFeatures: {features}")

    drug_level = _get_all_langs(product.get("Drug level", ""))
    if drug_level:
        parts.append(f"\nDrug level: {drug_level}")

    stacking = _get_all_langs(product.get("Stacking", ""))
    if stacking:
        parts.append(f"\nStacking: {stacking}")

    pct = product.get("PCT", "")
    if pct:
        parts.append(f"\nPCT: {pct}")

    protection = _get_all_langs(product.get("Protection", ""))
    if protection:
        parts.append(f"\nProtection: {protection}")

    important = _get_all_langs(product.get("Important", ""))
    if important:
        parts.append(f"\nImportant: {important}")

    goals = product.get("Goals", [])
    if goals and goals != [False]:
        parts.append(f"\nGoals: {', '.join(str(g) for g in goals if g)}")

    # Common names for search
    common = _get_all_langs(product.get("Common names", ""))
    if common:
        parts.append(f"\nCommon names: {common}")

    return "\n".join(parts)


class ProductAPIScraper:
    """Scraper that fetches product data from the product API."""

    source = "product_api"

    async def scrape_all(self) -> list[dict]:
        """Fetch all products from the API."""
        if not settings.product_api_url or not settings.product_api_token:
            logger.warning("Product API not configured — skipping")
            return []

        logger.info("Fetching products from API...")
        loop = asyncio.get_event_loop()

        try:
            raw_products = await loop.run_in_executor(None, _fetch_products_sync)
        except Exception as e:
            logger.error(f"Failed to fetch from product API: {e}")
            return []

        logger.info(f"API returned {len(raw_products)} products")

        products = []
        for product in raw_products:
            title_en = _get_text(product.get("title"), "en")
            title_ru = _get_text(product.get("title"), "ru")
            title = f"{title_en} / {title_ru}" if title_ru and title_ru != title_en else title_en

            # Get image — use main image or first from Picture array
            image_url = product.get("image", "")
            pictures = product.get("Picture", [])
            if not image_url and pictures:
                image_url = pictures[0]

            content = _build_product_content(product)

            products.append({
                "source": self.source,
                "url": product.get("URL", ""),
                "title": title,
                "content": content,
                "image_url": image_url,
                "page_type": "product",
            })

        logger.info(f"Processed {len(products)} products from API")
        return products

import json
import logging
from dataclasses import dataclass, field

import anthropic

from app.config.settings import settings
from app.database.queries import get_all_products, search_products, search_products_exact

logger = logging.getLogger(__name__)

client = anthropic.AsyncAnthropic(api_key=settings.claude_api_key)

SYSTEM_PROMPT = """You are a sales support assistant for Hilma Biocare and Marten products. Your goal is to help customers find products, answer questions, and guide them toward placing an order in the online shop.

LANGUAGE RULES:
- ALWAYS respond in the same language the user writes in (Russian, English, Latvian, etc.)
- If the user writes in Russian, respond fully in Russian
- If the user writes in Latvian, respond fully in Latvian

CORE BEHAVIOR — SALES SUPPORT:
When a customer asks about a product (availability, price, info):
1. Provide the product info: name, dosage, price (if available)
2. Guide them to order: "Press the 'Shop' button to add items to your cart, complete the order and payment. The process is automatic — we see the payment and your order, and it will be processed in queue order. A manager will send a tracking code here in the chat. You can always contact a manager for order details."

AVAILABILITY:
- If a product IS available: give the product info and guide to Shop
- If a product is NOT available: suggest alternatives from the same category with their details. For example, if they ask for a specific testosterone and it's unavailable, show other testosterone products that ARE available.
- For restock timing: "Stock is regularly replenished. Depending on the market situation, it can take from 2 weeks to a month. There is no exact date — when the product appears in stock, you'll see it in our shop by pressing the 'Shop' button."

PRICING:
- If asked for a price list: "Are you interested in specific products or just want to browse the price list? You can browse by pressing the 'Shop' button."
- If the shop doesn't load for the user: "Try using a VPN or use this link."

PAYMENT:
- Payment by Russian bank card: minimum 10,000 RUB
- Payment by cryptocurrency: any amount, no minimum
- If asked about payment methods, provide both options

DELIVERY:
- Delivery is only within Russia
- Do NOT ship to CIS countries
- Russian Post: 1,200 RUB
- EMS Courier: 3,000 RUB
- No SDEK delivery available
- We have multiple warehouses, the exact origin is unknown
- Tracking code delivery: 5-10 days for tracking number, then 3-7 days for delivery

ORDERING PROBLEMS:
- "I can't place an order" or "I need help ordering": "You can place an order online without a manager — press the 'Shop' button, fill your cart, and proceed to checkout and payment. The process is automatic."
- "I can't open the shop": "Press the 'Shop' button. If it doesn't open, try using a VPN. If the problem persists, write 'manager' in the chat and I'll connect you with a manager."
- If the user is stuck or frustrated: offer to transfer to a manager. Manager hours: Mon-Fri 09:00-18:00 Moscow time.

ABOUT THE BRAND:
- We work with Hilma Biocare (India) pharmaceuticals and Marten growth hormone (Germany)
- Products have been on the Russian market for about 10 years

PRODUCT QUESTIONS:
- "What do you think about [product]?" → "The product [name] is used for [purpose], reviews are positive as with the entire product line in our shop."
- "How to use/inject [product]?" → "We do not provide usage recommendations — everything is individual and depends on your age, weight, and training experience. We recommend consulting specialists or researching online."
- Do NOT provide medical advice, dosing protocols, or cycle recommendations

MANAGER HANDOFF:
- If the user writes "менеджер", "manager", or asks to speak with a human → respond: "Connecting you with a manager now. Working hours: Mon-Fri 09:00-18:00 Moscow time."
- If you cannot help or the user is frustrated → offer manager transfer

CLARIFICATION:
- If you're not sure what product the user is asking about, suggest: "Could you clarify — did you mean [product name]?"
- Users may use slang names (e.g., "трен" = Trenbolone, "метан" = Methandienone, "тесто" = Testosterone, "дека" = Nandrolone Decanoate, "болд" = Boldenone, "винни" = Stanozolol, "прови" = Mesterolone, "окси" = Oxymetholone, "анавар" = Oxandrolone, "суст" = Sustanon, "маст" = Drostanolone, "гормонка/гр" = HGH, "клен" = Clenbuterol, "турик" = Turinabol, "примка" = Primobolan, "гало" = Halotestin)

Below is the product catalog data you have access to:
"""

EXTRACT_PROMPT = """Extract the product name(s) from this user message. The user is asking about pharmaceutical/supplement products.

Return a JSON object with:
- "products": list of product names mentioned (just the product names, no extra words)
- "is_specific": true if the user is asking about ONE specific product, false if asking about multiple products or a general question

Examples:
- "Tell me about Testosterone Enanthate" → {"products": ["Testosterone Enanthate"], "is_specific": true}
- "Could you show me these testosterone enanthate" → {"products": ["Testosterone Enanthate"], "is_specific": true}
- "What testosterone products do you have?" → {"products": ["Testosterone"], "is_specific": false}
- "Tell me about Testosterone and Clenbuterol" → {"products": ["Testosterone", "Clenbuterol"], "is_specific": false}
- "Kādi peptīdu produkti jums ir pieejami?" → {"products": ["peptide"], "is_specific": false}
- "Какие есть препараты для похудения?" → {"products": ["weight loss"], "is_specific": false}
- "What is the dosage for Oxandrolone?" → {"products": ["Oxandrolone"], "is_specific": true}
- "Hi, what can you help me with?" → {"products": [], "is_specific": false}

Return ONLY the JSON, nothing else."""

MAX_CONTENT_LENGTH = 1500


@dataclass
class AgentResponse:
    text: str
    product_images: list[dict] = field(default_factory=list)
    show_shop_button: bool = False


async def extract_product_names(user_message: str, chat_history: list[dict] = None) -> tuple[list[str], bool]:
    """Use Claude Haiku to extract product names and intent from user message."""
    try:
        # Include recent history so Haiku understands follow-up questions
        context = ""
        if chat_history:
            recent = chat_history[-4:]  # Last 2 exchanges
            history_lines = []
            for msg in recent:
                role = "User" if msg["role"] == "user" else "Assistant"
                # Truncate long assistant messages
                content = msg["content"][:500] if msg["role"] == "assistant" else msg["content"]
                history_lines.append(f"{role}: {content}")
            context = "Recent conversation:\n" + "\n".join(history_lines) + "\n\n"

        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[
                {"role": "user", "content": f"{EXTRACT_PROMPT}\n\n{context}User message: {user_message}"}
            ],
        )

        raw = response.content[0].text.strip()
        # Strip markdown code blocks if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]  # Remove first line (```json)
            raw = raw.rsplit("```", 1)[0]  # Remove closing ```
            raw = raw.strip()

        result = json.loads(raw)
        logger.info(f"Extracted products: {result}")
        return result.get("products", []), result.get("is_specific", False)
    except Exception as e:
        logger.error(f"Product extraction failed: {e}")
        # Fallback: use the raw message words
        words = [w for w in user_message.lower().split() if len(w) > 3]
        return words, False


async def find_relevant_products(user_message: str, chat_history: list[dict] = None) -> tuple[list, bool]:
    """Find products relevant to the user's query using Claude for understanding."""
    product_names, is_specific = await extract_product_names(user_message, chat_history)

    if not product_names:
        return [], False

    # Search for each product name
    all_results = []
    for name in product_names:
        # Try exact match on the full product name
        keywords = name.lower().split()
        exact = await search_products_exact(keywords)
        if exact:
            all_results.extend(exact)
        else:
            # Fall back to broad search
            results = await search_products(name)
            all_results.extend(results)

    # Deduplicate by URL
    seen_urls = set()
    unique_products = []
    for product in all_results:
        if product.url not in seen_urls:
            seen_urls.add(product.url)
            unique_products.append(product)

    # Override is_specific if we got too many results
    if len(unique_products) > 2:
        is_specific = False

    return unique_products, is_specific


async def build_product_context(user_message: str, chat_history: list[dict] = None) -> tuple[str, list[dict]]:
    """Build context string and return matched product images."""
    unique_products, is_specific = await find_relevant_products(user_message, chat_history)

    # Only show images for specific product queries (1-2 results)
    product_images = []
    if is_specific:
        for product in unique_products:
            if product.image_url:
                product_images.append({
                    "title": product.title.replace(" | Hilma Biocare Website", ""),
                    "image_url": product.image_url,
                    "url": product.url,
                })

    # If no relevant products found, send compact catalog
    if not unique_products:
        all_products = await get_all_products()
        if not all_products:
            return "\n[No products have been scraped yet. The database is empty.]", []

        context_parts = ["\nFull product catalog (names only — ask for details on specific products):"]
        for product in all_products:
            context_parts.append(f"- {product.title} | {product.url}")
        return "\n".join(context_parts), []

    # Send detailed info for relevant products (max 10)
    products_to_send = unique_products[:10]
    context_parts = []
    for product in products_to_send:
        content = product.content
        if len(content) > MAX_CONTENT_LENGTH:
            content = content[:MAX_CONTENT_LENGTH] + "..."

        context_parts.append(
            f"--- Product from {product.source} ---\n"
            f"URL: {product.url}\n"
            f"{content}\n"
        )

    return "\n".join(context_parts), product_images


async def get_agent_response(user_message: str, chat_history: list[dict] = None) -> AgentResponse:
    """Get a response from the Claude agent for a user message."""
    try:
        product_context, product_images = await build_product_context(user_message, chat_history)
        system = SYSTEM_PROMPT + product_context

        # Build messages with conversation history
        messages = []
        if chat_history:
            messages.extend(chat_history)
        messages.append({"role": "user", "content": user_message})

        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system,
            messages=messages,
        )

        response_text = response.content[0].text

        # Show Shop button when response mentions products, ordering, or shop
        shop_keywords = ["shop", "Shop", "корзин", "магазин", "оформ", "заказ", "купить", "наличи", "цен", "price", "order", "available"]
        show_shop = any(kw in response_text for kw in shop_keywords) or bool(product_images)

        return AgentResponse(
            text=response_text,
            product_images=product_images,
            show_shop_button=show_shop,
        )

    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return AgentResponse(
            text="Sorry, I'm having trouble processing your request right now. Please try again in a moment.",
        )

import io

from aiogram import Bot, F, Router, types
from aiogram.enums import ChatAction
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions

from app.agents.sales_agent import AgentResponse, get_agent_response
from app.services.chat_history import add_message, get_history
from app.services.formatting import markdown_to_telegram_html
from app.services.voice import transcribe_voice

router = Router()

# Shop URL — Telegram mini app
SHOP_URL = "https://razvedka_rf_bot.miniapp-rf.app"

# Manager trigger words
MANAGER_TRIGGERS = {"менеджер", "manager", "менеджера", "оператор", "operator"}


def shop_keyboard() -> InlineKeyboardMarkup:
    """Create an inline keyboard with the Shop button."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Shop", url=SHOP_URL)]
    ])


def is_manager_request(text: str) -> bool:
    """Check if the user wants to speak with a manager."""
    return text.strip().lower() in MANAGER_TRIGGERS


async def send_response(message: types.Message, bot: Bot, response: AgentResponse) -> None:
    """Send the agent response with product images and Shop button."""
    formatted_text = markdown_to_telegram_html(response.text)

    if response.product_images:
        for product in response.product_images[:3]:
            try:
                await bot.send_photo(
                    chat_id=message.chat.id,
                    photo=product["image_url"],
                    caption=f"<b>{product['title']}</b>",
                    parse_mode="HTML",
                )
            except Exception:
                pass

    # Add Shop button when the response mentions ordering/shopping
    keyboard = shop_keyboard() if response.show_shop_button else None

    await message.answer(
        formatted_text,
        parse_mode="HTML",
        link_preview_options=LinkPreviewOptions(is_disabled=True),
        reply_markup=keyboard,
    )


@router.message(F.voice)
async def handle_voice(message: types.Message, bot: Bot) -> None:
    """Handle incoming voice messages."""
    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    file = await bot.get_file(message.voice.file_id)
    file_bytes = io.BytesIO()
    await bot.download_file(file.file_path, file_bytes)

    text = await transcribe_voice(file_bytes.getvalue())
    if not text:
        await message.answer("Sorry, I couldn't understand the voice message. Please try again or send a text message.")
        return

    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    history = await get_history(message.chat.id)
    response = await get_agent_response(text, chat_history=history)

    await add_message(message.chat.id, "user", text)
    await add_message(message.chat.id, "assistant", response.text)

    await message.answer(f"🎤 <i>{text}</i>")
    await send_response(message, bot, response)


@router.message(F.text)
async def handle_message(message: types.Message, bot: Bot) -> None:
    """Handle all incoming text messages."""
    # Manager handoff
    if is_manager_request(message.text):
        await message.answer(
            "Переключаем вас на менеджера. График работы: Пн-Пт 09:00-18:00 МСК.\n\n"
            "Connecting you with a manager. Working hours: Mon-Fri 09:00-18:00 Moscow time."
        )
        # TODO: Forward to manager chat/group
        return

    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    history = await get_history(message.chat.id)
    response = await get_agent_response(message.text, chat_history=history)

    await add_message(message.chat.id, "user", message.text)
    await add_message(message.chat.id, "assistant", response.text)

    await send_response(message, bot, response)


@router.message()
async def handle_other(message: types.Message) -> None:
    """Handle any other message type."""
    await message.answer("Please send a text or voice message and I'll help you find information.")

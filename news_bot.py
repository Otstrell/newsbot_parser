import logging
import requests
from bs4 import BeautifulSoup
from telegram import (
    Bot,
    Update,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "7818778997:AAGrrawghnCsdEJB2gfjNtTb-wwS4zQi-7Y"
CHANNEL_ID = "@Investt_Baza"  # или числовой ID -1001431430716

# -------------------------------------------------------------------
# Парсер для новостей с сайта
# -------------------------------------------------------------------
def get_latest_cryptonews():
    """
    Парсит https://cryptonews.net/ru/ и возвращает dict{title, link, description, image_url} или None.
    """
    url = "https://cryptonews.net/ru/"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Ошибка при запросе страницы: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    news_blocks = soup.select("div.row.news-item.start-xs")
    if not news_blocks:
        logger.error("Не найден блок .row.news-item.start-xs")
        return None

    first_news = news_blocks[0]
    title_elem = first_news.select_one("a.title")
    if not title_elem:
        logger.error("Не найден заголовок (a.title).")
        return None

    title = title_elem.get_text(strip=True)
    link = first_news.get("data-link") or title_elem.get("href", "")
    if link.startswith("/"):
        link = "https://cryptonews.net" + link

    image_url = first_news.get("data-image")
    domain = first_news.get("data-domain", "")
    date_elem = first_news.select_one(".datetime")
    date_text = date_elem.get_text(strip=True) if date_elem else ""
    description = f"{domain} | {date_text}".strip()

    return {
        "title": title,
        "link": link,
        "description": description,
        "image_url": image_url,
    }

# -------------------------------------------------------------------
# Публикация поста
# -------------------------------------------------------------------
async def publish_post(context: CallbackContext, chat_id: str, news: dict):
    bot: Bot = context.bot
    caption = (
        f"<b>{news['title']}</b>\n\n"
        f"{news['description']}\n\n"
        f"<a href='{news['link']}'>Читать далее</a>"
    )
    if news["image_url"]:
        try:
            r = requests.get(news["image_url"], timeout=10)
            r.raise_for_status()
            await bot.send_photo(
                chat_id=chat_id,
                photo=r.content,
                caption=caption,
                parse_mode="HTML",
            )
            logger.info(f"Пост отправлен в {chat_id}.")
        except Exception as e:
            logger.error(f"Ошибка при отправке фото: {e}")
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode="HTML",
            )
    else:
        await bot.send_message(
            chat_id=chat_id,
            text=caption,
            parse_mode="HTML",
        )
        logger.info(f"Пост отправлен в {chat_id}.")

# -------------------------------------------------------------------
# Тестовая публикация новости в канал
# -------------------------------------------------------------------
async def post_test_in_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    news = get_latest_cryptonews()
    if not news:
        await update.message.reply_text("Не удалось загрузить новость.")
        return

    await publish_post(context, CHANNEL_ID, news)
    await update.message.reply_text("Тестовый пост отправлен в канал.")

# -------------------------------------------------------------------
# Тестовая публикация новости в чат
# -------------------------------------------------------------------
async def post_test_in_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    news = get_latest_cryptonews()
    if not news:
        await update.message.reply_text("Не удалось загрузить новость.")
        return

    await publish_post(context, update.effective_chat.id, news)

# -------------------------------------------------------------------
# Автоматическая публикация новых новостей
# -------------------------------------------------------------------
async def auto_post_news(context: CallbackContext):
    bot_data = context.application.bot_data
    news = get_latest_cryptonews()
    if not news:
        logger.info("Нет новых новостей для публикации.")
        return

    last_link = bot_data.get("last_news_link")
    if last_link == news["link"]:
        logger.info("Новость уже публиковалась.")
        return

    bot_data["last_news_link"] = news["link"]
    await publish_post(context, CHANNEL_ID, news)

# -------------------------------------------------------------------
# /start: Меню с кнопками
# -------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        ["Перезапустить бота", "Тест пост — Канал"],
        ["Тест пост — Чат"]
    ]
    reply_kb = ReplyKeyboardMarkup(kb, resize_keyboard=True)

    await update.message.reply_text(
        "Бот запущен! Выберите действие:",
        reply_markup=reply_kb
    )

# -------------------------------------------------------------------
# Обработка кнопок
# -------------------------------------------------------------------
async def handle_reply_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "Перезапустить бота":
        await start_command(update, context)

    elif text == "Тест пост — Канал":
        await post_test_in_channel(update, context)

    elif text == "Тест пост — Чат":
        await post_test_in_chat(update, context)

    else:
        await update.message.reply_text("Неизвестная команда.")

# -------------------------------------------------------------------
# Основная функция
# -------------------------------------------------------------------
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reply_options))

    # Автоматическая публикация каждые 15 минут
    application.job_queue.run_repeating(auto_post_news, interval=15 * 60, first=0)

    application.run_polling()

if __name__ == "__main__":
    main()
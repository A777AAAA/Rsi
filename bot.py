import logging
import asyncio
import requests
import pandas as pd
from ta.momentum import RSIIndicator
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

TELEGRAM_BOT_TOKEN = '7713878854:AAFEDuZNkxKyzRIzuIHzootvoChkqS6_t7E'

DEFAULT_SYMBOL = 'BTC-USDT-SWAP'
DEFAULT_INTERVAL = '1h'
CHECK_INTERVAL_MINUTES = 5

user_settings = {}
active_users = set()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_ohlcv(symbol: str, interval: str, limit: int = 100):
    url = f'https://www.okx.com/api/v5/market/candles?instId={symbol}&bar={interval}&limit={limit}'
    response = requests.get(url)
    data = response.json()
    if data['code'] != '0':
        raise Exception(f"Ошибка OKX API: {data['msg']}")
    df = pd.DataFrame(data['data'], columns=[
        "timestamp", "open", "high", "low", "close", "volume", "_", "_", "_", "_", "_", "_"
    ])
    df = df.iloc[::-1].reset_index(drop=True)
    df['close'] = df['close'].astype(float)
    return df

def check_rsi(symbol: str, interval: str):
    df = get_ohlcv(symbol, interval)
    rsi = RSIIndicator(close=df['close'], window=14).rsi()
    latest_rsi = rsi.iloc[-1]
    crossed = None
    if rsi.iloc[-2] > 70 and latest_rsi <= 70:
        crossed = '🔻 RSI опустился ниже 70 (возможен разворот вниз)'
    elif rsi.iloc[-2] < 30 and latest_rsi >= 30:
        crossed = '🔺 RSI поднялся выше 30 (возможен разворот вверх)'
    return latest_rsi, crossed

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    user_settings[user_id] = {
        'symbol': DEFAULT_SYMBOL,
        'interval': DEFAULT_INTERVAL,
    }
    active_users.add(user_id)
    await update.message.reply_text(f'✅ Бот запущен!
Пара: {DEFAULT_SYMBOL}
Таймфрейм: {DEFAULT_INTERVAL}
Проверка RSI каждые {CHECK_INTERVAL_MINUTES} мин.')

async def set_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    if context.args:
        user_settings[user_id]['symbol'] = context.args[0]
        await update.message.reply_text(f'Пара изменена на {context.args[0]}')
    else:
        await update.message.reply_text('❗ Пример: /set_symbol ETH-USDT-SWAP')

async def set_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    if context.args:
        user_settings[user_id]['interval'] = context.args[0]
        await update.message.reply_text(f'Таймфрейм изменен на {context.args[0]}')
    else:
        await update.message.reply_text('❗ Пример: /set_interval 15m')

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    settings = user_settings.get(user_id, {
        'symbol': DEFAULT_SYMBOL,
        'interval': DEFAULT_INTERVAL
    })
    try:
        rsi_value, crossed = check_rsi(settings['symbol'], settings['interval'])
        response = f'📊 RSI: {rsi_value:.2f} на {settings["symbol"]} ({settings["interval"]})'
        if crossed:
            response += f'
⚠️ {crossed}'
        await update.message.reply_text(response)
    except Exception as e:
        await update.message.reply_text(f'Ошибка: {str(e)}')

async def rsi_notifier(app):
    while True:
        for user_id in active_users:
            settings = user_settings.get(user_id, {
                'symbol': DEFAULT_SYMBOL,
                'interval': DEFAULT_INTERVAL
            })
            try:
                rsi_value, crossed = check_rsi(settings['symbol'], settings['interval'])
                if crossed:
                    await app.bot.send_message(chat_id=user_id,
                        text=f'⚠️ Автоуведомление:
📊 RSI: {rsi_value:.2f}
{crossed}
({settings["symbol"]}, {settings["interval"]})')
            except Exception as e:
                logger.error(f'Ошибка при автоуведомлении: {e}')
        await asyncio.sleep(CHECK_INTERVAL_MINUTES * 60)

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("set_symbol", set_symbol))
    app.add_handler(CommandHandler("set_interval", set_interval))
    app.add_handler(CommandHandler("check", check))
    asyncio.get_event_loop().create_task(rsi_notifier(app))
    app.run_polling()

if __name__ == '__main__':
    main()

import random
import time
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import logging
from datetime import datetime
import asyncio
from flask import Flask, render_template, request, redirect, url_for, session
from flask_caching import Cache
from flask_socketio import SocketIO
from telegram.error import TelegramError
from threading import Thread
import hashlib
import hmac

logging.basicConfig(filename='bot_errors.log',
                    filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    level=logging.ERROR)

DATA_FILE = 'global_user_data.json'
global_user_data = {}
user_last_poop_time = {}
used_promo_codes = {}
last_command_time = {}
commands_for_poop = {"кака", "какать", "срать"}
group_chats = set()
chat_messages = {}
appFlask = Flask(__name__)
appFlask.secret_key = os.urandom(24)
bot_token = "7288586629:AAHuQ1qzfq5cGM4_BzT8UnOy4Io1GXLC5V8"
cache = Cache(config={'CACHE_TYPE': 'FileSystemCache', 'CACHE_DIR': 'cache-directory'})
cache.init_app(appFlask)
socketio = SocketIO(appFlask)
promo_codes = {
    "олд": 20.0,
    "чит": 10.0,
}

def load_data():
    """Загружает данные из файла."""
    global global_user_data, user_last_poop_time, used_promo_codes, group_chats

    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as file:
            data = json.load(file)
            # Преобразуем ключи из строк в числа
            global_user_data = {
                int(user_id): value
                for user_id, value in data.get('global_user_data', {}).items()
}
            user_last_poop_time = {
                int(user_id): timestamp
                for user_id, timestamp in data.get('user_last_poop_time', {}).items()
            }
            used_promo_codes = {
                int(user_id): promo_code
                for user_id, promo_code in data.get('used_promo_codes', {}).items()
            }
            group_chats = set(data.get('group_chats', []))
            chat_messages = data.get('chat_messages', {})

def save_data():
    """Сохраняет данные в файл."""
    data = {
        'global_user_data': {
            str(user_id): value
            for user_id, value in global_user_data.items()
        },
        'user_last_poop_time': {
            str(user_id): timestamp
            for user_id, timestamp in user_last_poop_time.items()
        },
        'used_promo_codes': {
            str(user_id): promo_code
            for user_id, promo_code in used_promo_codes.items()
        },
        'group_chats': list(group_chats),
        'chat_messages': chat_messages,
    }
    with open(DATA_FILE, 'w') as file:
        json.dump(data, file, indent=4)

def is_command_cooldown_valid(user_id: int) -> bool:
    current_time = time.time()
    if user_id in last_command_time:
        time_since_last_call = current_time - last_command_time[user_id]
        if time_since_last_call < 2:
            return False
    last_command_time[user_id] = current_time
    return True

async def message_handler(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    chat_id = update.message.chat_id
    user_id = user.id
    user_name = user.username
    current_time = time.time()

    if chat_id not in chat_messages:
        chat_messages[chat_id] = []
    chat_messages[chat_id].append({
        'text': update.message.text,
        'from_user': user_name,
        'date': datetime.now().isoformat()
    })
    if not is_command_cooldown_valid(user_id) or update.message is None or update.message.chat is None:
        return

    elif update.message.chat.type in ['group', 'supergroup']:
        if chat_id not in group_chats:
            group_chats.add(chat_id)
            print(f"Бота додано до нової групи: {chat_id}. Усього груп: {len(group_chats)}")
        textMessage = update.message.text.lower()

        if "/poop" in textMessage or textMessage in commands_for_poop:

            if user_id in user_last_poop_time:
                last_poop_time = user_last_poop_time[user_id]
                elapsed_time = current_time - last_poop_time
                if elapsed_time < 3600:
                    remaining_time = 3600 - elapsed_time
                    minutes, seconds = divmod(remaining_time, 60)
                    profile_link = f"[{user.full_name}](tg://user?id={user_id})"
                    if user_id in global_user_data:
                        current_value = global_user_data[user_id]["value"]
                    else:
                        current_value = 0.0
                    await context.bot.send_message(chat_id=chat_id, text=f"{profile_link}, повтори через {int(minutes)}м. {int(seconds)}с.\nВ твоей баночке сейчас {round(current_value, 2):.2f} л.", parse_mode='Markdown')
                    return
            user_last_poop_time[user_id] = current_time

            if user_id not in global_user_data:
                global_user_data[user_id] = {
                    "username": user_name,
                    "value": 0.0
                }

            random_value = round(random.uniform(-2, 10) + random.uniform(0, 0.99), 2)
            global_user_data[user_id]["value"] += random_value
            save_data()
            user_link = f"[{user.full_name}](https://t.me/{user_name})"
            if random_value < 0:
                await context.bot.send_message(chat_id=chat_id, text=f"О, нет!\n\n{user_link}, тебе помешали посрать ({random_value}).\nВ твоей баночке сейчас {round(global_user_data[user_id]['value'], 2):.2f} л.", parse_mode='Markdown', disable_web_page_preview=True)
            else:
                await context.bot.send_message(chat_id=chat_id, text=f"{user_link}, ты высрал(а) {random_value} л.\nВ твоей баночке сейчас {round(global_user_data[user_id]['value'], 2):.2f} л.", parse_mode='Markdown', disable_web_page_preview=True)
    else:
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        bot_name = bot_info.full_name
        bot_link = f"[{bot_name}](https://t.me/{bot_username})"
        await context.bot.send_message(chat_id=chat_id, text=f"{bot_link} работает только в группах.", parse_mode='Markdown', disable_web_page_preview=True)

async def private_message_handler(update: Update, context: CallbackContext) -> None:
    global bot
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    keyboard = [[InlineKeyboardButton("Добавить бота в группу", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    bot_info = await bot.get_me()
    bot_username = bot_info.username
    bot_name = bot_info.full_name
    user_link = f"[{bot_name}](https://t.me/{bot_username})"
    text = update.message.text.strip().lower()
    if not is_command_cooldown_valid(user_id):
        return

    elif text == "/start":
        await context.bot.send_message(chat_id=chat_id, text=f"Привет! 💩{user_link} — бот-линейка для групп (чатов)\n\n" "Раз в *час* игрок может ввести команду /poop, чтобы покакать 💩💩💩\n\n" "*Мои команды* — /help",
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True)

    elif text.startswith("#"):
        print(f"@{update.message.from_user.username} попытался активировать промокод {text}")
        promo_code = text[1:]
        if promo_code in promo_codes:
            if user_id not in used_promo_codes or promo_code not in used_promo_codes[user_id]:
                if user_id not in used_promo_codes:
                    used_promo_codes[user_id] = []
                used_promo_codes[user_id].append(promo_code)
                if user_id not in global_user_data:
                    global_user_data[user_id] = {
                        "username": update.message.from_user.username,
                        "value": 0.0
                    }
                bonus = promo_codes[promo_code]
                global_user_data[user_id]["value"] += bonus
                save_data()
                await context.bot.send_message(chat_id=chat_id, text=f"Вы получаете {bonus} литров за промокод.")
            else:
                await context.bot.send_message(chat_id=chat_id, text="Этот промокод уже был использован.")
        else:
            await context.bot.send_message(chat_id=chat_id, text="Неизвестный промокод.")
        return

    elif text.startswith("добавить"):
        if user_id == 5046805682:
            change = ''.join(text.split()[1:])
            global_user_data[5046805682]["value"] += float(change)
            await context.bot.send_message(chat_id=chat_id, text=f"change {change}")

    elif text != "/help":
        await context.bot.send_message(chat_id=chat_id, text=f"💩{user_link} работает только в группах.", reply_markup=reply_markup, parse_mode='Markdown', disable_web_page_preview=True)

async def help_command(update: Update, context: CallbackContext) -> None:
    if not is_command_cooldown_valid(update.message.from_user.id):
        return
    await update.message.reply_text(
        "*Команды бота:*\n"
        "/poop — Какать\n"
        "/stats — Рейтинг чата\n"
        "/top — Топ 10 игроков",
        parse_mode='Markdown'
    )

def get_id_by_username(username: str, user_data: dict) -> str:
    for user_id, data in user_data.items():
        if data['username'] == username:
            return user_id
    return None

async def toppoop(update: Update, context: CallbackContext) -> None:
    if not is_command_cooldown_valid(update.message.from_user.id):
        return
    chat_id = update.message.chat_id
    messageToppoop = ""
    try:
        top_users = sorted(global_user_data.items(), key=lambda x: x[1]['value'], reverse=True)
        if top_users:
            messageToppoop = "Рейтинг чата\n"
            for idx, (user_id, data) in enumerate(top_users, 1):
                id = get_id_by_username(data['username'], global_user_data)
                if id is not None:
                    try:
                        chat_member = await context.bot.get_chat_member(chat_id=chat_id, user_id=id)
                        if chat_member.status in ['member', 'administrator', 'creator']:
                            value = round(data['value'], 2)
                            messageToppoop += f"\n{idx}. {data['username']}: {value} л."
                    except Exception as e:
                        logging.error(f"Error fetching chat member {data['username']} (ID: {id}): {e}")
        else:
            messageToppoop = "Нет данных для отображения рейтинга чата."
    except Exception as e:
        logging.error(f"Error in toppoop: {e}")
        messageToppoop = "Произошла ошибка при попытке отображения рейтинга чата."
    await update.message.reply_text(messageToppoop)

async def globaltop(update: Update, context: CallbackContext) -> None:
    if not is_command_cooldown_valid(update.message.from_user.id):
        return
    top_users = sorted(global_user_data.items(), key=lambda x: x[1]['value'], reverse=True)[:10]
    messageGlobaltop = " "
    if top_users:
        messageGlobaltop = "Глобальный топ 10 игроков\n"
        for idx, (user_id, data) in enumerate(top_users, 1):
            value = round(data['value'], 2)
            messageGlobaltop += f"\n{idx}. {data['username']}: {value} л."
    else:
        messageGlobaltop = "Нет данных для отображения глобального топ 10."
    await update.message.reply_text(messageGlobaltop)


async def broadcast_message(context: CallbackContext):
    for chat_id in group_chats:
        try:
            await context.bot.send_message(chat_id=chat_id, text="Новый промокод🚀\n\nВсем привет! 🎉\nИспользуйте промокод #олд (в лс с ботом) и получите +20 л. в свою банку! 🎁")
            print("🚀Відправлено: " + str(chat_id))
        except Exception as e:
            print(f"Не вдалося відправити: {chat_id}: {str(e)}")

# 17 вер 2024 11:00
async def schedule_broadcast(context: CallbackContext):
    target_time = datetime(2024, 9, 17, 9, 0, 0)
    time_to_wait = (target_time - datetime.now()).total_seconds()

    if time_to_wait > 0:
        print(f"Заплановано розсилку на {target_time}.\nЗалишилось {time_to_wait} секунд.")
        await asyncio.sleep(time_to_wait)
        await broadcast_message(context)
    else:
        print("Час для розсилки вже минув.")

def verify_telegram_auth(data: dict) -> bool:
    if 'hash' not in data:
        return False
    check_hash = data.pop('hash')
    sorted_data = sorted(f'{key}={value}' for key, value in data.items())
    data_check_string = '\n'.join(sorted_data)
    
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    return calculated_hash == check_hash

@appFlask.route('/')
def main():
    return redirect(url_for('login'))

@appFlask.route('/login')
def login():
    user_id = session.get('user_id')
    if not user_id or not cache.get(f"user_session_{user_id}"):
        return render_template('login.html')
    return redirect(url_for('chats'))

def checkAuchTelegramLogin() -> bool:
    user_data = request.args.to_dict()
    if verify_telegram_auth(user_data):
        user_id_logedin = user_data.get('id')
        if str(user_id_logedin) == '5046805682':
            session['user_id'] = user_id_logedin
            cache.set(f"user_session_{user_id_logedin}", True, timeout=3600)
            return True
    return False

@appFlask.route('/auth')
def auth():
    if checkAuchTelegramLogin():
        return redirect(url_for('chats'))
    else:
        return "Ви не маєте доступу до цієї сторінки.", 403

@appFlask.route('/logout')
def logout():
    user_id_logedin = session.get('user_id')
    if user_id_logedin:
        cache.delete(f"user_session_{user_id_logedin}")
    session.clear()
    return redirect(url_for('login'))
    
@appFlask.route('/chats', methods=['GET'])
def chats():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session['user_id'] != '5046805682':
        return "Ви не маєте доступу до цієї сторінки.", 403

    try:
        chats = []
        for chat_id in list(group_chats):
            try:
                chat = bot.get_chat(chat_id)
                chats.append({
                    'title': chat.title,
                    'id': chat_id,
                    'type': chat.type
                })
            except TelegramError as e:
                print(f"Помилка при отриманні чату {chat_id}: {e}")

        return render_template('chats.html', chats=chats)

    except Exception as e:
        return f"Помилка: {str(e)}"

@appFlask.route('/chat/<chat_id>')
def chat_history(chat_id):
    try:
        chat_id = int(chat_id)
        
        messages = chat_messages.get(chat_id, [])
        formatted_messages = [{
            'text': message['text'],
            'from_user': message['from_user'],
            'date': message['date']
        } for message in messages]
        
        return render_template('history.html', messages=formatted_messages, chat_id=chat_id)
    except Exception as e:
        return f"Помилка: {str(e)}"

def main():
    global bot
    app = Application.builder().token(bot_token).build()
    bot = app.bot
    load_data()
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", toppoop, filters.ChatType.GROUPS))
    app.add_handler(CommandHandler("top", globaltop))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, private_message_handler))
    app.add_handler(MessageHandler(filters.TEXT, message_handler))
    print("Бот успішно запущено.")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(schedule_broadcast(app))
    loop.run_until_complete(app.run_polling())

if __name__ == '__main__':
    thread = Thread(target=lambda: appFlask.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False))
    thread.start()
    main()

  

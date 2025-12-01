import os
import json
import threading
import time
from datetime import datetime
import logging

from telebot import TeleBot, types
from flask import Flask, request
import yt_dlp

# ============================================================
#                     ПІДКЛЮЧЕННЯ МОВ
# ============================================================
# Переконайтеся, що файл languages.py лежить поруч
try:
    from languages import texts   # 🇺🇦 🇬🇧 🇷🇺 🇫🇷 🇩🇪
except ImportError:
    # Заглушка, якщо файлу немає, щоб код не впав при тесті
    texts = {"uk": {"welcome": "Привіт!", "loading": "Завантаження...", "error": "Помилка", "menu": "Меню"}}

# ============================================================
#                     КОНФІГУРАЦІЯ
# ============================================================

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    # Для локального тестування можна вписати токен сюди, але на сервері краще через ENV
    print("⚠️ ПОПЕРЕДЖЕННЯ: TOKEN не знайдено в змінних середовища.")

WEBHOOK_HOST = "https://dowlanderbot.onrender.com" # Змініть на вашу адресу
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = WEBHOOK_HOST + WEBHOOK_PATH

# 🔥 ВАЖЛИВО: прибрали threaded=False, щоб бот працював швидко
bot = TeleBot(TOKEN)
app = Flask(__name__)

# Налаштування логування
logging.basicConfig(level=logging.INFO)

USER_FILE = "users.json"
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ============================================================
#                   СИСТЕМА КОРИСТУВАЧІВ
# ============================================================

# Простий м'ютекс для запису файлу, щоб потоки не сварилися
file_lock = threading.Lock()

def load_users():
    if os.path.exists(USER_FILE):
        try:
            with open(USER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_users(data):
    with file_lock:
        with open(USER_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

users = load_users()

def get_user(u):
    uid = str(u.id)
    if uid not in users:
        users[uid] = {
            "name": u.first_name or "User",
            "subscription": "free",
            "videos_downloaded": 0,
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "language": "uk",
            "format": "mp4",
            "video_plus_audio": True
        }
        save_users(users)
    
    # Перевірка наявності мови
    if users[uid]["language"] not in texts:
        users[uid]["language"] = "uk"
    
    return users[uid]

# ============================================================
#                   ДОПОМІЖНІ ФУНКЦІЇ
# ============================================================

def clean_text(text):
    import re
    return re.sub(
        r"[^a-zA-Zа-яА-ЯёЁіІїЇєЄçÇčČšŠğĞüÜöÖâÂêÊôÔùÙàÀéÉ0-9 ]",
        "",
        text or ""
    ).strip().lower()

CMD = {
    "menu": ["меню", "menu", "menü"],
    "profile": ["профіль", "проф", "profile", "profil"],
    "settings": ["налаштування", "налаш", "настройки", "settings", "einstellungen", "paramètres"],
    "language": ["мова", "язык", "language", "langue", "sprache"],
    "subscription": ["підписка", "подписка", "subscription", "abonnement"],
    "help": ["про бота", "help", "about", "о боте", "à propos"],
    "back": ["назад", "back", "retour", "zurück"]
}

def match_cmd(text):
    text = clean_text(text)
    for cmd, variants in CMD.items():
        for v in variants:
            if clean_text(v) in text:
                return cmd
    return None

# ============================================================
#                   КЛАВІАТУРИ (MENU)
# ============================================================

def main_menu(user):
    t = texts[user["language"]]
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.row(types.KeyboardButton(f"📋 {t['menu']}"), types.KeyboardButton(f"👤 {t['profile']}"))
    kb.row(types.KeyboardButton(f"⚙️ {t['settings']}"), types.KeyboardButton(f"💎 {t['subscription']}"))
    kb.row(types.KeyboardButton(f"🌍 {t['language']}"), types.KeyboardButton(f"ℹ️ {t['help']}"))
    return kb

def settings_keyboard(user):
    t = texts[user["language"]]
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(
        types.InlineKeyboardButton(f"{'✅ ' if user['format']=='mp4' else ''}MP4", callback_data="format_mp4"),
        types.InlineKeyboardButton(f"{'✅ ' if user['format']=='mp3' else ''}MP3", callback_data="format_mp3"),
    )
    
    # Стан перемикача
    state = f"✔ {t.get('yes', 'Yes')}" if user["video_plus_audio"] else f"✖ {t.get('no', 'No')}"
    kb.add(types.InlineKeyboardButton(f"🎵+🎬 {state}", callback_data="toggle_vpa"))
    kb.add(types.InlineKeyboardButton("⬅ " + t.get("back", "Back"), callback_data="cmd_back"))
    return kb

# ============================================================
#            ЛОГІКА ЗАВАНТАЖЕННЯ (THREADED)
# ============================================================

def run_download_task(url, chat_id, user_data, lang):
    """
    Виконується в окремому потоці.
    """
    t = texts[lang]
    downloaded_files = []
    
    # 1. Відправляємо "Завантаження..."
    try:
        status_msg = bot.send_message(chat_id, f"⏳ {t['loading']}...")
    except Exception as e:
        logging.error(f"Cannot send message: {e}")
        return

    # 2. Налаштування yt-dlp
    timestamp = int(time.time())
    
    ydl_opts = {
        'outtmpl': f'{DOWNLOAD_DIR}/{chat_id}_{timestamp}_%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'max_filesize': 50 * 1024 * 1024, # 50 MB ліміт Telegram Bot API
        'noplaylist': True,
        # Маскуємося під браузер, щоб TikTok/Instagram не блокували
        'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'},
    }

    if user_data["format"] == "mp3":
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    else:
        # Пріоритет MP4 для сумісності з iOS/Android плеєрами
        ydl_opts.update({
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        })

    try:
        # 3. Процес завантаження
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Отримуємо ім'я файлу
            filename = ydl.prepare_filename(info)
            if user_data["format"] == "mp3":
                # yt-dlp змінює розширення після конвертації
                filename = os.path.splitext(filename)[0] + ".mp3"
            
            if os.path.exists(filename):
                downloaded_files.append(filename)

                # 4. Відправка файлу
                with open(filename, 'rb') as f:
                    if user_data["format"] == "mp3":
                        bot.send_chat_action(chat_id, 'upload_voice')
                        bot.send_audio(chat_id, f, caption="@dowlanderbot", title=info.get('title', 'Audio'))
                    else:
                        bot.send_chat_action(chat_id, 'upload_video')
                        bot.send_video(chat_id, f, caption=f"{info.get('title', '')}\n\n@dowlanderbot", supports_streaming=True)
                
                # Оновлення статистики
                user_data['videos_downloaded'] += 1
                save_users(users)
                
                # Видаляємо повідомлення "Завантаження"
                try:
                    bot.delete_message(chat_id, status_msg.message_id)
                except:
                    pass
            else:
                raise Exception("File not found after download")

    except yt_dlp.utils.DownloadError as e:
        logging.error(f"Download Error: {e}")
        bot.edit_message_text(f"❌ {t.get('download_failed', 'Download failed. Check URL or size.')}", chat_id, status_msg.message_id)
    except Exception as e:
        logging.error(f"General Error: {e}")
        bot.edit_message_text(f"❌ Error: {str(e)}", chat_id, status_msg.message_id)
    finally:
        # 5. Очистка (Видалення файлів)
        for f in downloaded_files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception as e:
                    logging.error(f"Cleanup error: {e}")

# ============================================================
#                     CALLBACK HANDLER
# ============================================================

@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    user = get_user(c.from_user)
    t = texts[user["language"]]
    data = c.data

    try:
        bot.answer_callback_query(c.id)
    except:
        pass

    if data == "cmd_back" or data == "cmd_menu":
        bot.send_message(c.message.chat.id, t.get("enter_url", "Send Link"), reply_markup=main_menu(user))
    
    elif data == "cmd_settings":
        bot.edit_message_text(f"⚙️ {t['settings']}:", c.message.chat.id, c.message.message_id, reply_markup=settings_keyboard(user))

    elif data.startswith("lang_"):
        new_lang = data.replace("lang_", "")
        user["language"] = new_lang
        save_users(users)
        bot.send_message(c.message.chat.id, texts[new_lang]["welcome"], reply_markup=main_menu(user))
        # Видаляємо старе повідомлення вибору мови
        try:
            bot.delete_message(c.message.chat.id, c.message.message_id)
        except:
            pass

    elif data.startswith("format_"):
        fmt = data.replace("format_", "")
        user["format"] = fmt
        save_users(users)
        bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=settings_keyboard(user))

    elif data == "toggle_vpa":
        user["video_plus_audio"] = not user["video_plus_audio"]
        save_users(users)
        bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=settings_keyboard(user))

# ============================================================
#                     MESSAGE HANDLERS
# ============================================================

@bot.message_handler(commands=["start"])
def start(m):
    u = get_user(m.from_user)
    t = texts[u["language"]]
    bot.send_message(m.chat.id, t["welcome"], reply_markup=main_menu(u))

@bot.message_handler(func=lambda m: True)
def message_handler(m):
    u = get_user(m.from_user)
    t = texts[u["language"]]
    raw = m.text or ""
    txt = clean_text(raw)

    # 1. Перевірка на URL
    if "http" in raw: # Проста перевірка
        # 🔥 ЗАПУСК В ОКРЕМОМУ ПОТОЦІ
        threading.Thread(
            target=run_download_task,
            args=(raw, m.chat.id, u, u["language"]),
            daemon=True
        ).start()
        return

    # 2. Перевірка команд
    cmd = match_cmd(txt)

    if cmd == "menu":
        bot.send_message(m.chat.id, t.get("enter_url", "Send Link"), reply_markup=main_menu(u))
        return

    if cmd == "profile":
        msg = (
            f"👤 {t['profile']}\n\n"
            f"👋 {t.get('lbl_name', 'Name')}: {u['name']}\n"
            f"🎥 {t.get('lbl_downloaded', 'Downloads')}: {u['videos_downloaded']}\n"
            f"🎞️ Format: {u['format'].upper()}\n"
        )
        bot.send_message(m.chat.id, msg, reply_markup=main_menu(u))
        return

    if cmd == "settings":
        bot.send_message(m.chat.id, f"⚙️ {t['settings']}:", reply_markup=settings_keyboard(u))
        return

    if cmd == "language":
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk"))
        kb.add(types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"))
        # Додайте інші мови тут
        bot.send_message(m.chat.id, t["language"], reply_markup=kb)
        return

    if cmd == "help":
        bot.send_message(m.chat.id, t.get("help_text", "Help info..."), reply_markup=main_menu(u))
        return

    # Якщо нічого не зрозуміло
    bot.send_message(m.chat.id, t.get("not_understood", "???"), reply_markup=main_menu(u))

# ============================================================
#                     FLASK WEBHOOK
# ============================================================

@app.route("/", methods=["GET"])
def home():
    return "Bot is running!", 200

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    else:
        return "Forbidden", 403

# ============================================================
#                        ЗАПУСК
# ============================================================

if __name__ == "__main__":
    # Налаштування команд бота при старті
    try:
        bot.delete_webhook()
        time.sleep(1)
        bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
        print(f"✅ Webhook встановлено: {WEBHOOK_URL}")
    except Exception as e:
        print(f"❌ Помилка Webhook: {e}")

    # Запуск Flask сервера
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

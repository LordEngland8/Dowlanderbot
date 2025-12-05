import os
import threading
import time
import re
import logging
from datetime import datetime

from telebot import TeleBot, types, apihelper
from flask import Flask, request
import yt_dlp

# ============================================================
#                     ПІДКЛЮЧЕННЯ МОВ
# ============================================================
try:
    from languages import texts
except ImportError:
    # Заглушка, якщо файлу немає, щоб код не впав при копіюванні
    texts = {
        "uk": {
            "menu": "Меню", "profile": "Профіль", "settings": "Налаштування",
            "language": "Мова", "subscription": "Підписка", "help": "Допомога",
            "back": "Назад", "yes": "Так", "no": "Ні", "loading": "Завантаження",
            "download_failed": "Помилка завантаження", "enter_url": "Надішліть посилання",
            "settings_title": "Налаштування завантаження", "welcome": "Привіт!",
            "profile_title": "Ваш профіль", "lbl_name": "Ім'я", "lbl_subscription": "Підписка",
            "lbl_downloaded": "Завантажено", "lbl_format": "Формат", "lbl_since": "З нами з",
            "lbl_video_plus_audio": "Відео + Аудіо файл", "free_version": "Безкоштовна версія",
            "help_text": "Надішліть посилання з TikTok, YouTube, Instagram...", 
            "not_understood": "Я не розумію цю команду."
        }
    }
    # Дублюємо для інших мов, щоб не було помилок
    for l in ["en", "ru", "fr", "de"]:
        texts[l] = texts["uk"]

# ============================================================
#                     КОНФІГУРАЦІЯ
# ============================================================
TOKEN = os.getenv("TOKEN")
# Якщо тестуєте локально, вставте токен сюди, але для Render краще через ENV
if not TOKEN:
    print("⚠️ УВАГА: TOKEN не знайдено в змінних середовища.")

WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "https://dowlanderbot.onrender.com")
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = WEBHOOK_HOST + WEBHOOK_PATH

bot = TeleBot(TOKEN)
app = Flask(__name__)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

LANGUAGE_OPTIONS = [
    ("uk", "🇺🇦 Українська"),
    ("en", "🇬🇧 English"),
    ("ru", "🇷🇺 Русский"),
    ("fr", "🇫🇷 Français"),
    ("de", "🇩🇪 Deutsch")
]

# ============================================================
#              ГЕНЕРАЦІЯ КОМАНД ДЛЯ ВСІХ МОВ
# ============================================================
def build_cmd_map():
    cmd_map = {
        "menu": [], "profile": [], "settings": [], "language": [],
        "subscription": [], "help": [], "back": []
    }
    for lang, pack in texts.items():
        cmd_map["menu"].append(pack["menu"].lower())
        cmd_map["profile"].append(pack["profile"].lower())
        cmd_map["settings"].append(pack["settings"].lower())
        cmd_map["language"].append(pack["language"].lower())
        cmd_map["subscription"].append(pack["subscription"].lower())
        cmd_map["help"].append(pack["help"].lower())
        cmd_map["back"].append(pack["back"].lower())
    return cmd_map

CMD = build_cmd_map()

# ============================================================
#               ЗБЕРЕЖЕННЯ В ПАМ'ЯТІ (RAM)
# ============================================================

# Словник для зберігання даних користувачів в оперативній пам'яті
users = {} 

def clean_text(text):
    return re.sub(r"[^a-zA-Zа-яА-ЯіІїЇєЄ0-9]+", "", text or "").lower()

def match_cmd(text):
    text = clean_text(text)
    for cmd, variants in CMD.items():
        for v in variants:
            if clean_text(v) == text:
                return cmd
    return None

def get_user(u):
    uid = str(u.id)
    if uid not in users:
        # Створення профілю (живе до перезапуску бота)
        users[uid] = {
            "name": u.first_name or "User",
            "subscription": "free",
            "videos_downloaded": 0,
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "language": "uk",
            "format": "mp4",
            "video_plus_audio": True
        }
    
    # Перевірка наявності мови
    if users[uid]["language"] not in texts:
        users[uid]["language"] = "uk"

    return users[uid]

# ============================================================
#                     КЛАВІАТУРИ
# ============================================================

def main_menu(user):
    t = texts[user["language"]]
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(f"📋 {t['menu']}", f"👤 {t['profile']}")
    kb.row(f"⚙️ {t['settings']}", f"💎 {t['subscription']}")
    kb.row(f"🌍 {t['language']}", f"ℹ️ {t['help']}")
    return kb

def settings_keyboard(user):
    t = texts[user["language"]]
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton(f"{'✅ ' if user['format']=='mp4' else ''}MP4", callback_data="format_mp4"),
        types.InlineKeyboardButton(f"{'✅ ' if user['format']=='mp3' else ''}MP3", callback_data="format_mp3")
    )
    state = t["yes"] if user["video_plus_audio"] else t["no"]
    kb.add(types.InlineKeyboardButton(f"{t['lbl_video_plus_audio']}: {state}", callback_data="toggle_vpa"))
    kb.add(types.InlineKeyboardButton(f"⬅ {t['back']}", callback_data="cmd_back"))
    return kb

def language_keyboard():
    kb = types.InlineKeyboardMarkup()
    for code, name in LANGUAGE_OPTIONS:
        kb.add(types.InlineKeyboardButton(name, callback_data=f"lang_{code}"))
    return kb

# ============================================================
#              ЗАВАНТАЖЕННЯ ВІДЕО + АУДІО
# ============================================================

def run_download_task(url, chat_id, user, lang):
    t = texts[lang]
    file_path = None
    message_id = None

    try:
        m = bot.send_message(chat_id, f"⏳ {t['loading']}...")
        message_id = m.message_id
    except:
        return

    ts = int(time.time())

    # Налаштування без лімітів розміру
    ydl_opts = {
        "outtmpl": f"{DOWNLOAD_DIR}/{chat_id}_{ts}_%(id)s.%(ext)s",
        "quiet": True,
        "noplaylist": True,
        "no_warnings": True,
        "http_headers": {"User-Agent": "Mozilla/5.0"},
        # Ліміт прибрано, але Telegram не прийме >50MB
    }

    if user["format"] == "mp3":
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }]
        })
    else:
        # Завантажуємо найкращу якість
        if user["video_plus_audio"]:
            ydl_opts["format"] = "bestvideo[ext=mp4]+bestaudio/best/best[ext=mp4]/best"
        else:
            ydl_opts["format"] = "best[ext=mp4]/best"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

            if user["format"] == "mp3":
                filename = filename.rsplit(".", 1)[0] + ".mp3"

            if not os.path.exists(filename):
                raise Exception("File missing")

            file_path = filename
            
            # Перевірка розміру для логування (Telegram ліміт ~50MB)
            file_size = os.path.getsize(file_path)
            if file_size > 50 * 1024 * 1024:
                bot.send_message(chat_id, "⚠️ Файл занадто великий (>50MB). Telegram може не дозволити його відправити.")

            # ВІДПРАВКА ВІДЕО
            if user["format"] == "mp4":
                with open(file_path, "rb") as f:
                    bot.send_video(
                        chat_id, f,
                        caption=f"{info.get('title')}\n@dowlanderbot",
                        supports_streaming=True
                    )

                # Екстракція аудіо (залишено стару логіку через ffmpeg, як ви просили)
                if user["video_plus_audio"]:
                    audio_path = file_path.rsplit(".", 1)[0] + ".mp3"
                    cmd = f'ffmpeg -i "{file_path}" -vn -acodec mp3 -y "{audio_path}" -loglevel quiet'
                    os.system(cmd)

                    if os.path.exists(audio_path):
                        time.sleep(0.4)
                        with open(audio_path, "rb") as af:
                            bot.send_audio(
                                chat_id, af,
                                caption=f"{info.get('title')} — Audio\n@dowlanderbot"
                            )
                        os.remove(audio_path)

            # ВІДПРАВКА ТІЛЬКИ АУДІО (MP3 режим)
            else:
                with open(file_path, "rb") as f:
                    bot.send_audio(chat_id, f, caption="@dowlanderbot")

            user["videos_downloaded"] += 1
            # save_users більше не потрібен

    except apihelper.ApiTelegramException as e:
        if "Request Entity Too Large" in str(e):
             bot.send_message(chat_id, "❌ Файл занадто великий для відправки через Telegram (Ліміт 50МБ).")
        else:
             logging.error(f"Telegram API Error: {e}")
             bot.send_message(chat_id, "❌ Помилка при відправці файлу.")

    except Exception as e:
        logging.error(f"DOWNLOAD ERROR: {e}")
        bot.send_message(chat_id, f"❌ {t['download_failed']}")

    finally:
        try:
            if message_id:
                bot.delete_message(chat_id, message_id)
        except: pass
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except: pass

# ============================================================
#                     CALLBACKS
# ============================================================

@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    user = get_user(c.from_user)
    t = texts[user["language"]]
    data = c.data
    chat_id = c.message.chat.id

    if data == "cmd_back":
        bot.send_message(chat_id, t["enter_url"], reply_markup=main_menu(user))

    elif data == "cmd_settings":
        bot.edit_message_text(t["settings_title"], chat_id, c.message.message_id, reply_markup=settings_keyboard(user))

    elif data == "cmd_language":
        bot.edit_message_text(t["language"], chat_id, c.message.message_id, reply_markup=language_keyboard())

    elif data.startswith("lang_"):
        lang = data.replace("lang_", "")
        user["language"] = lang
        bot.send_message(chat_id, texts[lang]["welcome"], reply_markup=main_menu(user))

    elif data.startswith("format_"):
        user["format"] = data.replace("format_", "")
        bot.edit_message_reply_markup(chat_id, c.message.message_id, reply_markup=settings_keyboard(user))

    elif data == "toggle_vpa":
        user["video_plus_audio"] = not user["video_plus_audio"]
        bot.edit_message_reply_markup(chat_id, c.message.message_id, reply_markup=settings_keyboard(user))

# ============================================================
#                     MESSAGE HANDLER
# ============================================================

@bot.message_handler(commands=["start"])
def start_handler(m):
    user = get_user(m.from_user)
    t = texts[user["language"]]
    bot.send_message(m.chat.id, t["welcome"], reply_markup=main_menu(user))

@bot.message_handler(func=lambda m: True)
def message_handler(m):
    user = get_user(m.from_user)
    t = texts[user["language"]]
    text = m.text or ""

    if text.startswith("http"):
        threading.Thread(
            target=run_download_task,
            args=(text, m.chat.id, user, user["language"]),
            daemon=True
        ).start()
        return

    cmd = match_cmd(text)

    if cmd == "menu":
        bot.send_message(m.chat.id, t["enter_url"], reply_markup=main_menu(user))
    elif cmd == "profile":
        msg = (
            f"👤 {t['profile_title']}\n"
            f"ID: `{m.from_user.id}`\n"
            f"{t['lbl_name']}: {user['name']}\n"
            f"{t['lbl_subscription']}: {user['subscription']}\n"
            f"{t['lbl_downloaded']}: {user['videos_downloaded']}\n"
            f"{t['lbl_format']}: {user['format']}\n"
            f"{t['lbl_since']}: {user['joined']}"
        )
        bot.send_message(m.chat.id, msg, parse_mode="Markdown", reply_markup=main_menu(user))
    elif cmd == "settings":
        bot.send_message(m.chat.id, t["settings_title"], reply_markup=settings_keyboard(user))
    elif cmd == "language":
        bot.send_message(m.chat.id, t["language"], reply_markup=language_keyboard())
    elif cmd == "subscription":
        bot.send_message(m.chat.id, t["free_version"], reply_markup=main_menu(user))
    elif cmd == "help":
        bot.send_message(m.chat.id, t["help_text"], reply_markup=main_menu(user))
    else:
        bot.send_message(m.chat.id, t["not_understood"], reply_markup=main_menu(user))

# ============================================================
#                       WEBHOOK
# ============================================================

@app.route("/", methods=["GET"])
def home():
    return "Bot is running!", 200

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        json_string = request.get_data().decode("utf-8")
        update = types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403

if __name__ == "__main__":
    logging.info("🚀 Запуск Webhook")
    try:
        bot.delete_webhook()
        time.sleep(0.3)
        bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
        logging.info(f"✅ Webhook встановлено: {WEBHOOK_URL}")
    except Exception as e:
        logging.error(f"Webhook error: {e}")

    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

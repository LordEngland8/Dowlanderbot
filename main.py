import os
import json
import threading
import time
import re
import logging
from datetime import datetime

from telebot import TeleBot, types
from flask import Flask, request
import yt_dlp
from yt_dlp.utils import DownloadError

# ============================================================
#                     ПІДКЛЮЧЕННЯ МОВ
# ============================================================
try:
    from languages import texts
except ImportError:
    raise ImportError("❌ Не вдалося імпортувати texts. Переконайтеся, що файл languages.py існує.")

# ============================================================
#                     КОНФІГУРАЦІЯ
# ============================================================
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("❌ TOKEN не встановлено! Встановіть змінну середовища.")

WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "https://dowlanderbot.onrender.com")
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = WEBHOOK_HOST + WEBHOOK_PATH

bot = TeleBot(TOKEN)
app = Flask(__name__)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
USER_FILE = "users.json"
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Мови
LANGUAGE_OPTIONS = [
    ("uk", "🇺🇦 Українська"),
    ("en", "🇬🇧 English"),
    ("ru", "🇷🇺 Русский"),
    ("fr", "🇫🇷 Français"),
    ("de", "🇩🇪 Deutsch")
]

# ============================================================
#                   СИСТЕМА КОРИСТУВАЧІВ
# ============================================================
file_lock = threading.Lock()

def load_users():
    if os.path.exists(USER_FILE):
        try:
            with open(USER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Помилка завантаження users.json: {e}")
            return {}
    return {}

def save_users(data):
    with file_lock:
        try:
            with open(USER_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Помилка збереження users.json: {e}")

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

    if users[uid].get("language") not in texts:
        users[uid]["language"] = "uk"
        save_users(users)

    return users[uid]

# ============================================================
#                   КОМАНДИ
# ============================================================
def clean_text(text):
    return re.sub(r"[^a-zA-Zа-яА-ЯёЁіІїЇєЄ0-9 ]", "", text or "").strip().lower()

CMD = {
    "menu": ["меню", "menu", "menü"],
    "profile": ["профіль", "profile", "profil"],
    "settings": ["налаштування", "settings", "настройки"],
    "language": ["мова", "language", "язык"],
    "subscription": ["підписка", "subscription", "подписка"],
    "help": ["про бота", "help", "about"],
    "back": ["назад", "back"]
}

def match_cmd(text):
    text = clean_text(text)
    for cmd, variants in CMD.items():
        for v in variants:
            if clean_text(v) in text:
                return cmd
    return None

# ============================================================
#                   КЛАВІАТУРИ
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

    state = f"✔ {t['yes']}" if user["video_plus_audio"] else f"✖ {t['no']}"
    kb.add(types.InlineKeyboardButton(f"{t['lbl_video_plus_audio']}: {state}", callback_data="toggle_vpa"))

    kb.add(types.InlineKeyboardButton("⬅ " + t["back"], callback_data="cmd_back"))
    return kb

def language_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    for code, name in LANGUAGE_OPTIONS:
        kb.add(types.InlineKeyboardButton(name, callback_data=f"lang_{code}"))
    return kb

# ============================================================
#                   ЗАВАНТАЖЕННЯ
# ============================================================
def download_progress_hook(d, chat_id, message_id):
    if not hasattr(download_progress_hook, 'last_update'):
        download_progress_hook.last_update = 0

    if d['status'] == 'downloading':
        p = d['_percent_str'].strip()
        s = d['_speed_str'].strip()

        if time.time() - download_progress_hook.last_update > 2:
            try:
                bot.edit_message_text(
                    f"⏳ **Завантаження:** {p}\n➡️ {s}",
                    chat_id, message_id, parse_mode="Markdown"
                )
                download_progress_hook.last_update = time.time()
            except:
                pass

def run_download_task(url, chat_id, user_data, lang):
    t = texts[lang]
    file_path = None

    try:
        msg = bot.send_message(chat_id, f"⏳ {t['loading']}...")
        message_id = msg.message_id
    except:
        return

    timestamp = int(time.time())

    ydl_opts = {
        'outtmpl': f'{DOWNLOAD_DIR}/{chat_id}_{timestamp}_%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'progress_hooks': [lambda d: download_progress_hook(d, chat_id, message_id)],
        'http_headers': {'User-Agent': 'Mozilla/5.0'}
    }

    # ------------------------------
    # FORMAT SETTINGS
    # ------------------------------
    if user_data["format"] == "mp3":
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192'
            }]
        })
    else:
        # VIDEO MODE
        if user_data["video_plus_audio"]:
            ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio/best'
        else:
            ydl_opts['format'] = 'best[ext=mp4]/best'

    try:
        # -------------------------
        # DOWNLOAD
        # -------------------------
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            filename = ydl.prepare_filename(info)
            if user_data["format"] == "mp3":
                filename = filename.rsplit(".", 1)[0] + ".mp3"

            if not os.path.exists(filename):
                raise Exception("Downloaded file not found.")

            file_path = filename

            # -------------------------
            # SEND FILES
            # -------------------------
            if user_data["format"] == "mp3":
                # SEND AUDIO DIRECTLY
                with open(file_path, 'rb') as f:
                    bot.send_audio(chat_id, f, caption="@dowlanderbot", title=info.get('title'))

            else:
                # SEND VIDEO
                with open(file_path, 'rb') as f:
                    bot.send_video(
                        chat_id,
                        f,
                        caption=f"{info.get('title')}\n@dowlanderbot",
                        supports_streaming=True
                    )

                # ------------------------------------------
                # VIDEO + AUDIO — SEND SECOND FILE (MP3)
                # ------------------------------------------
                if user_data["video_plus_audio"]:
                    try:
                        audio_path = file_path.rsplit(".", 1)[0] + ".mp3"

                        # Convert to MP3
                        cmd = f"ffmpeg -i \"{file_path}\" -vn -acodec mp3 -y \"{audio_path}\""
                        os.system(cmd)

                        if os.path.exists(audio_path):
                            with open(audio_path, "rb") as audio_file:
                                bot.send_audio(
                                    chat_id,
                                    audio_file,
                                    caption=f"{info.get('title')} — Audio\n@dowlanderbot",
                                    title=info.get('title')
                                )

                            os.remove(audio_path)

                    except Exception as e:
                        logging.error(f"Audio conversion error: {e}")

            # UPDATE USER STATS
            user_data['videos_downloaded'] += 1
            save_users(users)

    except Exception as e:
        logging.error(f"Download ERROR: {e}")
        bot.edit_message_text(f"❌ {t['download_failed']}", chat_id, message_id)

    finally:
        # DELETE TEMP VIDEO FILE
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass

        # DELETE "Loading..." message
        try:
            bot.delete_message(chat_id, message_id)
        except:
            pass


# ============================================================
#                   CALLBACK HANDLER
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

    chat_id = c.message.chat.id
    message_id = c.message.message_id

    if data == "cmd_back":
        bot.send_message(chat_id, t["enter_url"], reply_markup=main_menu(user))

    elif data == "cmd_settings":
        bot.edit_message_text(t["settings_title"], chat_id, message_id, reply_markup=settings_keyboard(user))

    elif data == "cmd_language":
        bot.edit_message_text(t["language"], chat_id, message_id, reply_markup=language_keyboard())

    elif data.startswith("lang_"):
        lang = data.replace("lang_", "")
        user["language"] = lang
        save_users(users)

        bot.delete_message(chat_id, message_id)
        bot.send_message(chat_id, texts[lang]["welcome"], reply_markup=main_menu(user))

    elif data.startswith("format_"):
        user["format"] = data.replace("format_", "")
        save_users(users)
        bot.edit_message_reply_markup(chat_id, message_id, reply_markup=settings_keyboard(user))

    elif data == "toggle_vpa":
        user["video_plus_audio"] = not user["video_plus_audio"]
        save_users(users)
        bot.edit_message_reply_markup(chat_id, message_id, reply_markup=settings_keyboard(user))

# ============================================================
#                   MESSAGE HANDLER
# ============================================================
@bot.message_handler(commands=["start"])
def start(m):
    u = get_user(m.from_user)
    bot.send_message(m.chat.id, texts[u["language"]]["welcome"], reply_markup=main_menu(u))

@bot.message_handler(func=lambda m: True)
def message_handler(m):
    u = get_user(m.from_user)
    t = texts[u["language"]]
    raw = m.text or ""

    if raw.startswith("http"):
        if ("youtube.com" in raw or "youtu.be" in raw) and t.get("yt_disabled"):
            bot.send_message(m.chat.id, t["yt_disabled"])
            return

        threading.Thread(
            target=run_download_task,
            args=(raw, m.chat.id, u, u["language"]),
            daemon=True
        ).start()
        return

    cmd = match_cmd(raw)
    if cmd == "menu":
        bot.send_message(m.chat.id, t["enter_url"], reply_markup=main_menu(u))
    elif cmd == "profile":
        msg = (
            f"👤 {t['profile_title']}\n\n"
            f"🆔 `{m.from_user.id}`\n"
            f"👋 {t['lbl_name']}: {u['name']}\n"
            f"💎 {t['lbl_subscription']}: {u['subscription']}\n"
            f"🎥 {t['lbl_downloaded']}: {u['videos_downloaded']}\n"
            f"🎞️ {t['lbl_format']}: {u['format']}\n"
            f"🎬 {t['lbl_video_plus_audio']}: {t['yes'] if u['video_plus_audio'] else t['no']}\n"
            f"📅 {t['lbl_since']}: {u['joined']}\n"
        )
        bot.send_message(m.chat.id, msg, parse_mode="Markdown", reply_markup=main_menu(u))
    elif cmd == "settings":
        bot.send_message(m.chat.id, t["settings_title"], reply_markup=settings_keyboard(u))
    elif cmd == "language":
        bot.send_message(m.chat.id, t["language"], reply_markup=language_keyboard())
    elif cmd == "subscription":
        bot.send_message(m.chat.id, t["free_version"], reply_markup=main_menu(u))
    elif cmd == "help":
        bot.send_message(m.chat.id, t["help_text"], reply_markup=main_menu(u))
    else:
        bot.send_message(m.chat.id, t["not_understood"], reply_markup=main_menu(u))

# ============================================================
#                   FLASK WEBHOOK
# ============================================================
@app.route("/", methods=["GET"])
def home():
    return "Bot is running!", 200

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        update = types.Update.de_json(request.get_data().decode("utf-8"))
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403

# ============================================================
#                   ЗАПУСК
# ============================================================
if __name__ == "__main__":
    logging.info("🚀 Запуск Webhook")
    try:
        bot.delete_webhook()
        time.sleep(0.5)
        bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
        logging.info(f"✅ Webhook встановлено: {WEBHOOK_URL}")
    except Exception as e:
        logging.error(f"❌ Помилка Webhook: {e}")

    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


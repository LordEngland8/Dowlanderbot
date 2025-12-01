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
    # Завантаження словника текстів з окремого файлу
    from languages import texts
except ImportError:
    raise ImportError("❌ Не вдалося імпортувати texts. Переконайтеся, що файл languages.py існує.")

# ============================================================
#                     КОНФІГУРАЦІЯ
# ============================================================

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("❌ TOKEN не встановлено! Встановіть змінну середовища.")

# Конфігурація для Webhook
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "https://dowlanderbot.onrender.com")
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = WEBHOOK_HOST + WEBHOOK_PATH

# Налаштування бота та Flask
bot = TeleBot(TOKEN)
app = Flask(__name__)

# Шляхи та логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
USER_FILE = "users.json"
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# 5 мов для клавіатур
LANGUAGE_OPTIONS = [
    ("uk", "🇺🇦 Українська"),
    ("en", "🇬🇧 English"),
    ("ru", "🇷🇺 Русский"),
    ("fr", "🇫🇷 Français"),
    ("de", "🇩🇪 Deutsch")
]

# ============================================================
#                   СИСТЕМА КОРИСТУВАЧІВ (users.json)
# ============================================================

file_lock = threading.Lock() # М'ютекс для захисту файлу users.json

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
#                   ДОПОМІЖНІ ФУНКЦІЇ / КОМАНДИ
# ============================================================

def clean_text(text):
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
    "subscription": ["підписка", "подписка", "subscription", "abonnement", "mitgliedschaft"],
    "help": ["про бота", "help", "about", "о боте", "à propos", "über bot"],
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
#                   КЛАВІАТУРИ (MENU / SETTINGS)
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
    
    # Вибір формату
    kb.row(
        types.InlineKeyboardButton(f"{'✅ ' if user['format']=='mp4' else ''}MP4", callback_data="format_mp4"),
        types.InlineKeyboardButton(f"{'✅ ' if user['format']=='mp3' else ''}MP3", callback_data="format_mp3"),
    )
    # Перемикач Відео + Аудіо
    state = f"✔ {t.get('yes', 'Yes')}" if user["video_plus_audio"] else f"✖ {t.get('no', 'No')}"
    kb.add(types.InlineKeyboardButton(
        f"{t.get('lbl_video_plus_audio', 'Video + Audio')}: {state}",
        callback_data="toggle_vpa"
    ))
    
    kb.add(types.InlineKeyboardButton("⬅ " + t.get("back", "Back"), callback_data="cmd_back"))
    return kb

def language_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    for code, name in LANGUAGE_OPTIONS:
        kb.add(types.InlineKeyboardButton(name, callback_data=f"lang_{code}"))
    return kb

# ============================================================
#            ЛОГІКА ЗАВАНТАЖЕННЯ (THREADED)
# ============================================================

def download_progress_hook(d, chat_id, message_id):
    # 🔥 ВИПРАВЛЕННЯ NameError: ініціалізуємо атрибут всередині функції
    if not hasattr(download_progress_hook, 'last_update'):
        download_progress_hook.last_update = 0

    if d['status'] == 'downloading':
        p = d['_percent_str'].strip()
        s = d['_speed_str'].strip()
        
        current_time = time.time()
        # Обмеження частоти оновлень (не частіше ніж раз на 2 секунди)
        if current_time - download_progress_hook.last_update > 2:
            try:
                # Оновлюємо статус повідомлення
                bot.edit_message_text(f"⏳ **Завантаження:** {p} \n➡️ {s}", 
                                      chat_id, message_id, parse_mode="Markdown")
                download_progress_hook.last_update = current_time
            except Exception:
                pass
    elif d['status'] == 'finished':
        pass

def run_download_task(url, chat_id, user_data, lang):
    """
    Виконується в окремому потоці для запобігання блокуванню.
    """
    t = texts[lang]
    file_path = None
    
    # 1. Надсилаємо "Завантаження..." і зберігаємо ID повідомлення
    try:
        status_msg = bot.send_message(chat_id, f"⏳ {t['loading']}...")
        message_id = status_msg.message_id
    except Exception as e:
        logging.error(f"Cannot send initial message: {e}")
        return

    # 2. Налаштування yt-dlp
    timestamp = int(time.time())
    
    ydl_opts = {
        'outtmpl': f'{DOWNLOAD_DIR}/{chat_id}_{timestamp}_%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'progress_hooks': [lambda d: download_progress_hook(d, chat_id, message_id)],
        'http_headers': {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
                ' AppleWebKit/537.36 (KHTML, like Gecko)'
                ' Chrome/91.0.4472.124 Safari/537.36'
            )
        },
    }

    # Формат MP3
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
        # Формат Відео
        if user_data["video_plus_audio"]:
            # Вибираємо найкраще відео + звук (FFmpeg required)
            ydl_opts.update({
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]'
            })
        else:
            # Вибираємо найкращий стрім, навіть якщо без звуку
            ydl_opts.update({
                'format': 'best[ext=mp4]/best'
            })

    try:
        # 3. Завантаження файлу
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            # Генерація фінального імені
            filename = ydl.prepare_filename(info)
            if user_data["format"] == "mp3":
                filename = os.path.splitext(filename)[0] + ".mp3"

            if os.path.exists(filename):
                file_path = filename
                file_size = os.path.getsize(file_path)

                # 4. Відправка відео або аудіо
                with open(file_path, 'rb') as f:

                    # ---- CASE 1: Користувач обрав MP3 ----
                    if user_data["format"] == "mp3":
                        bot.send_chat_action(chat_id, 'upload_voice')
                        bot.send_audio(
                            chat_id,
                            f,
                            caption="@dowlanderbot",
                            title=info.get('title', 'Audio')
                        )

                    # ---- CASE 2: Відео ----
                    else:
                        bot.send_chat_action(chat_id, 'upload_video')
                        bot.send_video(
                            chat_id,
                            f,
                            caption=f"{info.get('title', '')}\n\n@dowlanderbot",
                            supports_streaming=True
                        )

                        # ---- VIDEO + AUDIO MODE ----
                        if user_data["video_plus_audio"]:
                            try:
                                audio_path = file_path.rsplit(".", 1)[0] + ".mp3"

                                # Конвертація аудіо
                                cmd = (
                                    f"ffmpeg -i \"{file_path}\" -vn -acodec mp3 -y \"{audio_path}\""
                                )
                                os.system(cmd)

                                if os.path.exists(audio_path):
                                    with open(audio_path, "rb") as audio_file:
                                        bot.send_audio(
                                            chat_id,
                                            audio_file,
                                            caption=f"{info.get('title', '')} — Audio\n@dowlanderbot",
                                            title=info.get('title', 'Audio')
                                        )

                                    os.remove(audio_path)

                            except Exception as e:
                                logging.error(f"Помилка конвертації аудіо: {e}")

                # 5. Оновлюємо статистику
                user_data['videos_downloaded'] += 1
                save_users(users)

            else:
                raise Exception("File not found after download.")

    except DownloadError as e:
        logging.error(f"Download Error: {e}")
        bot.edit_message_text(f"❌ {t.get('download_failed')}", chat_id, message_id)

    except Exception as e:
        logging.error(f"General Error during download/upload: {e}")
        bot.edit_message_text(f"❌ {t.get('download_failed')}", chat_id, message_id)

    finally:
        # 6. Видалення файлу
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logging.error(f"Cleanup error: {e}")

        # 7. Видаляємо статус-повідомлення
        try:
            bot.delete_message(chat_id, message_id)
        except:
            pass


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

    chat_id = c.message.chat.id
    message_id = c.message.message_id

    # 1. Обробка повернення до меню
    if data == "cmd_back" or data == "cmd_menu":
        bot.send_message(chat_id, t.get("enter_url"), reply_markup=main_menu(user))
    
    # 2. Перехід до налаштувань
    elif data == "cmd_settings":
        bot.edit_message_text(f"⚙️ {t.get('settings_title')}:", chat_id, message_id, reply_markup=settings_keyboard(user))
    
    # 3. Виклик клавіатури мов
    elif data == "cmd_language":
        bot.edit_message_text(t["language"], chat_id, message_id, reply_markup=language_keyboard())

    # 4. ЗМІНА МОВИ (НАДІЙНИЙ БЛОК)
    elif data.startswith("lang_"):
        new_lang = data.replace("lang_", "")
        
        user["language"] = new_lang
        save_users(users)
        
        new_t = texts[new_lang]
        
        # Видаляємо старе повідомлення
        try:
            bot.delete_message(chat_id, message_id)
        except Exception as e:
            logging.warning(f"Failed to delete message after language change: {e}")

        # Надсилаємо нове привітання з головним меню новою мовою
        bot.send_message(
            chat_id,
            new_t["welcome"],
            reply_markup=main_menu(user)
        )
    
    # 5. Зміна формату (MP4/MP3)
    elif data.startswith("format_"):
        fmt = data.replace("format_", "")
        user["format"] = fmt
        save_users(users)
        bot.edit_message_reply_markup(chat_id, message_id, reply_markup=settings_keyboard(user))

    # 6. Перемикач Відео + Аудіо
    elif data == "toggle_vpa":
        user["video_plus_audio"] = not user["video_plus_audio"]
        save_users(users)
        bot.edit_message_reply_markup(chat_id, message_id, reply_markup=settings_keyboard(user))

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
    if raw.startswith("http"):
        # Бізнес-логіка: заборона YouTube, якщо це вказано в мовному файлі
        if ("youtube.com" in raw or "youtu.be" in raw) and t.get("yt_disabled"):
            bot.send_message(m.chat.id, t["yt_disabled"], reply_markup=main_menu(u))
            return
        
        # ЗАПУСК ЗАВАНТАЖЕННЯ В ОКРЕМОМУ ПОТОЦІ
        threading.Thread(
            target=run_download_task,
            args=(raw, m.chat.id, u, u["language"]),
            daemon=True
        ).start()
        return

    # 2. Перевірка команд
    cmd = match_cmd(txt)

    if cmd == "menu":
        bot.send_message(m.chat.id, t.get("enter_url"), reply_markup=main_menu(u))
        return

    if cmd == "profile":
        sub_name = t['subscription_names'].get(u['subscription'], u['subscription'])
        msg = (
            f"👤 {t.get('profile_title', 'Профіль')}\n\n"
            f"🆔 `{m.from_user.id}`\n"
            f"👋 {t.get('lbl_name', 'Ім\'я')}: {u['name']}\n"
            f"💎 {t.get('lbl_subscription', 'Підписка')}: {sub_name}\n"
            f"🎥 {t.get('lbl_downloaded', 'Завантажено')}: {u['videos_downloaded']}\n"
            f"🎞️ {t.get('lbl_format', 'Формат')}: {u['format'].upper()}\n"
            f"🎬 {t.get('lbl_video_plus_audio', 'Відео + Аудіо')}: "
            f"{t['yes'] if u['video_plus_audio'] else t['no']}\n"
            f"📅 {t.get('lbl_since', 'З')}: {u['joined']}\n"
        )
        bot.send_message(m.chat.id, msg, parse_mode="Markdown", reply_markup=main_menu(u))
        return

    if cmd == "settings":
        bot.send_message(m.chat.id, t.get('settings_title'), reply_markup=settings_keyboard(u))
        return

    if cmd == "language":
        bot.send_message(m.chat.id, t["language"], reply_markup=language_keyboard())
        return

    if cmd == "subscription":
        bot.send_message(m.chat.id, t.get("free_version_text", t["free_version"]), reply_markup=main_menu(u))
        return

    if cmd == "help":
        bot.send_message(m.chat.id, t.get("help_text", t.get("help")), reply_markup=main_menu(u))
        return

    # Якщо нічого не зрозуміло
    bot.send_message(m.chat.id, t.get("not_understood"), reply_markup=main_menu(u))

# ============================================================
#                     FLASK WEBHOOK
# ============================================================

@app.route("/", methods=["GET"])
def home():
    # Health check для хостингу
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
    logging.info("🚀 Запуск конфігурації Webhook")
    try:
        # Налаштування Webhook при старті програми
        bot.delete_webhook()
        time.sleep(0.5)
        bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
        logging.info(f"✅ Webhook встановлено: {WEBHOOK_URL}")
    except Exception as e:
        logging.error(f"❌ Помилка налаштування Webhook: {e}")

    # 🔥 ВАЖЛИВО: Використання dev-сервера Flask для запуску.
    # Це є ПРИЧИНОЮ попередження, яке ви бачили раніше,
    # але дозволить запустити застосунок без Gunicorn.
    
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


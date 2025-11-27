import os
import json
import glob
import subprocess
import re
from datetime import datetime

from telebot import TeleBot, types
from flask import Flask, request

# ============================================================
#                     ПІДКЛЮЧЕННЯ МОВ
# ============================================================

from languages import texts   # 🇺🇦 🇬🇧 🇷🇺 🇫🇷 🇩🇪


# ============================================================
#                     КОНФІГУРАЦІЯ
# ============================================================

TOKEN = os.getenv("TOKEN") or os.getenv("TELEGRAM_TOKEN", "")
if not TOKEN or ":" not in TOKEN:
    raise ValueError("❌ TOKEN не встановлено!")

WEBHOOK_HOST = "https://dowlanderbot.onrender.com"
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = WEBHOOK_HOST + WEBHOOK_PATH

bot = TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

USER_FILE = "users.json"
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# ============================================================
#                  СИСТЕМА КОРИСТУВАЧІВ
# ============================================================

def load_users():
    return json.load(open(USER_FILE, "r", encoding="utf-8")) if os.path.exists(USER_FILE) else {}


def save_users(data):
    json.dump(
        data, open(USER_FILE, "w", encoding="utf-8"),
        indent=4, ensure_ascii=False
    )


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
            "audio_only": False,
            "video_plus_audio": True
        }
        save_users(users)

    if users[uid]["language"] not in texts:
        users[uid]["language"] = "uk"
        save_users(users)

    return users[uid]


# ============================================================
#                 ОЧИЩЕННЯ ТЕКСТУ
# ============================================================

def clean_text(text):
    return re.sub(
        r"[^a-zA-Zа-яА-ЯёЁіІїЇєЄçÇčČšŠğĞüÜöÖâÂêÊôÔùÙàÀéÉ0-9 ]",
        "",
        text or ""
    ).strip().lower()


# ============================================================
#            АЛІАСИ КОМАНД (усі мови)
# ============================================================

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
#                 ГОЛОВНЕ МЕНЮ
# ============================================================

def main_menu(user):
    t = texts[user["language"]]

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.row(types.KeyboardButton(f"📋 {t['menu']}"),
           types.KeyboardButton(f"👤 {t['profile']}"))

    kb.row(types.KeyboardButton(f"⚙️ {t['settings']}"),
           types.KeyboardButton(f"💎 {t['subscription']}"))

    kb.row(types.KeyboardButton(f"🌍 {t['language']}"),
           types.KeyboardButton(f"ℹ️ {t['help']}"))

    return kb


# ============================================================
#                 INLINE НАЛАШТУВАННЯ
# ============================================================

def settings_keyboard(user):
    t = texts[user["language"]]

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(
        types.InlineKeyboardButton("MP4", callback_data="format_mp4"),
        types.InlineKeyboardButton("MP3", callback_data="format_mp3"),
    )
    kb.add(types.InlineKeyboardButton("WEBM", callback_data="format_webm"))

    state = f"✔ {t['yes']}" if user["video_plus_audio"] else f"✖ {t['no']}"
    kb.add(types.InlineKeyboardButton(
        f"{t['lbl_video_plus_audio']}: {state}",
        callback_data="toggle_vpa"
    ))

    kb.add(types.InlineKeyboardButton("⬅ " + t["back"], callback_data="cmd_back"))
    return kb


# ============================================================
#                   CALLBACK HANDLER
# ============================================================

@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    user = get_user(c.from_user)
    t = texts[user["language"]]
    data = c.data

    bot.answer_callback_query(c.id)

    # ====== menu ======
    if data == "cmd_back" or data == "cmd_menu":
        bot.send_message(c.message.chat.id, t["enter_url"], reply_markup=main_menu(user))
        return

    # ====== profile ======
    if data == "cmd_profile":
        msg = (
            f"👤 {t['profile']}\n\n"
            f"🆔 `{c.from_user.id}`\n"
            f"👋 {t['lbl_name']}: {user['name']}\n"
            f"🎥 {t['lbl_downloaded']}: {user['videos_downloaded']}\n"
            f"🎞️ {t['lbl_format']}: {user['format'].upper()}\n"
            f"🎬 {t['lbl_video_plus_audio']}: "
            f"{t['yes'] if user['video_plus_audio'] else t['no']}\n"
            f"📅 {t['lbl_since']}: {user['joined']}\n"
        )
        bot.send_message(c.message.chat.id, msg, parse_mode="Markdown", reply_markup=main_menu(user))
        return

    # ====== settings ======
    if data == "cmd_settings":
        bot.send_message(c.message.chat.id, f"⚙️ {t['settings']}:", reply_markup=settings_keyboard(user))
        return

    # ====== language ======
    if data == "cmd_language":
        kb = types.InlineKeyboardMarkup()
        for code, name in [
            ("uk", "🇺🇦 Українська"),
            ("en", "🇬🇧 English"),
            ("ru", "🇷🇺 Русский"),
            ("fr", "🇫🇷 Français"),
            ("de", "🇩🇪 Deutsch")
        ]:
            kb.add(types.InlineKeyboardButton(name, callback_data=f"lang_{code}"))

        bot.send_message(c.message.chat.id, t["language"], reply_markup=kb)
        return

    if data.startswith("lang_"):
        new_lang = data.replace("lang_", "")
        user["language"] = new_lang
        save_users(users)
        bot.send_message(
            c.message.chat.id,
            texts[new_lang]["welcome"],
            reply_markup=main_menu(user)
        )
        return

    # ====== change format ======
    if data.startswith("format_"):
        fmt = data.replace("format_", "")
        user["format"] = fmt
        user["audio_only"] = fmt == "mp3"
        save_users(users)
        bot.edit_message_reply_markup(
            c.message.chat.id, c.message.message_id,
            reply_markup=settings_keyboard(user)
        )
        return

    # ====== toggle video+audio ======
    if data == "toggle_vpa":
        user["video_plus_audio"] = not user["video_plus_audio"]
        save_users(users)
        bot.edit_message_reply_markup(
            c.message.chat.id, c.message.message_id,
            reply_markup=settings_keyboard(user)
        )
        return


# ============================================================
#                 ОПЕРАЦІЇ З ФАЙЛАМИ
# ============================================================

def extract_audio(video_path):
    audio_path = video_path.rsplit(".", 1)[0] + ".mp3"
    cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "mp3", "-y", audio_path]

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        return audio_path
    except:
        return None


def cleanup(files):
    for f in files:
        try:
            os.remove(f)
        except:
            pass


# ============================================================
#                    ГОЛОВНА ФУНКЦІЯ ЗАВАНТАЖЕННЯ
# ============================================================

def download_from_url(url, chat_id, user, lang):
    t = texts[lang]

    if "youtube.com" in url or "youtu.be" in url:
        bot.send_message(chat_id, t["yt_disabled"])
        return False

    if "tiktok.com" in url:
        return download_tiktok(url, chat_id, user, lang)

    if "instagram.com" in url:
        return download_instagram(url, chat_id, user, lang)

    return download_generic(url, chat_id, user, lang)


# ============================================================
#                           TIKTOK
# ============================================================

def download_tiktok(url, chat_id, user, lang):
    t = texts[lang]
    fmt = user["format"]
    template = f"{DOWNLOAD_DIR}/{chat_id}_tt.%(ext)s"

    base = [
        "yt-dlp", "--force-ipv4", "--no-check-certificates",
        "--referer", "https://www.tiktok.com/",
        "-o", template, url
    ]

    cmd = base + (["-x", "--audio-format", "mp3"] if fmt == "mp3"
                  else ["-f", "bv*+ba/best"])

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except:
        bot.send_message(chat_id, t["tiktok_error"])
        return False

    files = glob.glob(f"{DOWNLOAD_DIR}/{chat_id}_tt.*")
    return process_downloaded_media(files, chat_id, user, lang)


# ============================================================
#                         INSTAGRAM
# ============================================================

def download_instagram(url, chat_id, user, lang):
    t = texts[lang]
    fmt = user["format"]
    template = f"{DOWNLOAD_DIR}/{chat_id}_ig.%(ext)s"

    base = [
        "yt-dlp", "--force-ipv4", "--no-check-certificates",
        "-o", template, url
    ]

    cmd = base + (
        ["-x", "--audio-format", "mp3"]
        if fmt == "mp3"
        else ["-f", "bestvideo*+bestaudio", "--merge-output-format", "mp4"]
    )

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except:
        bot.send_message(chat_id, t["ig_error"])
        return False

    files = glob.glob(f"{DOWNLOAD_DIR}/{chat_id}_ig.*")
    return process_downloaded_media(files, chat_id, user, lang)


# ============================================================
#                           GENERIC
# ============================================================

def download_generic(url, chat_id, user, lang):
    t = texts[lang]
    fmt = user["format"]
    ts = str(datetime.now().timestamp()).replace(".", "")

    template = f"{DOWNLOAD_DIR}/{chat_id}_{ts}.%(ext)s"

    cmd = ["yt-dlp", "-o", template, url]

    if fmt == "mp3":
        cmd += ["-x", "--audio-format", "mp3"]
    elif fmt == "webm":
        cmd += ["-f", "bestvideo*+bestaudio", "--merge-output-format", "webm"]
    else:
        cmd += ["-f", "bestvideo*+bestaudio", "--merge-output-format", "mp4"]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except:
        bot.send_message(chat_id, t["download_failed"])
        return False

    files = glob.glob(f"{DOWNLOAD_DIR}/{chat_id}_{ts}.*")
    return process_downloaded_media(files, chat_id, user, lang)


# ============================================================
#              РОЗПІЗНАВАННЯ ВИДУ МЕДІА
# ============================================================

def process_downloaded_media(files, chat_id, user, lang):
    t = texts[lang]

    audio_ext = (".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav")
    video_ext = (".mp4", ".webm", ".mov", ".mkv")
    image_ext = (".jpg", ".jpeg", ".png", ".webp")

    fmt = user["format"]

    # 🔥 MP3 режим
    if fmt == "mp3":
        audio = next((p for p in files if p.endswith(audio_ext)), None)
        if audio:
            bot.send_audio(chat_id, open(audio, "rb"))
            cleanup(files)
            return True

        bot.send_message(chat_id, t["download_failed"])
        cleanup(files)
        return False

    # 🔥 Відео
    video = next((p for p in files if p.endswith(video_ext)), None)
    if video:
        bot.send_video(chat_id, open(video, "rb"))

        if user["video_plus_audio"]:
            audio = extract_audio(video)
            if audio:
                bot.send_audio(chat_id, open(audio, "rb"))

        cleanup(files)
        return True

    # 🔥 Фото
    images = [p for p in files if p.endswith(image_ext)]
    if images:
        if len(images) == 1:
            bot.send_photo(chat_id, open(images[0], "rb"), caption=t["tiktok_photo_caption"])
        else:
            media = []
            for i, img in enumerate(images):
                if i == 0:
                    media.append(types.InputMediaPhoto(open(img, "rb"), caption=t["tiktok_photo_caption"]))
                else:
                    media.append(types.InputMediaPhoto(open(img, "rb")))
            bot.send_media_group(chat_id, media)

        cleanup(files)
        return True

    # 🔥 Все погано
    bot.send_message(chat_id, t["download_failed"])
    cleanup(files)
    return False


# ============================================================
#                      ХЕНДЛЕРИ
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

    # 🔥 якщо це URL
    if raw.startswith("http"):
        bot.send_message(m.chat.id, t["loading"])
        ok = download_from_url(raw, m.chat.id, u, u["language"])

        if ok:
            u["videos_downloaded"] += 1
            save_users(users)
        return

    # 🔥 розпізнавання команд (меню, профіль, налаштування...)
    cmd = match_cmd(txt)

    if cmd == "menu":
        bot.send_message(m.chat.id, t["enter_url"], reply_markup=main_menu(u))
        return

    if cmd == "profile":
        msg = (
            f"👤 {t['profile']}\n\n"
            f"🆔 `{m.from_user.id}`\n"
            f"👋 {t['lbl_name']}: {u['name']}\n"
            f"🎥 {t['lbl_downloaded']}: {u['videos_downloaded']}\n"
            f"🎞️ {t['lbl_format']}: {u['format'].upper()}\n"
            f"🎬 {t['lbl_video_plus_audio']}: "
            f"{t['yes'] if u['video_plus_audio'] else t['no']}\n"
            f"📅 {t['lbl_since']}: {u['joined']}\n"
        )
        bot.send_message(m.chat.id, msg, parse_mode="Markdown", reply_markup=main_menu(u))
        return

    if cmd == "settings":
        bot.send_message(m.chat.id, f"⚙️ {t['settings']}:", reply_markup=settings_keyboard(u))
        return

    if cmd == "language":
        kb = types.InlineKeyboardMarkup()
        for code, name in [
            ("uk", "🇺🇦 Українська"),
            ("en", "🇬🇧 English"),
            ("ru", "🇷🇺 Русский"),
            ("fr", "🇫🇷 Français"),
            ("de", "🇩🇪 Deutsch")
        ]:
            kb.add(types.InlineKeyboardButton(name, callback_data=f"lang_{code}"))
        bot.send_message(m.chat.id, t["language"], reply_markup=kb)
        return

    if cmd == "subscription":
        bot.send_message(m.chat.id, t["free_version"], reply_markup=main_menu(u))
        return

    if cmd == "help":
        bot.send_message(m.chat.id, t["help_text"], reply_markup=main_menu(u))
        return

    bot.send_message(m.chat.id, t["not_understood"], reply_markup=main_menu(u))


# ============================================================
#               РЕЄСТРАЦІЯ КОМАНД В ТГ
# ============================================================

def setup_bot_commands():
    for lang_code in texts.keys():
        t = texts[lang_code]

        bot.set_my_commands([
            types.BotCommand("menu", t["menu"]),
            types.BotCommand("profile", t["profile"]),
            types.BotCommand("settings", t["settings"]),
            types.BotCommand("language", t["language"]),
            types.BotCommand("subscription", t["subscription"]),
            types.BotCommand("help", t["help"])
        ], language_code=lang_code)


# ============================================================
#                        WEBHOOK
# ============================================================

@app.route("/", methods=["GET"])
def home():
    return "Bot is running!"


@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    update = types.Update.de_json(request.get_data().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200


# ============================================================
#                       ЗАПУСК
# ============================================================

if __name__ == "__main__":
    print("🚀 Запуск Flask + Webhook")

    setup_bot_commands()

    bot.delete_webhook()
    bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=True
    )

    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 10000)),
        debug=False
    )

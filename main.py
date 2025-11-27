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

from languages import texts   # словник texts = { "uk": {...}, ... }


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
    json.dump(data, open(USER_FILE, "w", encoding="utf-8"), indent=4, ensure_ascii=False)


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
    "settings": ["налаштування", "налаш", "настройки", "settings", "einstellungen", "paramètres", "parametre"],
    "language": ["мова", "язык", "language", "langue", "sprache"],
    "subscription": ["підпис", "подпис", "subscription", "abonnement", "mitgliedschaft"],
    "help": ["про бота", "help", "about", "à propos", "über bot"],
    "back": ["назад", "back", "retour", "zurück", "⬅️"],
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
    lang = user["language"]
    t = texts[lang]

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

    kb.row(types.KeyboardButton(f"📋 {t['menu']}"),
           types.KeyboardButton(f"👤 {t['profile']}"))

    kb.row(types.KeyboardButton(f"⚙️ {t['settings']}"),
           types.KeyboardButton(f"💎 {t['subscription']}"))

    kb.row(types.KeyboardButton(f"🌍 {t['language']}"),
           types.KeyboardButton(f"ℹ️ {t['help']}"))

    return kb


# ============================================================
#                 INLINE-НАЛАШТУВАННЯ
# ============================================================

def settings_keyboard(user):
    lang = user["language"]
    t = texts[lang]

    kb = types.InlineKeyboardMarkup(row_width=2)

    kb.row(
        types.InlineKeyboardButton("MP4", callback_data="format_mp4"),
        types.InlineKeyboardButton("MP3", callback_data="format_mp3"),
    )
    kb.add(types.InlineKeyboardButton("WEBM", callback_data="format_webm"))

    vpa_state = f"✔ {t['yes']}" if user["video_plus_audio"] else f"✖ {t['no']}"
    kb.add(types.InlineKeyboardButton(f"{t['lbl_video_plus_audio']}: {vpa_state}", callback_data="toggle_vpa"))

    kb.add(types.InlineKeyboardButton("⬅ " + t["back"], callback_data="cmd_back"))

    return kb


# ============================================================
#                      CALLBACK
# ============================================================

@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    user = get_user(c.from_user)
    lang = user["language"]
    t = texts[lang]

    bot.answer_callback_query(c.id)
    data = c.data

    if data == "cmd_menu":
        bot.send_message(c.message.chat.id, t["enter_url"], reply_markup=main_menu(user))
        return

    if data == "cmd_profile":
        msg_text = (
            f"👤 {t['profile']}\n\n"
            f"🆔 `{c.from_user.id}`\n"
            f"👋 {t['lbl_name']}: {user['name']}\n"
            f"🎥 {t['lbl_downloaded']}: {user['videos_downloaded']}\n"
            f"🎞️ {t['lbl_format']}: {user['format'].upper()}\n"
            f"🎬 {t['lbl_video_plus_audio']}: {t['yes'] if user['video_plus_audio'] else t['no']}\n"
            f"📅 {t['lbl_since']}: {user['joined']}\n"
        )
        bot.send_message(c.message.chat.id, msg_text, parse_mode="Markdown", reply_markup=main_menu(user))
        return

    if data == "cmd_settings":
        bot.send_message(c.message.chat.id, f"⚙️ {t['settings']}:", reply_markup=settings_keyboard(user))
        return

    if data == "cmd_language":
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk"))
        kb.add(types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"))
        kb.add(types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"))
        kb.add(types.InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr"))
        kb.add(types.InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de"))
        bot.send_message(c.message.chat.id, t["language"], reply_markup=kb)
        return

    if data.startswith("lang_"):
        new_lang = data.replace("lang_", "")
        if new_lang in texts:
            user["language"] = new_lang
            save_users(users)
            bot.send_message(c.message.chat.id, texts[new_lang]["welcome"], reply_markup=main_menu(user))
        return

    if data.startswith("format_"):
        fmt = data.replace("format_", "")
        user["format"] = fmt
        user["audio_only"] = (fmt == "mp3")
        save_users(users)
        bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=settings_keyboard(user))
        return

    if data == "toggle_vpa":
        user["video_plus_audio"] = not user["video_plus_audio"]
        save_users(users)
        bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=settings_keyboard(user))
        return


# ============================================================
#      ФУНКЦІЇ ОБРОБКИ АУДІО/ФАЙЛІВ
# ============================================================

def extract_audio(video_path):
    audio_path = video_path.rsplit('.', 1)[0] + ".mp3"

    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vn",
        "-acodec", "mp3",
        "-y",
        audio_path
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return audio_path
    except:
        return None


def _cleanup_files(files):
    for p in files:
        try:
            os.remove(p)
        except:
            pass


# ============================================================
#        ЗАВАНТАЖЕННЯ TIKTOK / INSTAGRAM / GENERIC
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
#                        TIKTOK
# ============================================================

def download_tiktok(url, chat_id, user, lang):
    t = texts[lang]
    fmt = user["format"]
    template = os.path.join(DOWNLOAD_DIR, f"{chat_id}_tt.%(ext)s")

    base_cmd = [
        "yt-dlp",
        "--force-ipv4",
        "--no-check-certificates",
        "--referer", "https://www.tiktok.com/",
        "-o", template,
        url,
    ]

    if fmt == "mp3":
        cmd = base_cmd + ["-x", "--audio-format", "mp3", "--audio-quality", "0"]
    else:
        cmd = base_cmd + ["-f", "bv*+ba/best"]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except:
        bot.send_message(chat_id, t["tiktok_error"])
        return False

    files = glob.glob(os.path.join(DOWNLOAD_DIR, f"{chat_id}_tt.*"))

    audio_exts = (".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav")
    video_exts = (".mp4", ".webm", ".mov", ".mkv")
    image_exts = (".jpg", ".jpeg", ".png", ".webp")

    # MP3 mode
    if fmt == "mp3":
        audio_path = next((p for p in files if os.path.splitext(p)[1].lower() in audio_exts), None)
        if audio_path:
            bot.send_audio(chat_id, open(audio_path, "rb"))
            _cleanup_files(files)
            return True
        bot.send_message(chat_id, t["download_failed"])
        return False

    # VIDEO mode
    video_path = next((p for p in files if os.path.splitext(p)[1].lower() in video_exts), None)

    if video_path:
        bot.send_video(chat_id, open(video_path, "rb"))

        if user["video_plus_audio"]:
            audio_path = extract_audio(video_path)
            if audio_path:
                bot.send_audio(chat_id, open(audio_path, "rb"))

        _cleanup_files(files)
        return True

    # PHOTO mode
    img_paths = [p for p in files if os.path.splitext(p)[1].lower() in image_exts]
    if img_paths:
        if len(img_paths) == 1:
            bot.send_photo(chat_id, open(img_paths[0], "rb"))
        else:
            media = [types.InputMediaPhoto(open(p, "rb")) for p in img_paths]
            bot.send_media_group(chat_id, media)
        _cleanup_files(files)
        return True

    bot.send_message(chat_id, t["download_failed"])
    return False


# ============================================================
#                        INSTAGRAM
# ============================================================

def download_instagram(url, chat_id, user, lang):
    t = texts[lang]
    fmt = user["format"]
    template = os.path.join(DOWNLOAD_DIR, f"{chat_id}_ig.%(ext)s")

    base_cmd = [
        "yt-dlp",
        "--force-ipv4",
        "--no-check-certificates",
        "-o", template,
        url,
    ]

    if fmt == "mp3":
        cmd = base_cmd + ["-x", "--audio-format", "mp3", "--audio-quality", "0"]
    else:
        cmd = base_cmd + ["-f", "bestvideo*+bestaudio/best", "--merge-output-format", "mp4"]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except:
        bot.send_message(chat_id, t["ig_error"])
        return False

    files = glob.glob(os.path.join(DOWNLOAD_DIR, f"{chat_id}_ig.*"))

    audio_exts = (".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav")
    video_exts = (".mp4", ".webm", ".mov", ".mkv")
    image_exts = (".jpg", ".jpeg", ".png", ".webp")

    # MP3 mode
    if fmt == "mp3":
        audio_path = next((p for p in files if os.path.splitext(p)[1].lower() in audio_exts), None)
        if audio_path:
            bot.send_audio(chat_id, open(audio_path, "rb"))
            _cleanup_files(files)
            return True

        bot.send_message(chat_id, t["download_failed"])
        return False

    # VIDEO mode
    video_path = next((p for p in files if os.path.splitext(p)[1].lower() in video_exts), None)

    if video_path:
        bot.send_video(chat_id, open(video_path, "rb"))

        if user["video_plus_audio"]:
            audio_path = extract_audio(video_path)
            if audio_path:
                bot.send_audio(chat_id, open(audio_path, "rb"))

        _cleanup_files(files)
        return True

    # PHOTO mode
    img_paths = [p for p in files if os.path.splitext(p)[1].lower() in image_exts]

    if img_paths:
        if len(img_paths) == 1:
            bot.send_photo(chat_id, open(img_paths[0], "rb"))
        else:
            media = [types.InputMediaPhoto(open(p, "rb")) for p in img_paths]
            bot.send_media_group(chat_id, media)

        _cleanup_files(files)
        return True

    bot.send_message(chat_id, t["download_failed"])
    return False


# ============================================================
#                        GENERIC
# ============================================================

def download_generic(url, chat_id, user, lang):
    t = texts[lang]
    fmt = user["format"]

    ts = str(datetime.now().timestamp()).replace(".", "")
    base_name = f"{chat_id}_gen_{ts}"
    template = os.path.join(DOWNLOAD_DIR, base_name + ".%(ext)s")

    cmd = [
        "yt-dlp",
        "--force-ipv4",
        "--no-check-certificates",
        "-o", template,
        url,
    ]

    if fmt == "mp3":
        cmd += ["-x", "--audio-format", "mp3", "--audio-quality", "0"]
    elif fmt == "webm":
        cmd += ["-f", "bestvideo*+bestaudio/best", "--merge-output-format", "webm"]
    else:
        cmd += ["-f", "bestvideo*+bestaudio/best", "--merge-output-format", "mp4"]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except:
        bot.send_message(chat_id, t["download_failed"])
        return False

    files = glob.glob(os.path.join(DOWNLOAD_DIR, base_name + ".*"))

    audio_exts = (".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav")
    video_exts = (".mp4", ".webm", ".mov", ".mkv")

    # MP3 mode
    if fmt == "mp3":
        audio_path = next((p for p in files if os.path.splitext(p)[1].lower() in audio_exts), None)
        if audio_path:
            bot.send_audio(chat_id, open(audio_path, "rb"))
            _cleanup_files(files)
            return True

        bot.send_message(chat_id, t["download_failed"])
        return False

    # VIDEO mode
    video_path = next((p for p in files if os.path.splitext(p)[1].lower() in video_exts), None)

    if video_path:
        bot.send_video(chat_id, open(video_path, "rb"))

        if user["video_plus_audio"]:
            audio_path = extract_audio(video_path)
            if audio_path:
                bot.send_audio(chat_id, open(audio_path, "rb"))

        _cleanup_files(files)
        return True

    bot.send_message(chat_id, t["download_failed"])
    return False


# ============================================================
#                     ХЕНДЛЕРИ
# ============================================================

@bot.message_handler(commands=["start"])
def start(m):
    u = get_user(m.from_user)
    lang = u["language"]

    bot.send_message(m.chat.id, texts[lang]["welcome"], reply_markup=main_menu(u))


@bot.message_handler(func=lambda m: True)
def msg(m):
    u = get_user(m.from_user)
    lang = u["language"]
    t = texts[lang]

    raw_text = m.text or ""
    txt = clean_text(raw_text)

    if raw_text.strip().lower().startswith("http"):
        bot.send_message(m.chat.id, t["loading"])
        ok = download_from_url(raw_text.strip(), m.chat.id, u, lang)

        if ok:
            u["videos_downloaded"] += 1
            save_users(users)
        return

    cmd = match_cmd(txt)

    if cmd == "menu":
        bot.send_message(m.chat.id, t["enter_url"], reply_markup=main_menu(u))
        return

    if cmd == "profile":
        bot.send_message(
            m.chat.id,
            (
                f"👤 {t['profile']}\n\n"
                f"🆔 `{m.from_user.id}`\n"
                f"👋 {t['lbl_name']}: {u['name']}\n"
                f"🎥 {t['lbl_downloaded']}: {u['videos_downloaded']}\n"
                f"🎞️ {t['lbl_format']}: {u['format'].upper()}\n"
                f"🎬 {t['lbl_video_plus_audio']}: {t['yes'] if u['video_plus_audio'] else t['no']}\n"
                f"📅 {t['lbl_since']}: {u['joined']}\n"
            ),
            parse_mode="Markdown",
            reply_markup=main_menu(u),
        )
        return

    if cmd == "language":
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk"))
        kb.add(types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"))
        kb.add(types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"))
        kb.add(types.InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr"))
        kb.add(types.InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de"))
        bot.send_message(m.chat.id, t["language"], reply_markup=kb)
        return

    if cmd == "settings":
        bot.send_message(m.chat.id, f"⚙️ {t['settings']}:", reply_markup=settings_keyboard(u))
        return

    if cmd == "subscription":
        bot.send_message(m.chat.id, t["free_version"], reply_markup=main_menu(u))
        return

    if cmd == "help":
        bot.send_message(m.chat.id, t["help_text"], reply_markup=main_menu(u))
        return

    bot.send_message(m.chat.id, t["not_understood"], reply_markup=main_menu(u))


# ============================================================
#                  КОМАНДИ МЕНЮ
# ============================================================

def setup_bot_commands():
    for lang in texts.keys():
        bot.set_my_commands([
            types.BotCommand("menu", f"📋 {texts[lang]['menu']}"),
            types.BotCommand("profile", f"👤 {texts[lang]['profile']}"),
            types.BotCommand("settings", f"⚙ {texts[lang]['settings']}"),
            types.BotCommand("language", f"🌍 {texts[lang]['language']}"),
            types.BotCommand("subscription", f"💎 {texts[lang]['subscription']}"),
            types.BotCommand("help", f"ℹ {texts[lang]['help']}"),
        ], language_code=lang)


# ============================================================
#                     WEBHOOK
# ============================================================

@app.route("/", methods=["GET"])
def home():
    return "Bot is running!"


@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook_receiver():
    json_str = request.get_data().decode("utf-8")
    update = types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200


# ============================================================
#                    RUN SERVER
# ============================================================

if __name__ == "__main__":
    print("🚀 Запуск Flask + Webhook")

    setup_bot_commands()

    bot.delete_webhook()
    bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)

    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 10000)),
        debug=False
    )

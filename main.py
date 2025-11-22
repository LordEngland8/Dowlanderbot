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

from languages import texts   # файл languages.py


# ============================================================
#                     КОНФІГУРАЦІЯ
# ============================================================

TOKEN = os.getenv("TOKEN") or os.getenv("TELEGRAM_TOKEN", "")
if not TOKEN or ":" not in TOKEN:
    raise ValueError("❌ TOKEN не встановлено!")

WEBHOOK_HOST = "https://dowlanderbot-2.onrender.com"
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
            "joined": datetime.now().strftime("%Y-%m-%d %H:%М"),
            "language": "uk",
            "format": "mp4",          # mp4 / mp3 / webm
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
    # прибираємо емодзі та зайві символи, залишаємо букви/цифри/пробіли
    return re.sub(r"[^a-zA-Zа-яА-ЯёЁіІїЇєЄçÇčČšŠğĞüÜöÖâÂêÊôÔùÙàÀéÉ0-9 ]", "", text).strip().lower()


# ============================================================
#            АЛІАСИ КОМАНД
# ============================================================

CMD = {
    "menu": ["меню", "menu", "menü"],
    "profile": ["профіль", "проф", "profile", "profil"],
    "settings": [
        "налаштування", "налаш", "настройки",  # 🇺🇦🇷🇺
        "settings",                           # 🇬🇧
        "einstellungen",                      # 🇩🇪
        "paramètres", "parametre"             # 🇫🇷
    ],
    "language": ["мова", "язык", "language", "langue", "sprache"],
    "subscription": ["підпис", "подпис", "subscription", "abonnement", "mitgliedschaft"],
    "help": ["про бота", "help", "about", "à propos", "über bot"],
    "back": ["назад", "back", "retour", "zurück", "⬅️"],
}



def match_cmd(text):
    text = clean_text(text)
    for cmd, variants in CMD.items():
        for v in variants:
            if clean_text(v) in text:   # 🔥 працює як раніше
                return cmd
    return None



# ============================================================
#                 КЛАВІАТУРИ
# ============================================================

def main_menu(lang):
    t = texts[lang]
    kb = types.InlineKeyboardMarkup(row_width=2)

    kb.row(
        types.InlineKeyboardButton(f"📋 {t['menu']}", callback_data="cmd_menu"),
        types.InlineKeyboardButton(f"👤 {t['profile']}", callback_data="cmd_profile")
    )

    kb.row(
        types.InlineKeyboardButton(f"⚙️ {t['settings']}", callback_data="cmd_settings"),
        types.InlineKeyboardButton(f"🌍 {t['language']}", callback_data="cmd_language")
    )

    kb.row(
        types.InlineKeyboardButton(f"💎 {t['subscription']}", callback_data="cmd_sub"),
        types.InlineKeyboardButton(f"ℹ️ {t['help']}", callback_data="cmd_help")
    )

    return kb




def back_menu(lang):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(f"⬅️ {texts[lang]['back']}")
    return kb


def settings_keyboard(user):
    lang = user["language"]
    t = texts[lang]

    kb = types.InlineKeyboardMarkup(row_width=2)

    kb.row(
        types.InlineKeyboardButton("MP4", callback_data="format_mp4"),
        types.InlineKeyboardButton("MP3", callback_data="format_mp3"),
    )
    kb.add(types.InlineKeyboardButton("WEBM", callback_data="format_webm"))

    vpa_state = f"✅ {t['yes']}" if user["video_plus_audio"] else f"❌ {t['no']}"
    kb.add(types.InlineKeyboardButton(f"{t['lbl_video_plus_audio']}: {vpa_state}", callback_data="toggle_vpa"))

    return kb


# ============================================================
#                      CALLBACK
# ============================================================

@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    user = get_user(c.from_user)
    lang = user["language"]
    t = texts[lang]

    # ======= 📌 КОМАНДИ МЕНЮ =======
    if c.data.startswith("cmd_"):
        bot.answer_callback_query(c.id)

        if c.data == "cmd_menu":
            bot.send_message(c.message.chat.id, t["enter_url"], reply_markup=main_menu(lang))

        elif c.data == "cmd_profile":
            msg_text = (
                f"👤 {t['profile']}\n\n"
                f"🆔 `{c.from_user.id}`\n"
                f"👋 {t['lbl_name']}: {user['name']}\n"
                f"🎥 {t['lbl_downloaded']}: {user['videos_downloaded']}\n"
                f"🎞️ {t['lbl_format']}: {user['format'].upper()}\n"
                f"🎬 {t['lbl_video_plus_audio']}: {t['yes'] if user['video_plus_audio'] else t['no']}\n"
                f"📅 {t['lbl_since']}: {user['joined']}\n"
            )
            bot.send_message(c.message.chat.id, msg_text, parse_mode="Markdown", reply_markup=main_menu(lang))

        elif c.data == "cmd_settings":
            bot.send_message(c.message.chat.id, f"⚙️ {t['settings']}:", reply_markup=settings_keyboard(user))

        elif c.data == "cmd_language":
            lang_menu = types.InlineKeyboardMarkup()
            lang_menu.add(types.InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk"))
            lang_menu.add(types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"))
            lang_menu.add(types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"))
            lang_menu.add(types.InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr"))
            lang_menu.add(types.InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de"))

            bot.send_message(c.message.chat.id, t["language"], reply_markup=lang_menu)

        elif c.data == "cmd_sub":
            bot.send_message(c.message.chat.id, t["free_version"])

        elif c.data == "cmd_help":
            bot.send_message(c.message.chat.id, t["help_text"])

        return  # <<< ВАЖЛИВО



# ============================================================
#        ЗАВАНТАЖЕННЯ: TIKTOK / INSTAGRAM / ГЕНЕРИК
# ============================================================

def download_from_url(url, chat_id, user, lang):
    t = texts[lang]

    # YouTube – блокуємо
    if "youtube.com" in url or "youtu.be" in url:
        bot.send_message(chat_id, t["yt_disabled"])
        return False

    # TikTok (кастом)
    if "tiktok.com" in url:
        return download_tiktok(url, chat_id, user, lang)

    # Instagram (кастом)
    if "instagram.com" in url:
        return download_instagram(url, chat_id, user, lang)

    # Все інше – generic через yt-dlp
    return download_generic(url, chat_id, user, lang)


# =============================== TIKTOK ===============================

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
        url
    ]

    # якщо обрано MP3 – качаємо тільки аудіо
    if fmt == "mp3":
        cmd = base_cmd + [
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "0",
        ]
    else:
        cmd = base_cmd + [
            "-f", "bv*+ba/best",
        ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print("TikTok error:", e.stderr)
        bot.send_message(chat_id, t["tiktok_error"])
        return False

    files = glob.glob(os.path.join(DOWNLOAD_DIR, f"{chat_id}_tt.*"))
    if not files:
        bot.send_message(chat_id, t["download_failed"])
        return False

    audio_exts = (".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav")
    video_exts = (".mp4", ".webm", ".mov", ".mkv")
    image_exts = (".jpg", ".jpeg", ".png", ".webp")

    # Якщо формат mp3 → шукаємо аудіо
    if fmt == "mp3":
        for path in files:
            ext = os.path.splitext(path)[1].lower()
            if ext in audio_exts:
                with open(path, "rb") as f:
                    bot.send_audio(chat_id, f)
                _cleanup_files(files)
                return True
        bot.send_message(chat_id, t["download_failed"])
        _cleanup_files(files)
        return False

    # Спочатку пробуємо відео
    for path in files:
        ext = os.path.splitext(path)[1].lower()
        if ext in video_exts:
            with open(path, "rb") as f:
                bot.send_video(chat_id, f)
            _cleanup_files(files)
            return True

    # Якщо відео нема – пробуємо картинки (TikTok photo post)
    img_paths = [p for p in files if os.path.splitext(p)[1].lower() in image_exts]
    if img_paths:
        if len(img_paths) == 1:
            with open(img_paths[0], "rb") as f:
                bot.send_photo(chat_id, f, caption=t.get("tiktok_photo_caption", ""))
        else:
            media = []
            for i, p in enumerate(sorted(img_paths)):
                f = open(p, "rb")
                if i == 0:
                    media.append(types.InputMediaPhoto(f, caption=t.get("tiktok_photo_caption", "")))
                else:
                    media.append(types.InputMediaPhoto(f))
            bot.send_media_group(chat_id, media)
        _cleanup_files(files)
        return True

    bot.send_message(chat_id, t["download_failed"])
    _cleanup_files(files)
    return False


# =============================== INSTAGRAM ===============================

def download_instagram(url, chat_id, user, lang):
    t = texts[lang]
    fmt = user["format"]
    template = os.path.join(DOWNLOAD_DIR, f"{chat_id}_ig.%(ext)s")

    base_cmd = [
        "yt-dlp",
        "--force-ipv4",
        "--no-check-certificates",
        "-o", template,
        url
    ]

    if fmt == "mp3":
        cmd = base_cmd + [
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "0",
        ]
    else:
        cmd = base_cmd + [
            "-f", "bestvideo*+bestaudio/best",
            "--merge-output-format", "mp4",
        ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print("Instagram error:", e.stderr)
        bot.send_message(chat_id, t["ig_error"])
        return False

    files = glob.glob(os.path.join(DOWNLOAD_DIR, f"{chat_id}_ig.*"))
    if not files:
        bot.send_message(chat_id, t["download_failed"])
        return False

    audio_exts = (".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav")
    video_exts = (".mp4", ".webm", ".mov", ".mkv")
    image_exts = (".jpg", ".jpeg", ".png", ".webp")

    if fmt == "mp3":
        for path in files:
            ext = os.path.splitext(path)[1].lower()
            if ext in audio_exts:
                with open(path, "rb") as f:
                    bot.send_audio(chat_id, f)
                _cleanup_files(files)
                return True
        bot.send_message(chat_id, t["download_failed"])
        _cleanup_files(files)
        return False

    # відео
    for path in files:
        ext = os.path.splitext(path)[1].lower()
        if ext in video_exts:
            with open(path, "rb") as f:
                bot.send_video(chat_id, f)
            _cleanup_files(files)
            return True

    # картинки (якщо фото-пост)
    img_paths = [p for p in files if os.path.splitext(p)[1].lower() in image_exts]
    if img_paths:
        if len(img_paths) == 1:
            with open(img_paths[0], "rb") as f:
                bot.send_photo(chat_id, f)
        else:
            media = []
            for p in sorted(img_paths):
                f = open(p, "rb")
                media.append(types.InputMediaPhoto(f))
            bot.send_media_group(chat_id, media)
        _cleanup_files(files)
        return True

    bot.send_message(chat_id, t["download_failed"])
    _cleanup_files(files)
    return False


# =============================== GENERIC (ВСЕ ІНШЕ) ===============================

def download_generic(url, chat_id, user, lang):
    t = texts[lang]
    fmt = user["format"]

    # унікальне імʼя файлу
    ts = str(datetime.now().timestamp()).replace(".", "")
    base_name = f"{chat_id}_gen_{ts}"
    template = os.path.join(DOWNLOAD_DIR, base_name + ".%(ext)s")

    cmd = [
        "yt-dlp",
        "--force-ipv4",
        "--no-check-certificates",
        "-o", template,
        url
    ]

    if fmt == "mp3":
        cmd += [
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "0",
        ]
    elif fmt == "webm":
        cmd += [
            "-f", "bestvideo*+bestaudio/best",
            "--merge-output-format", "webm",
        ]
    else:  # mp4 або інше → mp4
        cmd += [
            "-f", "bestvideo*+bestaudio/best",
            "--merge-output-format", "mp4",
        ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print("Generic error:", e.stderr)
        bot.send_message(chat_id, t["download_failed"])
        return False

    files = glob.glob(os.path.join(DOWNLOAD_DIR, base_name + ".*"))
    if not files:
        bot.send_message(chat_id, t["download_failed"])
        return False

    audio_exts = (".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav")
    video_exts = (".mp4", ".webm", ".mov", ".mkv")

    # Якщо формат mp3 → відправляємо аудіо
    if fmt == "mp3":
        for path in files:
            if os.path.splitext(path)[1].lower() in audio_exts:
                with open(path, "rb") as f:
                    bot.send_audio(chat_id, f)
                _cleanup_files(files)
                return True
        bot.send_message(chat_id, t["download_failed"])
        _cleanup_files(files)
        return False

    # Інакше шукаємо відео
    for path in files:
        if os.path.splitext(path)[1].lower() in video_exts:
            with open(path, "rb") as f:
                bot.send_video(chat_id, f)
            _cleanup_files(files)
            return True

    bot.send_message(chat_id, t["download_failed"])
    _cleanup_files(files)
    return False


def _cleanup_files(files):
    for p in files:
        try:
            os.remove(p)
        except:
            pass


# ============================================================
#                     ХЕНДЛЕРИ ПОВІДОМЛЕНЬ
# ============================================================

@bot.message_handler(commands=["start"])
def start(m):
    u = get_user(m.from_user)
    lang = u["language"]
    bot.send_message(m.chat.id, texts[lang]["welcome"], reply_markup=main_menu(lang))


@bot.message_handler(func=lambda m: True)
def msg(m):
    u = get_user(m.from_user)
    lang = u["language"]
    t = texts[lang]

    raw_text = m.text or ""
    txt = clean_text(raw_text)

    # -------- URL --------
    if raw_text.strip().lower().startswith("http"):
        bot.send_message(m.chat.id, t["loading"])
        ok = download_from_url(raw_text.strip(), m.chat.id, u, lang)

        if ok:
            u["videos_downloaded"] += 1
            save_users(users)
        return

    # -------- Команди --------
    cmd = match_cmd(txt)

    # --- Меню ---
    if cmd == "menu":
        bot.send_message(m.chat.id, t["enter_url"], reply_markup=main_menu(lang))
        return

    # --- Профіль ---
    if cmd == "profile":
        bot.send_message(m.chat.id, (
            f"👤 {t['profile']}\n\n"
            f"🆔 `{m.from_user.id}`\n"
            f"👋 {t['lbl_name']}: {u['name']}\n"
            f"🎥 {t['lbl_downloaded']}: {u['videos_downloaded']}\n"
            f"🎞️ {t['lbl_format']}: {u['format'].upper()}\n"
            f"🎬 {t['lbl_video_plus_audio']}: {t['yes'] if u['video_plus_audio'] else t['no']}\n"
            f"📅 {t['lbl_since']}: {u['joined']}\n"
        ), parse_mode="Markdown", reply_markup=main_menu(lang))
        return

    # --- Зміна мови ---
    if cmd == "language":
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk"))
        kb.add(types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"))
        kb.add(types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"))
        kb.add(types.InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr"))
        kb.add(types.InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de"))

        bot.send_message(m.chat.id, t["language"], reply_markup=kb)
        return

    # --- Налаштування ---
    if cmd == "settings":
        bot.send_message(m.chat.id, f"⚙️ {t['settings']}:", reply_markup=settings_keyboard(u))
        return

    # --- Підписка ---
    if cmd == "subscription":
        bot.send_message(m.chat.id, t["free_version"], reply_markup=main_menu(lang))
        return

    # --- Про бота ---
    if cmd == "help":
        bot.send_message(m.chat.id, t["help_text"], reply_markup=main_menu(lang))
        return

    # --- Невідоме повідомлення ---
    bot.send_message(m.chat.id, t["not_understood"], reply_markup=main_menu(lang))

# ============================================================
#                     WEBHOOK
# ============================================================

@app.route("/", methods=["GET"])
def home():
    return "Bot is running!"

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook_receiver():
    update = types.Update.de_json(request.get_json())
    bot.process_new_updates([update])
    return "OK", 200


# ============================================================
#                    RUN SERVER
# ============================================================

if __name__ == "__main__":
    print("🚀 Запуск Flask + Webhook")

    bot.delete_webhook()
    bot.set_webhook(url=WEBHOOK_URL)

    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))







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

from languages import texts   # файл languages.py (словник texts = { "uk": {...}, ... })


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
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M"),
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
    # Прибираємо емодзі та зайві символи, лишаємо букви/цифри/пробіли
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
    "settings": [
        "налаштування", "налаш", "настройки",
        "settings",
        "einstellungen",
        "paramètres", "parametre"
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
            if clean_text(v) in text:
                return cmd
    return None


# ============================================================
#                 КЛАВІАТУРИ (тільки INLINE)
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
    kb.add(
        types.InlineKeyboardButton(
            f"{t['lbl_video_plus_audio']}: {vpa_state}",
            callback_data="toggle_vpa",
        )
    )

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

    # ---------- КОМАНДИ МЕНЮ (інлайн кнопки) ----------
    if data == "cmd_menu":
        bot.send_message(c.message.chat.id, t["enter_url"])
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
        bot.send_message(
            c.message.chat.id,
            msg_text,
            parse_mode="Markdown",
        )
        return

    if data == "cmd_settings":
        bot.send_message(
            c.message.chat.id,
            f"⚙️ {t['settings']}:",
            reply_markup=settings_keyboard(user),
        )
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

    if data == "cmd_sub":
        bot.send_message(c.message.chat.id, t["free_version"])
        return

    if data == "cmd_help":
        bot.send_message(c.message.chat.id, t["help_text"])
        return

    if data == "cmd_back":
        bot.send_message(c.message.chat.id, t["enter_url"])
        return

    # ---------- ЗМІНА МОВИ ----------
    if data.startswith("lang_"):
        new_lang = data.replace("lang_", "")
        if new_lang in texts:
            user["language"] = new_lang
            save_users(users)

            t_new = texts[new_lang]
            bot.answer_callback_query(c.id, t_new["lang_saved"])

            try:
                bot.delete_message(c.message.chat.id, c.message.message_id)
            except:
                pass

            bot.send_message(
                c.message.chat.id,
                t_new["welcome"],
            )
        return

    # ---------- НАЛАШТУВАННЯ ФОРМАТУ ----------
    if data.startswith("format_"):
        fmt = data.replace("format_", "")
        user["format"] = fmt
        user["audio_only"] = (fmt == "mp3")
        save_users(users)

        bot.answer_callback_query(c.id, "✔ Збережено!")
        bot.edit_message_reply_markup(
            c.message.chat.id,
            c.message.message_id,
            reply_markup=settings_keyboard(user),
        )
        return

    # ---------- ПЕРЕМИКАЧ "ВІДЕО + АУДІО" ----------
    if data == "toggle_vpa":
        user["video_plus_audio"] = not user["video_plus_audio"]
        save_users(users)

        bot.answer_callback_query(c.id, "✔ Збережено!")
        bot.edit_message_reply_markup(
            c.message.chat.id,
            c.message.message_id,
            reply_markup=settings_keyboard(user),
        )
        return


# ============================================================
#        ЗАВАНТАЖЕННЯ: TIKTOK / INSTAGRAM / ГЕНЕРИК
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
        url,
    ]

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

    if fmt == "mp3":
        audio_path = None
        for path in files:
            if os.path.splitext(path)[1].lower() in audio_exts:
                audio_path = path
                break
        if audio_path:
            with open(audio_path, "rb") as f:
                bot.send_audio(chat_id, f)
            _cleanup_files(files)
            return True

        bot.send_message(chat_id, t["download_failed"])
        _cleanup_files(files)
        return False

    video_path = None
    for path in files:
        if os.path.splitext(path)[1].lower() in video_exts:
            video_path = path
            break

    audio_path = None
    for path in files:
        if os.path.splitext(path)[1].lower() in audio_exts:
            audio_path = path
            break

    if video_path:
        with open(video_path, "rb") as f:
            bot.send_video(chat_id, f)

        if user.get("video_plus_audio") and audio_path:
            with open(audio_path, "rb") as f:
                bot.send_audio(chat_id, f)

        _cleanup_files(files)
        return True

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
        url,
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
        audio_path = None
        for path in files:
            if os.path.splitext(path)[1].lower() in audio_exts:
                audio_path = path
                break
        if audio_path:
            with open(audio_path, "rb") as f:
                bot.send_audio(chat_id, f)
            _cleanup_files(files)
            return True
        bot.send_message(chat_id, t["download_failed"])
        _cleanup_files(files)
        return False

    video_path = None
    for path in files:
        if os.path.splitext(path)[1].lower() in video_exts:
            video_path = path
            break

    if video_path:
        with open(video_path, "rb") as f:
            bot.send_video(chat_id, f)
        _cleanup_files(files)
        return True

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
    else:
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

    if fmt == "mp3":
        audio_path = None
        for path in files:
            if os.path.splitext(path)[1].lower() in audio_exts:
                audio_path = path
                break
        if audio_path:
            with open(audio_path, "rb") as f:
                bot.send_audio(chat_id, f)
            _cleanup_files(files)
            return True
        bot.send_message(chat_id, t["download_failed"])
        _cleanup_files(files)
        return False

    video_path = None
    for path in files:
        if os.path.splitext(path)[1].lower() in video_exts:
            video_path = path
            break

    if video_path:
        with open(video_path, "rb") as f:
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

    # УСТАНОВКА МЕНЮ СПРАВА
    bot.set_chat_menu_button(chat_id=m.chat.id, menu_button=types.MenuButtonCommands())

    bot.send_message(m.chat.id, texts[lang]["welcome"])



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

    # -------- Команди через текст (/menu, меню, menu...) --------
    cmd = match_cmd(txt)

    if cmd == "menu":
        bot.send_message(m.chat.id, t["enter_url"])
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
        bot.send_message(m.chat.id, t["free_version"])
        return

    if cmd == "help":
        bot.send_message(m.chat.id, t["help_text"])
        return

    bot.send_message(m.chat.id, t["not_understood"])


# ============================================================
#           КОМАНДИ ДЛЯ КНОПКИ-МЕНЮ В ПОЛІ ВВОДУ
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
    update = types.Update.de_json(request.get_json())
    bot.process_new_updates([update])
    return "OK", 200


# ============================================================
#                    RUN SERVER
# ============================================================

if __name__ == "__main__":
    print("🚀 Запуск Flask + Webhook")

    setup_bot_commands()  # ← включає меню біля поля вводу



    bot.delete_webhook()
    bot.set_webhook(url=WEBHOOK_URL)

    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))


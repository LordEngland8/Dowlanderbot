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

    # якщо раптом в users збереглась мова, якої вже немає в texts
    if users[uid]["language"] not in texts:
        users[uid]["language"] = "uk"
        save_users(users)

    return users[uid]


# ============================================================
#                 ОЧИЩЕННЯ ТЕКСТУ
# ============================================================

def clean_text(text):
    return re.sub(
        r"[^a-zA-Zа-яА-ЯёЁіІїЇєЄ0-9 ]",
        "",
        text or ""
    ).strip().lower()


# ============================================================
#                 ГОЛОВНЕ МЕНЮ (REPLY KEYBOARD)
# ============================================================

def main_menu(user):
    lang = user["language"]
    t = texts[lang]

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

    kb.row(
        types.KeyboardButton(f"📋 {t['menu']}"),
        types.KeyboardButton(f"👤 {t['profile']}")
    )
    kb.row(
        types.KeyboardButton(f"⚙️ {t['settings']}"),
        types.KeyboardButton(f"💎 {t['subscription']}")
    )
    kb.row(
        types.KeyboardButton(f"🌍 {t['language']}"),
        types.KeyboardButton(f"ℹ️ {t['help']}")
    )

    return kb


# ============================================================
#                 CALLBACK HANDLER (INLINE КНОПКИ)
# ============================================================

@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    user = get_user(c.from_user)
    lang = user["language"]
    t = texts[lang]

    bot.answer_callback_query(c.id)
    data = c.data

    # ---------- ФОРМАТ ----------
    if data.startswith("format_"):
        fmt = data.replace("format_", "")
        user["format"] = fmt
        user["audio_only"] = (fmt == "mp3")
        save_users(users)
        try:
            bot.answer_callback_query(c.id, t.get("saved", "✔ Збережено!"))
        except:
            pass
        return

    # ---------- ВІДЕО+АУДІО ----------
    if data == "toggle_vpa":
        user["video_plus_audio"] = not user["video_plus_audio"]
        save_users(users)
        try:
            bot.answer_callback_query(c.id, t.get("saved", "✔ Збережено!"))
        except:
            pass
        return

    # ---------- МОВА ----------
    if data.startswith("lang_"):
        new_lang = data.replace("lang_", "")
        if new_lang in texts:
            user["language"] = new_lang
            save_users(users)
            t_new = texts[new_lang]
            bot.send_message(c.message.chat.id, t_new["lang_saved"])
        return


# ============================================================
#             ЗАВАНТАЖЕННЯ КОНТЕНТУ
# ============================================================

def download_from_url(url, chat_id, user, lang):
    t = texts[lang]

    if "youtube.com" in url or "youtu.be" in url:
        # YouTube заблокований
        bot.send_message(chat_id, t["yt_disabled"])
        return False

    if "tiktok.com" in url:
        return download_site(url, chat_id, user, lang, "tt")

    if "instagram.com" in url:
        return download_site(url, chat_id, user, lang, "ig")

    return download_site(url, chat_id, user, lang, "gen")


def download_site(url, chat_id, user, lang, prefix):
    t = texts[lang]
    fmt = user["format"]

    template = os.path.join(DOWNLOAD_DIR, f"{chat_id}_{prefix}.%(ext)s")
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
    else:
        cmd += [
            "-f", "bestvideo*+bestaudio/best",
            "--merge-output-format", "mp4",
        ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print("Download error:", e.stderr)
        bot.send_message(chat_id, t["download_failed"])
        return False

    files = glob.glob(os.path.join(DOWNLOAD_DIR, f"{chat_id}_{prefix}.*"))
    if not files:
        bot.send_message(chat_id, t["download_failed"])
        return False

    audio_exts = (".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav")
    video_exts = (".mp4", ".webm", ".mov", ".mkv")
    image_exts = (".jpg", ".jpeg", ".png", ".webp")

    # Якщо mp3 — шукаємо аудіо
    if fmt == "mp3":
        audio_path = None
        for p in files:
            if os.path.splitext(p)[1].lower() in audio_exts:
                audio_path = p
                break
        if audio_path:
            with open(audio_path, "rb") as f:
                bot.send_audio(chat_id, f)
            _cleanup_files(files)
            return True
        bot.send_message(chat_id, t["download_failed"])
        _cleanup_files(files)
        return False

    # Якщо відео
    video_path = None
    for p in files:
        if os.path.splitext(p)[1].lower() in video_exts:
            video_path = p
            break

    if video_path:
        with open(video_path, "rb") as f:
            bot.send_video(chat_id, f)
        _cleanup_files(files)
        return True

    # Можливо, картинки (наприклад, карусель)
    img_paths = [p for p in files if os.path.splitext(p)[1].lower() in image_exts]
    if img_paths:
        if len(img_paths) == 1:
            with open(img_paths[0], "rb") as f:
                bot.send_photo(chat_id, f)
        else:
            media = []
            for i, p in enumerate(sorted(img_paths)):
                f = open(p, "rb")
                if i == 0:
                    media.append(types.InputMediaPhoto(f))
                else:
                    media.append(types.InputMediaPhoto(f))
            bot.send_media_group(chat_id, media)
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

    # ❗ просимо Telegram повернути СТАНДАРТНУ кнопку меню (а не команд)
    try:
        bot.set_chat_menu_button(chat_id=m.chat.id, menu_button=types.MenuButtonDefault())
    except:
        pass

    bot.send_message(
        m.chat.id,
        texts[lang]["welcome"],
        reply_markup=main_menu(u)
    )


@bot.message_handler(func=lambda m: True)
def msg(m):
    u = get_user(m.from_user)
    lang = u["language"]
    t = texts[lang]

    raw = m.text or ""
    txt = clean_text(raw)

    # -------- URL --------
    if raw.strip().lower().startswith("http"):
        bot.send_message(m.chat.id, t["loading"])
        ok = download_from_url(raw.strip(), m.chat.id, u, lang)
        if ok:
            u["videos_downloaded"] += 1
            save_users(users)
        return

    # -------- КНОПКИ REPLY-МЕНЮ --------
    if txt == clean_text(f"📋 {t['menu']}"):
        bot.send_message(m.chat.id, t["enter_url"], reply_markup=main_menu(u))
        return

    if txt == clean_text(f"👤 {t['profile']}"):
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
            reply_markup=main_menu(u)
        )
        return

    if txt == clean_text(f"⚙️ {t['settings']}"):
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.row(
            types.InlineKeyboardButton("MP4", callback_data="format_mp4"),
            types.InlineKeyboardButton("MP3", callback_data="format_mp3"),
        )
        kb.add(types.InlineKeyboardButton("WEBM", callback_data="format_webm"))
        kb.add(
            types.InlineKeyboardButton(
                f"{t['lbl_video_plus_audio']}: "
                f"{t['yes'] if u['video_plus_audio'] else t['no']}",
                callback_data="toggle_vpa"
            )
        )
        bot.send_message(m.chat.id, t["settings"], reply_markup=kb)
        return

    if txt == clean_text(f"💎 {t['subscription']}"):
        bot.send_message(m.chat.id, t["free_version"], reply_markup=main_menu(u))
        return

    if txt == clean_text(f"🌍 {t['language']}"):
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk"))
        kb.add(types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"))
        kb.add(types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"))
        kb.add(types.InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de"))
        kb.add(types.InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr"))
        bot.send_message(m.chat.id, t["language"], reply_markup=kb)
        return

    if txt == clean_text(f"ℹ️ {t['help']}"):
        bot.send_message(m.chat.id, t["help_text"], reply_markup=main_menu(u))
        return

    # -------- Якщо нічого не підійшло --------
    bot.send_message(m.chat.id, t["not_understood"], reply_markup=main_menu(u))


# ============================================================
#         ПОВНЕ ВИДАЛЕННЯ ВСІХ КОМАНД У ТЕЛЕГРАМ
# ============================================================

def remove_all_commands():
    try:
        # language_code=None → для всіх мов одразу
        bot.set_my_commands([], language_code=None)
        print("❎ УСІ TELEGRAM-КОМАНДИ БУЛИ ВИДАЛЕНІ")
    except Exception as e:
        print("Error removing commands:", e)


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
    # перед запуском – ОЧИЩАЄМО ВСІ КОМАНДИ БОТА В TELEGRAM
    remove_all_commands()

    bot.delete_webhook()
    bot.set_webhook(url=WEBHOOK_URL)

    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

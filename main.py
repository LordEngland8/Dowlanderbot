import os
import json
import glob
import subprocess
from datetime import datetime
import threading

from telebot import TeleBot, types
from flask import Flask, request

# ============================================================
#                       КОНФІГ
# ============================================================

# Токен беремо з Render (env var TOKEN) або локально TELEGRAM_TOKEN
TOKEN = os.getenv("TOKEN") or os.getenv("TELEGRAM_TOKEN", "")
if not TOKEN or ":" not in TOKEN:
    raise ValueError("❌ TOKEN не встановлено або некоректний!")

WEBHOOK_HOST = "https://dowlanderbot-2.onrender.com"  # ← твій Render URL
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = WEBHOOK_HOST + WEBHOOK_PATH

bot = TeleBot(TOKEN, threaded=False)   # threaded=False, бо самі робимо потоки
app = Flask(__name__)

USER_FILE = "users.json"
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ============================================================
#                 РОБОТА З КОРИСТУВАЧАМИ
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
            "format": "mp4",           # mp4 | mp3 | webm
            "audio_only": False,       # якщо True — форс MP3
            "include_description": True,
            "video_plus_audio": True   # відео + аудіо (окремим файлом)
        }
        save_users(users)

    # санітизація мови
    if users[uid]["language"] not in ["uk", "en", "ru", "fr", "de"]:
        users[uid]["language"] = "uk"
        save_users(users)
    return users[uid]

# ============================================================
#                        ТЕКСТИ
# ============================================================

texts = {
    "uk": {
        "menu": "Меню",
        "profile": "Профіль",
        "subscription": "Підписка",
        "settings": "Налаштування",
        "language": "Мова",
        "help": "Про бота",
        "back": "Назад",
        "lang_saved": "✅ Мову збережено! 🇺🇦",
        "welcome": "👋 Привіт! Надішли посилання на відео (YouTube, TikTok, Instagram, Facebook, Twitter тощо)",
        "enter_url": "📎 Надішли посилання на відео!",
        "free_version": "💎 Безкоштовна версія. Premium скоро ✨",
        "help_text": "🤖 Бот уміє:\n• Завантажувати відео з багатьох сайтів (yt-dlp)\n• Показувати профіль\n• Має гнучкі налаштування",
        "not_understood": "😅 Не розумію, обери кнопку нижче.",
        "lbl_name": "Ім’я",
        "lbl_subscription": "Підписка",
        "lbl_downloaded": "Завантажено",
        "lbl_format": "Формат",
        "lbl_only_audio": "Тільки звук",
        "lbl_description": "Опис відео",
        "lbl_video_plus_audio": "Відео + Аудіо",
        "lbl_since": "З",
        "yes": "✅ Так",
        "no": "❌ Ні",
        "subscription_names": {
            "free": "Безкоштовна 💎",
            "premium": "Преміум 💠"
        }
    },
    "en": {
        "menu": "Menu",
        "profile": "Profile",
        "subscription": "Subscription",
        "settings": "Settings",
        "language": "Language",
        "help": "About bot",
        "back": "Back",
        "lang_saved": "✅ Language saved! 🇬🇧",
        "welcome": "👋 Hello! Send a link (YouTube, TikTok, Instagram, Facebook, Twitter, etc.)",
        "enter_url": "📎 Send me a video link!",
        "free_version": "💎 Free version. Premium coming soon ✨",
        "help_text": "🤖 The bot can:\n• Download from many sites (yt-dlp)\n• Show profile\n• Has flexible settings",
        "not_understood": "😅 I don't understand, choose a button below.",
        "lbl_name": "Name",
        "lbl_subscription": "Subscription",
        "lbl_downloaded": "Downloaded",
        "lbl_format": "Format",
        "lbl_only_audio": "Audio only",
        "lbl_description": "Video description",
        "lbl_video_plus_audio": "Video + Audio",
        "lbl_since": "Since",
        "yes": "✅ Yes",
        "no": "❌ No",
        "subscription_names": {
            "free": "Free 💎",
            "premium": "Premium 💠"
        }
    },
    "ru": {
        "menu": "Меню",
        "profile": "Профиль",
        "subscription": "Подписка",
        "settings": "Настройки",
        "language": "Язык",
        "help": "О боте",
        "back": "Назад",
        "lang_saved": "✅ Язык сохранён! 🇷🇺",
        "welcome": "👋 Привет! Пришли ссылку (YouTube, TikTok, Instagram, Facebook, Twitter и т.д.)",
        "enter_url": "📎 Пришли ссылку на видео!",
        "free_version": "💎 Бесплатная версия. Premium скоро ✨",
        "help_text": "🤖 Бот умеет:\n• Скачивать с многих сайтов (yt-dlp)\n• Показывать профиль\n• Имеет гибкие настройки",
        "not_understood": "😅 Не понимаю, выбери кнопку ниже.",
        "lbl_name": "Имя",
        "lbl_subscription": "Подписка",
        "lbl_downloaded": "Скачано",
        "lbl_format": "Формат",
        "lbl_only_audio": "Только аудио",
        "lbl_description": "Описание видео",
        "lbl_video_plus_audio": "Видео + Аудио",
        "lbl_since": "С",
        "yes": "✅ Да",
        "no": "❌ Нет",
        "subscription_names": {
            "free": "Бесплатная 💎",
            "premium": "Премиум 💠"
        }
    },
    "fr": {
        "menu": "Menu",
        "profile": "Profil",
        "subscription": "Abonnement",
        "settings": "Paramètres",
        "language": "Langue",
        "help": "À propos du bot",
        "back": "Retour",
        "lang_saved": "✅ Langue enregistrée! 🇫🇷",
        "welcome": "👋 Bonjour ! Envoie un lien (YouTube, TikTok, Instagram, etc.)",
        "enter_url": "📎 Envoie un lien vidéo !",
        "free_version": "💎 Version gratuite. Premium bientôt ✨",
        "help_text": "🤖 Le bot peut :\n• Télécharger depuis de nombreux sites (yt-dlp)\n• Afficher le profil\n• Paramètres flexibles",
        "not_understood": "😅 Je ne comprends pas, choisis un bouton.",
        "lbl_name": "Nom",
        "lbl_subscription": "Abonnement",
        "lbl_downloaded": "Téléchargé",
        "lbl_format": "Format",
        "lbl_only_audio": "Audio uniquement",
        "lbl_description": "Description",
        "lbl_video_plus_audio": "Vidéo + Audio",
        "lbl_since": "Depuis",
        "yes": "✅ Oui",
        "no": "❌ Non",
        "subscription_names": {
            "free": "Gratuit 💎",
            "premium": "Premium 💠"
        }
    },
    "de": {
        "menu": "Menü",
        "profile": "Profil",
        "subscription": "Abonnement",
        "settings": "Einstellungen",
        "language": "Sprache",
        "help": "Über den Bot",
        "back": "Zurück",
        "lang_saved": "✅ Sprache gespeichert! 🇩🇪",
        "welcome": "👋 Hallo! Sende einen Link (YouTube, TikTok, Instagram, Facebook, Twitter usw.)",
        "enter_url": "📎 Sende einen Videolink!",
        "free_version": "💎 Kostenlose Version. Premium bald ✨",
        "help_text": "🤖 Der Bot kann:\n• Von vielen Seiten laden (yt-dlp)\n• Profil anzeigen\n• Flexible Einstellungen",
        "not_understood": "😅 Ich verstehe nicht, wähle einen Button unten.",
        "lbl_name": "Name",
        "lbl_subscription": "Abonnement",
        "lbl_downloaded": "Heruntergeladen",
        "lbl_format": "Format",
        "lbl_only_audio": "Nur Audio",
        "lbl_description": "Videobeschreibung",
        "lbl_video_plus_audio": "Video + Audio",
        "lbl_since": "Seit",
        "yes": "✅ Ja",
        "no": "❌ Nein",
        "subscription_names": {
            "free": "Kostenlos 💎",
            "premium": "Premium 💠"
        }
    }
}

# ============================================================
#                    КЛАВІАТУРИ
# ============================================================

def main_menu(lang="uk"):
    t = texts.get(lang, texts["uk"])
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        types.KeyboardButton(f"📋 {t['menu']}"),
        types.KeyboardButton(f"👤 {t['profile']}"),
        types.KeyboardButton(f"⚙️ {t['settings']}"),
        types.KeyboardButton(f"💎 {t['subscription']}"),
        types.KeyboardButton(f"🌍 {t['language']}"),
        types.KeyboardButton(f"ℹ️ {t['help']}")
    )
    return kb

def back_menu(lang="uk"):
    t = texts.get(lang, texts["uk"])
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton(f"⬅️ {t['back']}"))
    return kb

def ask_language(cid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    langs = [
        ("🇺🇦 Українська", "uk"),
        ("🇬🇧 English", "en"),
        ("🇷🇺 Русский", "ru"),
        ("🇫🇷 Français", "fr"),
        ("🇩🇪 Deutsch", "de")
    ]
    for text_btn, code in langs:
        kb.add(types.InlineKeyboardButton(text_btn, callback_data=f"lang_{code}"))
    bot.send_message(cid, "🌍 Вибери мову:", reply_markup=kb)

def show_settings(chat_id, user, lang):
    t = texts.get(lang, texts["uk"])
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🎞️ MP4", callback_data="set_format_mp4"),
        types.InlineKeyboardButton("🎧 MP3", callback_data="set_format_mp3"),
        types.InlineKeyboardButton("🌐 WEBM", callback_data="set_format_webm")
    )
    kb.add(
        types.InlineKeyboardButton(
            f"📝 {t['lbl_description']}: {t['yes'] if user['include_description'] else t['no']}",
            callback_data="toggle_desc"
        )
    )
    kb.add(
        types.InlineKeyboardButton(
            f"🎬 {t['lbl_video_plus_audio']}: {t['yes'] if user['video_plus_audio'] else t['no']}",
            callback_data="toggle_vpa"
        )
    )
    kb.add(types.InlineKeyboardButton(f"⬅️ {t['back']}", callback_data="back_to_menu"))
    bot.send_message(chat_id, f"⚙️ {t['settings']}", reply_markup=kb)

# ============================================================
#                      CALLBACK'И
# ============================================================

@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    user = get_user(c.from_user)
    lang = user.get("language", "uk")
    t = texts.get(lang, texts["uk"])

    if c.data.startswith("lang_"):
        user["language"] = c.data.split("_")[1]
        save_users(users)
        try:
            bot.delete_message(c.message.chat.id, c.message.message_id)
        except Exception:
            pass
        bot.send_message(
            c.message.chat.id,
            texts[user["language"]]["lang_saved"],
            reply_markup=main_menu(user["language"])
        )
        return

    if c.data == "back_to_menu":
        try:
            bot.delete_message(c.message.chat.id, c.message.message_id)
        except Exception:
            pass
        bot.send_message(c.message.chat.id, t["menu"], reply_markup=main_menu(lang))
        return

    if c.data.startswith("set_format_"):
        user["format"] = c.data.split("_")[2]
        user["audio_only"] = (user["format"] == "mp3")
        bot.answer_callback_query(c.id, f"✅ {t['lbl_format']}: {user['format'].upper()}")

    elif c.data == "toggle_desc":
        user["include_description"] = not user["include_description"]
        bot.answer_callback_query(
            c.id,
            f"📝 {t['lbl_description']}: {t['yes'] if user['include_description'] else t['no']}"
        )

    elif c.data == "toggle_vpa":
        user["video_plus_audio"] = not user["video_plus_audio"]
        bot.answer_callback_query(
            c.id,
            f"🎬 {t['lbl_video_plus_audio']}: {t['yes'] if user['video_plus_audio'] else t['no']}"
        )

    save_users(users)
    try:
        bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=None)
    except Exception:
        pass
    show_settings(c.message.chat.id, user, lang)

# ============================================================
#                  ЗАВАНТАЖЕННЯ ВІДЕО (yt-dlp)
# ============================================================

def build_yt_dlp_cmd(url: str, fmt: str, audio_only: bool) -> list:
    cmd = ["yt-dlp"]
    if audio_only or fmt == "mp3":
        cmd += ["-x", "--audio-format", "mp3"]
    elif fmt == "webm":
        cmd += ["-S", "ext:webm", "-f", "bv*+ba/b"]
    else:
        cmd += ["-S", "ext:mp4:m4a", "-f", "bv*+ba/b"]

    cmd += [url]
    return cmd

def download_and_send(url: str, chat_id: int, lang: str, user: dict):
    """
    Завантажує відео + (опціонально) аудіо, надсилає користувачу.
    Підтримує:
    - mp4 / mp3 / webm
    - опис відео
    - відео + аудіо
    - очищення тимчасових файлів
    """

    t = texts.get(lang, texts["uk"])

    fmt = user.get("format", "mp4").lower()
    video_plus_audio = bool(user.get("video_plus_audio", True))
    include_desc = bool(user.get("include_description", True))

    wait_msg = bot.send_message(chat_id, "⏳ Завантаження… зачекай трохи.")
    wait_msg_id = wait_msg.message_id

    # === Формуємо команду yt-dlp ===
    def build_cmd(fmt: str):
        if fmt == "mp3":
            return ["yt-dlp", "-x", "--audio-format", "mp3"]
        elif fmt == "webm":
            return ["yt-dlp", "-S", "ext:webm", "-f", "bv*+ba/b"]
        else:
            return ["yt-dlp", "-S", "ext:mp4:m4a", "-f", "bv*+ba/b"]

    cmd = build_cmd(fmt)

    outtmpl_video = os.path.join(DOWNLOAD_DIR, f"{chat_id}_video.%(ext)s")

    # Додаємо -o перед URL
    cmd += ["-o", outtmpl_video, url]

    # === Качаємо відео ===
    try:
        subprocess.run(cmd, check=True)
    except Exception as e:
        bot.edit_message_text(
            f"❌ Помилка при завантаженні відео:\n`{e}`",
            chat_id,
            wait_msg_id,
            parse_mode="Markdown"
        )
        return

    # === Шукаємо відеофайл ===
    video_candidates = glob.glob(os.path.join(DOWNLOAD_DIR, f"{chat_id}_video.*"))
    if not video_candidates:
        bot.edit_message_text("❌ Відео не знайдено після завантаження.", chat_id, wait_msg_id)
        return

    video_file = sorted(video_candidates, key=os.path.getmtime)[-1]

    # === Качаємо аудіо окремо (якщо потрібно) ===
    audio_file = None
    if video_plus_audio:
        audio_path = os.path.join(DOWNLOAD_DIR, f"{chat_id}_audio.mp3")
        cmd_audio = ["yt-dlp", "-x", "--audio-format", "mp3", "-o", audio_path, url]

        try:
            subprocess.run(cmd_audio, check=True)
            audio_file = audio_path
        except Exception:
            audio_file = None

    # === Отримуємо title + description ===
    caption = None
    if include_desc:
        try:
            meta_cmd = ["yt-dlp", "--get-title", "--get-description", url]
            meta = subprocess.check_output(meta_cmd).decode("utf-8", errors="ignore").splitlines()

            title = meta[0] if meta else ""
            descr = "\n".join(meta[1:]) if len(meta) > 1 else ""

            if len(descr) > 900:
                descr = descr[:900] + "…"

            caption = (title + "\n\n" + descr).strip()
            if caption == "":
                caption = None
        except Exception:
            caption = None

    # === Надсилаємо відео ===
    try:
        with open(video_file, "rb") as f:
            bot.send_video(chat_id, f, caption=caption)
    except Exception:
        bot.edit_message_text(
            "❌ Не вдалося відправити відео (можливо, файл занадто великий).",
            chat_id,
            wait_msg_id
        )
        return

    # === Надсилаємо аудіо (якщо завантажене) ===
    if audio_file:
        try:
            with open(audio_file, "rb") as f:
                bot.send_audio(chat_id, f, caption=caption)
        except Exception:
            pass

    # === Очищення файлів ===
    try:
        os.remove(video_file)
        if audio_file:
            os.remove(audio_file)
    except:
        pass

    # === Успіх ===
    bot.edit_message_text("✅ Готово!", chat_id, wait_msg_id)

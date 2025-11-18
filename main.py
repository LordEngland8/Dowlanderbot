import os
import json
import glob
import subprocess
from datetime import datetime

from telebot import TeleBot, types
from flask import Flask, request

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
            "format": "mp4",
            "audio_only": False,
            "video_plus_audio": True
        }
        save_users(users)

    if users[uid]["language"] not in ["uk", "en", "ru", "fr", "de"]:
        users[uid]["language"] = "uk"
        save_users(users)

    return users[uid]


# ============================================================
#                  ПЕРЕКЛАДИ
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
        "welcome": "👋 Привіт! Надішли посилання на відео.",
        "enter_url": "📎 Надішли посилання!",
        "free_version": "💎 Безкоштовна версія.",
        "help_text": "🤖 Бот вміє:\n• Завантажувати відео\n• Показувати профіль\n• Має налаштування",
        "not_understood": "😅 Не розумію, обери кнопку.",

        "lbl_name": "Ім’я",
        "lbl_subscription": "Підписка",
        "lbl_downloaded": "Завантажено",
        "lbl_format": "Формат",
        "lbl_video_plus_audio": "Відео + Аудіо",
        "lbl_since": "З",
        "yes": "Так",
        "no": "Ні",

        "subscription_names": {"free": "Безкоштовна 💎"}
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
        "welcome": "👋 Hello! Send a link.",
        "enter_url": "📎 Send a link!",
        "free_version": "💎 Free version.",
        "help_text": "🤖 Bot can:\n• Download videos\n• Show profile\n• Has settings",
        "not_understood": "😅 I don't understand.",

        "lbl_name": "Name",
        "lbl_subscription": "Subscription",
        "lbl_downloaded": "Downloaded",
        "lbl_format": "Format",
        "lbl_video_plus_audio": "Video + Audio",
        "lbl_since": "Since",
        "yes": "Yes",
        "no": "No",

        "subscription_names": {"free": "Free 💎"}
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
        "welcome": "👋 Привет! Пришли ссылку.",
        "enter_url": "📎 Пришли ссылку!",
        "free_version": "💎 Бесплатная версия.",
        "help_text": "🤖 Бот умеет:\n• Скачать видео\n• Показать профиль\n• Настройки",
        "not_understood": "😅 Не понимаю.",

        "lbl_name": "Имя",
        "lbl_subscription": "Подписка",
        "lbl_downloaded": "Скачано",
        "lbl_format": "Формат",
        "lbl_video_plus_audio": "Видео + Аудио",
        "lbl_since": "С",
        "yes": "Да",
        "no": "Нет",

        "subscription_names": {"free": "Бесплатная 💎"}
    },

    "fr": {
        "menu": "Menu",
        "profile": "Profil",
        "subscription": "Abonnement",
        "settings": "Paramètres",
        "language": "Langue",
        "help": "À propos du bot",
        "back": "Retour",

        "lang_saved": "🇫🇷 Langue enregistrée!",
        "welcome": "👋 Bonjour ! Envoie un lien.",
        "enter_url": "📎 Envoie un lien!",
        "free_version": "💎 Version gratuite.",
        "help_text": "🤖 Le bot peut:\n• Télécharger des vidéos\n• Afficher le profil\n• Paramètres",
        "not_understood": "😅 Pas compris.",

        "lbl_name": "Nom",
        "lbl_subscription": "Abonnement",
        "lbl_downloaded": "Téléchargé",
        "lbl_format": "Format",
        "lbl_video_plus_audio": "Vidéo + Audio",
        "lbl_since": "Depuis",
        "yes": "Oui",
        "no": "Non",

        "subscription_names": {"free": "Gratuit 💎"}
    },

    "de": {
        "menu": "Menü",
        "profile": "Profil",
        "subscription": "Mitgliedschaft",
        "settings": "Einstellungen",
        "language": "Sprache",
        "help": "Über Bot",
        "back": "Zurück",

        "lang_saved": "🇩🇪 Sprache gespeichert!",
        "welcome": "👋 Hallo! Link senden.",
        "enter_url": "📎 Link senden!",
        "free_version": "💎 Kostenlose Version.",
        "help_text": "🤖 Bot kann:\n• Videos downloaden\n• Profil anzeigen\n• Einstellungen",
        "not_understood": "😅 Ich verstehe nicht.",

        "lbl_name": "Name",
        "lbl_subscription": "Mitgliedschaft",
        "lbl_downloaded": "Heruntergeladen",
        "lbl_format": "Format",
        "lbl_video_plus_audio": "Video + Audio",
        "lbl_since": "Seit",
        "yes": "Ja",
        "no": "Nein",

        "subscription_names": {"free": "Kostenlos 💎"}
    },
}


# ============================================================
#                 КЛАВІАТУРИ
# ============================================================

def main_menu(lang):
    t = texts[lang]
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(f"📋 {t['menu']}", f"👤 {t['profile']}")
    kb.add(f"⚙️ {t['settings']}", f"🌍 {t['language']}")
    kb.add(f"💎 {t['subscription']}", f"ℹ️ {t['help']}")
    return kb


def back_menu(lang):
    return types.ReplyKeyboardMarkup(resize_keyboard=True).add(f"⬅️ {texts[lang]['back']}")


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
    kb.add(
        types.InlineKeyboardButton(
            f"{t['lbl_video_plus_audio']}: {vpa_state}",
            callback_data="toggle_vpa",
        )
    )

    return kb


# ============================================================
#            АЛІАСИ КОМАНД (всі мови)
# ============================================================

CMD = {
    "menu": ["меню", "menu"],
    "profile": ["профіль", "проф", "profile"],
    "settings": ["налаш", "настройки", "settings", "setting"],
    "language": ["мова", "язык", "language"],
    "subscription": ["підпис", "подпис", "subscription"],
    "help": ["про бота", "help", "about"],
    "back": ["назад", "back", "⬅️"],
}


def match_cmd(text):
    text = text.lower()
    for cmd, variants in CMD.items():
        for v in variants:
            if v in text:
                return cmd
    return None


# ============================================================
#                 ЗАВАНТАЖЕННЯ ВІДЕО (ВИПРАВЛЕНО)
# ============================================================

def download_and_send(url, chat_id, user, lang):
    fmt = user["format"]

    # --------------------------
    #    АУДІО ТІЛЬКИ (MP3)
    # --------------------------
    if fmt == "mp3":
        audio_template = os.path.join(DOWNLOAD_DIR, f"{chat_id}_audio.%(ext)s")

        subprocess.run([
            "yt-dlp",
            "-o", audio_template,
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            url
        ], check=True)

        audio_files = glob.glob(os.path.join(DOWNLOAD_DIR, f"{chat_id}_audio.*"))
        if audio_files:
            with open(audio_files[0], "rb") as f:
                bot.send_audio(chat_id, f)

        return True

    # --------------------------
    #         ВІДЕО
    # --------------------------

    video_template = os.path.join(DOWNLOAD_DIR, f"{chat_id}_video.%(ext)s")

    # Головна правильна команда для ВСІХ сайтів:
    subprocess.run([
        "yt-dlp",
        "-o", video_template,
        "-f", "bestvideo*+bestaudio/best",
        "--merge-output-format", "mp4",
        url
    ], check=True)

    # Отримуємо відео
    video_files = glob.glob(os.path.join(DOWNLOAD_DIR, f"{chat_id}_video.*"))
    if video_files:
        with open(video_files[0], "rb") as f:
            bot.send_video(chat_id, f)

    # --------------------------
    #    ВІДЕО + ОКРЕМО АУДІО
    # --------------------------

    if user["video_plus_audio"]:
        audio_template = os.path.join(DOWNLOAD_DIR, f"{chat_id}_audio.%(ext)s")

        subprocess.run([
            "yt-dlp",
            "-o", audio_template,
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            url
        ], check=True)

        audio_files = glob.glob(os.path.join(DOWNLOAD_DIR, f"{chat_id}_audio.*"))
        if audio_files:
            with open(audio_files[0], "rb") as f:
                bot.send_audio(chat_id, f)

    return True



# ============================================================
#                      CALLBACK
# ============================================================

@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    user = get_user(c.from_user)
    lang = user["language"]

    if c.data.startswith("format_"):
        fmt = c.data.replace("format_", "")
        user["format"] = fmt
        user["audio_only"] = (fmt == "mp3")
        save_users(users)
        bot.answer_callback_query(c.id, "✔ Збережено!")
        bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=settings_keyboard(user))
        return

    if c.data == "toggle_vpa":
        user["video_plus_audio"] = not user["video_plus_audio"]
        save_users(users)
        bot.answer_callback_query(c.id, "✔ Збережено!")
        bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=settings_keyboard(user))
        return


# ============================================================
#                  ХЕНДЛЕРИ
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
    txt = (m.text or "").lower()

    if txt.startswith("http"):
        bot.send_message(m.chat.id, "⏳ Завантаження…")
        try:
            download_and_send(m.text, m.chat.id, u, lang)
            u["videos_downloaded"] += 1
            save_users(users)
        except:
            bot.send_message(m.chat.id, "❌ Помилка завантаження.")
        return

    cmd = match_cmd(txt)

    if cmd == "menu":
        bot.send_message(m.chat.id, t["enter_url"], reply_markup=main_menu(lang))
        return

    if cmd == "profile":
        msg = (
            f"👤 {t['profile']}\n\n"
            f"🆔 `{m.from_user.id}`\n"
            f"👋 {t['lbl_name']}: {u['name']}\n"
            f"🎥 {t['lbl_downloaded']}: {u['videos_downloaded']}\n"
            f"🎞️ {t['lbl_format']}: {u['format'].upper()}\n"
            f"🎬 {t['lbl_video_plus_audio']}: {t['yes'] if u['video_plus_audio'] else t['no']}\n"
            f"📅 {t['lbl_since']}: {u['joined']}\n"
        )
        bot.send_message(m.chat.id, msg, parse_mode="Markdown", reply_markup=back_menu(lang))
        return

    if cmd == "language":
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk"))
        kb.add(types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"))
        kb.add(types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"))
        kb.add(types.InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr"))
        kb.add(types.InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de"))
        bot.send_message(m.chat.id, "🌍 Обери мову:", reply_markup=kb)
        return

    if cmd == "settings":
        bot.send_message(m.chat.id, f"⚙️ {t['settings']}:", reply_markup=settings_keyboard(u))
        return

    if cmd == "subscription":
        bot.send_message(m.chat.id, t["free_version"], reply_markup=back_menu(lang))
        return

    if cmd == "help":
        bot.send_message(m.chat.id, t["help_text"], reply_markup=back_menu(lang))
        return

    if cmd == "back":
        bot.send_message(m.chat.id, t["enter_url"], reply_markup=main_menu(lang))
        return

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
#               ЗАПУСК FLASK + ВСТАНОВЛЕННЯ WEBHOOK
# ============================================================

if __name__ == "__main__":
    print("🚀 Запуск Flask + Webhook")

    bot.delete_webhook()
    bot.set_webhook(url=WEBHOOK_URL)

    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))





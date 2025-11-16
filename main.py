import os
import json
import glob
import subprocess
from datetime import datetime
from telebot import TeleBot, types
from flask import Flask, request

# ============================================================
#                       КОНФІГУРАЦІЯ
# ============================================================

TOKEN = os.getenv("TOKEN") or os.getenv("TELEGRAM_TOKEN", "")
if not TOKEN or ":" not in TOKEN:
    raise ValueError("❌ TOKEN не встановлено або неправильний!")

WEBHOOK_HOST = "https://dowlanderbot-2.onrender.com"
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = WEBHOOK_HOST + WEBHOOK_PATH

bot = TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

USER_FILE = "users.json"
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ============================================================
#                   ЗБЕРЕЖЕННЯ КОРИСТУВАЧІВ
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
            "include_description": True,
            "video_plus_audio": True
        }
        save_users(users)
    return users[uid]

# ============================================================
#                          ПЕРЕКЛАДИ
# ============================================================

texts = {
    "uk": {
        "menu":"Меню","profile":"Профіль","subscription":"Підписка","settings":"Налаштування","language":"Мова","help":"Про бота","back":"Назад",
        "lang_saved":"✅ Мову збережено! 🇺🇦",
        "welcome":"👋 Привіт! Надішли посилання на відео (YouTube, TikTok, Instagram...)",
        "enter_url":"📎 Надішли посилання на відео!",
        "free_version":"💎 Безкоштовна версія. Premium скоро ✨",
        "help_text":"🤖 Бот уміє:\n• Завантажувати відео\n• Показувати профіль\n• Має налаштування",
        "not_understood":"😅 Не розумію, обери кнопку.",

        "lbl_name":"Ім’я","lbl_subscription":"Підписка","lbl_downloaded":"Завантажено",
        "lbl_format":"Формат","lbl_only_audio":"Тільки звук",
        "lbl_description":"Опис відео","lbl_video_plus_audio":"Відео + Аудіо","lbl_since":"З",
        "yes":"Так","no":"Ні",

        "subscription_names":{"free":"Безкоштовна 💎"}
    },

    "en": {
        "menu":"Menu","profile":"Profile","subscription":"Subscription","settings":"Settings","language":"Language","help":"About bot","back":"Back",
        "lang_saved":"✅ Language saved! 🇬🇧",
        "welcome":"👋 Hello! Send me a video link.",
        "enter_url":"📎 Send a video link!",
        "free_version":"💎 Free version.",
        "help_text":"🤖 Bot can:\n• Download videos\n• Profile\n• Settings",
        "not_understood":"😅 I don't understand.",

        "lbl_name":"Name","lbl_subscription":"Subscription","lbl_downloaded":"Downloaded",
        "lbl_format":"Format","lbl_only_audio":"Audio only",
        "lbl_description":"Description","lbl_video_plus_audio":"Video + Audio","lbl_since":"Since",
        "yes":"Yes","no":"No",

        "subscription_names":{"free":"Free 💎"}
    },

    "ru": {
        "menu":"Меню","profile":"Профиль","subscription":"Подписка","settings":"Настройки","language":"Язык","help":"О боте","back":"Назад",
        "lang_saved":"✅ Язык сохранён! 🇷🇺",
        "welcome":"👋 Пришли ссылку на видео.",
        "enter_url":"📎 Пришли ссылку!",
        "free_version":"💎 Бесплатная версия.",
        "help_text":"🤖 Бот умеет:\n• Скачать видео\n• Профиль\n• Настройки",
        "not_understood":"😅 Не понимаю.",

        "lbl_name":"Имя","lbl_subscription":"Подписка","lbl_downloaded":"Скачано",
        "lbl_format":"Формат","lbl_only_audio":"Аудио",
        "lbl_description":"Описание","lbl_video_plus_audio":"Видео + Аудио","lbl_since":"С",
        "yes":"Да","no":"Нет",

        "subscription_names":{"free":"Бесплатная 💎"}
    },

    "fr": {
        "menu":"Menu","profile":"Profil","subscription":"Abonnement","settings":"Paramètres","language":"Langue","help":"À propos","back":"Retour",
        "lang_saved":"✅ Langue enregistrée! 🇫🇷",
        "welcome":"👋 Envoie un lien vidéo.",
        "enter_url":"📎 Envoie un lien!",
        "free_version":"💎 Version gratuite.",
        "help_text":"🤖 Le bot peut:\n• Télécharger des vidéos\n• Profil\n• Paramètres",
        "not_understood":"😅 Je ne comprends pas.",

        "lbl_name":"Nom","lbl_subscription":"Abonnement","lbl_downloaded":"Téléchargé",
        "lbl_format":"Format","lbl_only_audio":"Audio","lbl_description":"Description",
        "lbl_video_plus_audio":"Vidéo + Audio","lbl_since":"Depuis",
        "yes":"Oui","no":"Non",

        "subscription_names":{"free":"Gratuit 💎"}
    },

    "de": {
        "menu":"Menü","profile":"Profil","subscription":"Abo","settings":"Einstellungen","language":"Sprache","help":"Über Bot","back":"Zurück",
        "lang_saved":"✅ Sprache gespeichert! 🇩🇪",
        "welcome":"👋 Sende einen Videolink.",
        "enter_url":"📎 Sende Videolink!",
        "free_version":"💎 Kostenlose Version.",
        "help_text":"🤖 Bot kann:\n• Videos laden\n• Profil\n• Einstellungen",
        "not_understood":"😅 Ich verstehe nicht.",

        "lbl_name":"Name","lbl_subscription":"Abo","lbl_downloaded":"Geladen",
        "lbl_format":"Format","lbl_only_audio":"Nur Audio","lbl_description":"Beschreibung",
        "lbl_video_plus_audio":"Video + Audio","lbl_since":"Seit",
        "yes":"Ja","no":"Nein",

        "subscription_names":{"free":"Kostenlos 💎"}
    }
}

# ============================================================
#                           МЕНЮ
# ============================================================

def main_menu(lang):
    t = texts[lang]
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        f"📋 {t['menu']}", f"👤 {t['profile']}",
        f"⚙️ {t['settings']}", f"💎 {t['subscription']}",
        f"🌍 {t['language']}", f"ℹ️ {t['help']}"
    )
    return kb

def back_menu(lang):
    t = texts[lang]
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(f"⬅️ {t['back']}")
    return kb

def ask_language(cid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    langs = [
        ("🇺🇦 Українська","uk"),
        ("🇬🇧 English","en"),
        ("🇷🇺 Русский","ru"),
        ("🇫🇷 Français","fr"),
        ("🇩🇪 Deutsch","de")
    ]
    for name, code in langs:
        kb.add(types.InlineKeyboardButton(name, callback_data=f"lang_{code}"))
    bot.send_message(cid, "🌍 Вибери мову:", reply_markup=kb)

# ============================================================
#                  НАЛАШТУВАННЯ
# ============================================================

def show_settings(chat_id, user, lang):
    t = texts[lang]
    kb = types.InlineKeyboardMarkup(row_width=2)

    kb.add(
        types.InlineKeyboardButton("🎞 MP4", callback_data="set_format_mp4"),
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
#                      CALLBACK HANDLER
# ============================================================

@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    user = get_user(c.from_user)
    lang = user["language"]
    t = texts[lang]

    if c.data.startswith("lang_"):
        user["language"] = c.data.split("_")[1]
        save_users(users)
        bot.send_message(c.message.chat.id, t["lang_saved"], reply_markup=main_menu(user["language"]))
        return

    if c.data.startswith("set_format_"):
        fmt = c.data.split("_")[2]
        user["format"] = fmt
        user["audio_only"] = (fmt == "mp3")
        save_users(users)
        show_settings(c.message.chat.id, user, lang)
        return

    if c.data == "toggle_desc":
        user["include_description"] = not user["include_description"]
        save_users(users)
        show_settings(c.message.chat.id, user, lang)
        return

    if c.data == "toggle_vpa":
        user["video_plus_audio"] = not user["video_plus_audio"]
        save_users(users)
        show_settings(c.message.chat.id, user, lang)
        return

    if c.data == "back_to_menu":
        bot.send_message(c.message.chat.id, t["menu"], reply_markup=main_menu(lang))
        return

# ============================================================
#                   ЗАВАНТАЖЕННЯ ВІДЕО
# ============================================================

def build_yt_dlp_cmd(url, fmt, audio_only):
    cmd = ["yt-dlp"]
    if audio_only or fmt == "mp3":
        cmd += ["-x", "--audio-format", "mp3"]
    elif fmt == "webm":
        cmd += ["-S", "ext:webm", "-f", "bv*+ba/b"]
    else:
        cmd += ["-S", "ext:mp4:m4a", "-f", "bv*+ba/b"]
    cmd.append(url)
    return cmd

def download_and_send(url, chat_id, lang, user):
    t = texts[lang]
    fmt = user["format"]
    include_desc = user["include_description"]
    vpa = user["video_plus_audio"]

    video_pattern = os.path.join(DOWNLOAD_DIR, f"{chat_id}_video.%(ext)s")
    cmd = build_yt_dlp_cmd(url, fmt, False)
    cmd.insert(-1, "-o")
    cmd.insert(-1, video_pattern)

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        bot.send_message(chat_id, "❌ Помилка скачування відео.")
        return False

    video_files = glob.glob(os.path.join(DOWNLOAD_DIR, f"{chat_id}_video.*"))
    if not video_files:
        bot.send_message(chat_id, "❌ Відео не знайдено після завантаження.")
        return False

    video_file = sorted(video_files, key=os.path.getmtime, reverse=True)[0]

    caption = None
    if include_desc:
        try:
            meta = subprocess.check_output(
                ["yt-dlp", "--get-title", "--get-description", url]
            ).decode().splitlines()

            title = meta[0][:200]
            descr = "\n".join(meta[1:])[:900]
            caption = f"{title}\n\n{descr}".strip()
        except:
            pass

    audio_file = None
    if vpa:
        audio_out = os.path.join(DOWNLOAD_DIR, f"{chat_id}_audio.mp3")
        try:
            subprocess.run(
                ["yt-dlp", "-x", "--audio-format", "mp3", "-o", audio_out, url],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            audio_file = audio_out
        except:
            audio_file = None

    try:
        bot.send_video(chat_id, open(video_file, "rb"), caption=caption)
        if audio_file:
            bot.send_audio(chat_id, open(audio_file, "rb"), caption=caption)
    except Exception as e:
        bot.send_message(chat_id, f"❌ Не вдалося надіслати файл.\n{e}")
        return False

    try:
        os.remove(video_file)
        if audio_file:
            os.remove(audio_file)
    except:
        pass

    return True

# ============================================================
#                   ОБРОБНИК ПОВІДОМЛЕНЬ
# ============================================================

@bot.message_handler(commands=["start"])
def start(message):
    u = get_user(message.from_user)
    lang = u["language"]
    bot.send_message(message.chat.id, texts[lang]["welcome"], reply_markup=main_menu(lang))

@bot.message_handler(func=lambda m: True)
def handler(m):
    u = get_user(m.from_user)
    lang = u["language"]
    t = texts[lang]
    text = (m.text or "").lower()

    if text.startswith("http://") or text.startswith("https://"):
        tmp = bot.send_message(m.chat.id, "⏳ Завантаження...")
        ok = download_and_send(m.text.strip(), m.chat.id, lang, u)
        try:
            bot.delete_message(m.chat.id, tmp.message_id)
        except:
            pass
        if ok:
            u["videos_downloaded"] += 1
            save_users(users)
        return

    if "меню" in text or "menu" in text:
        bot.send_message(m.chat.id, t["enter_url"], reply_markup=main_menu(lang))
        return

    if "проф" in text or "profile" in text:
        sub_name = t["subscription_names"]["free"]
        msg = (
            f"👤 **{t['profile']}**\n\n"
            f"🆔 `{m.from_user.id}`\n"
            f"👋 {t['lbl_name']}: {u['name']}\n"
            f"💎 {t['lbl_subscription']}: {sub_name}\n"
            f"🎥 {t['lbl_downloaded']}: {u['videos_downloaded']}\n"
            f"🎞 {t['lbl_format']}: {u['format'].upper()}\n"
            f"📝 {t['lbl_description']}: {t['yes'] if u['include_description'] else t['no']}\n"
            f"🎬 {t['lbl_video_plus_audio']}: {t['yes'] if u['video_plus_audio'] else t['no']}\n"
            f"📅 {t['lbl_since']}: {u['joined']}"
        )

        bot.send_message(m.chat.id, msg, parse_mode="Markdown", reply_markup=back_menu(lang))
        return

    if "налаш" in text or "settings" in text:
        show_settings(m.chat.id, u, lang)
        return

    if "мова" in text or "language" in text:
        ask_language(m.chat.id)
        return

    if "підпис" in text or "subscription" in text:
        bot.send_message(m.chat.id, t["free_version"], reply_markup=back_menu(lang))
        return

    if "help" in text or "про" in text:
        bot.send_message(m.chat.id, t["help_text"], reply_markup=back_menu(lang))
        return

    if "назад" in text or "back" in text:
        bot.send_message(m.chat.id, t["menu"], reply_markup=main_menu(lang))
        return

    bot.send_message(m.chat.id, t["not_understood"], reply_markup=main_menu(lang))

# ============================================================
#                     WEBHOOK + FLASK
# ============================================================

@app.route("/", methods=["GET"])
def home():
    return "Bot is running via webhook! 🚀"

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook_receiver():
    json_data = request.get_data().decode("utf-8")
    update = bot.types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return "", 200

# ============================================================
#                       ЗАПУСК WEBHOOK
# ============================================================

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)

    print("=================================")
    print("   ✅ Webhook встановлено!")
    print("   URL:", WEBHOOK_URL)
    print("=================================")

    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

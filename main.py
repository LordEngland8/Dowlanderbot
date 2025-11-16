import os
import json
import glob
import subprocess
from datetime import datetime
from telebot import TeleBot, types
from telebot.types import Update
from flask import Flask, request

# ============================================================
#                       КОНФІГУРАЦІЯ
# ============================================================

TOKEN = os.getenv("TOKEN") or os.getenv("TELEGRAM_TOKEN", "")
if not TOKEN or ":" not in TOKEN:
    raise ValueError("❌ TOKEN не встановлено або неправильний!")

WEBHOOK_HOST = "https://dowlanderbot-2.onrender.com"
WEBHOOK_PATH = "/" + TOKEN
WEBHOOK_URL = WEBHOOK_HOST + WEBHOOK_PATH

bot = TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

USER_FILE = "users.json"
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ============================================================
#                 ЗБЕРЕЖЕННЯ КОРИСТУВАЧІВ
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
#                       ПЕРЕКЛАДИ
# ============================================================

texts = {
    "uk": {"menu":"Меню","profile":"Профіль","subscription":"Підписка","settings":"Налаштування","language":"Мова","help":"Про бота","back":"Назад",
           "lang_saved":"✅ Мову збережено! 🇺🇦","welcome":"👋 Привіт! Надішли посилання на відео (YouTube, TikTok...)",
           "enter_url":"📎 Надішли посилання!","free_version":"💎 Безкоштовна версія",
           "help_text":"🤖 Функції бота:\n• Завантаження відео\n• Профіль\n• Налаштування",
           "not_understood":"😅 Не розумію.","lbl_name":"Ім’я","lbl_subscription":"Підписка","lbl_downloaded":"Завантажено",
           "lbl_format":"Формат","lbl_only_audio":"Тільки аудіо","lbl_description":"Опис","lbl_video_plus_audio":"Відео+Аудіо","lbl_since":"З",
           "yes":"Так","no":"Ні","subscription_names":{"free":"Безкоштовна","premium":"Преміум"}},

    "en": {"menu":"Menu","profile":"Profile","subscription":"Subscription","settings":"Settings","language":"Language","help":"About",
           "back":"Back","lang_saved":"✅ Language saved! 🇬🇧","welcome":"👋 Hello! Send a video link.",
           "enter_url":"📎 Send a link!","free_version":"💎 Free version",
           "help_text":"🤖 Bot can:\n• Download videos\n• Show profile\n• Settings",
           "not_understood":"😅 I don't understand.","lbl_name":"Name","lbl_subscription":"Subscription","lbl_downloaded":"Downloaded",
           "lbl_format":"Format","lbl_only_audio":"Audio only","lbl_description":"Description","lbl_video_plus_audio":"Video+Audio","lbl_since":"Since",
           "yes":"Yes","no":"No","subscription_names":{"free":"Free","premium":"Premium"}},

    "ru": {"menu":"Меню","profile":"Профиль","subscription":"Подписка","settings":"Настройки","language":"Язык","help":"О боте",
           "back":"Назад","lang_saved":"✅ Язык сохранён! 🇷🇺","welcome":"👋 Пришли ссылку.",
           "enter_url":"📎 Пришли ссылку!","free_version":"💎 Бесплатная версия",
           "help_text":"🤖 Бот умеет скачивать видео и показывать профиль.","not_understood":"😅 Не понимаю.",
           "lbl_name":"Имя","lbl_subscription":"Подписка","lbl_downloaded":"Скачано","lbl_format":"Формат",
           "lbl_only_audio":"Только аудио","lbl_description":"Описание","lbl_video_plus_audio":"Видео+Аудио","lbl_since":"С",
           "yes":"Да","no":"Нет","subscription_names":{"free":"Бесплатно","premium":"Премиум"}},

    "fr": {"menu":"Menu","profile":"Profil","subscription":"Abonnement","settings":"Paramètres","language":"Langue","help":"À propos",
           "back":"Retour","lang_saved":"✅ Langue enregistrée! 🇫🇷","welcome":"👋 Envoie un lien vidéo.",
           "enter_url":"📎 Envoie un lien!","free_version":"💎 Version gratuite",
           "help_text":"🤖 Le bot peut télécharger des vidéos.","not_understood":"😅 Je ne comprends pas.",
           "lbl_name":"Nom","lbl_subscription":"Abonnement","lbl_downloaded":"Téléchargé","lbl_format":"Format",
           "lbl_only_audio":"Audio seul","lbl_description":"Description","lbl_video_plus_audio":"Vidéo+Audio","lbl_since":"Depuis",
           "yes":"Oui","no":"Non","subscription_names":{"free":"Gratuit","premium":"Premium"}},

    "de": {"menu":"Menü","profile":"Profil","subscription":"Abo","settings":"Einstellungen","language":"Sprache","help":"Über Bot",
           "back":"Zurück","lang_saved":"✅ Sprache gespeichert! 🇩🇪","welcome":"👋 Sende einen Videolink.",
           "enter_url":"📎 Sende einen Link!","free_version":"💎 Kostenlose Version",
           "help_text":"🤖 Bot kann Videos herunterladen.","not_understood":"😅 Ich verstehe nicht.",
           "lbl_name":"Name","lbl_subscription":"Abo","lbl_downloaded":"Heruntergeladen","lbl_format":"Format",
           "lbl_only_audio":"Nur Audio","lbl_description":"Beschreibung","lbl_video_plus_audio":"Video+Audio","lbl_since":"Seit",
           "yes":"Ja","no":"Nein","subscription_names":{"free":"Kostenlos","premium":"Premium"}}
}

# ============================================================
#                     КЛАВІАТУРИ
# ============================================================

def main_menu(lang):
    t = texts[lang]
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(f"📋 {t['menu']}", f"👤 {t['profile']}")
    kb.add(f"⚙️ {t['settings']}", f"💎 {t['subscription']}")
    kb.add(f"🌍 {t['language']}", f"ℹ️ {t['help']}")
    return kb

def back_menu(lang):
    t = texts[lang]
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(f"⬅️ {t['back']}")
    return kb


# ============================================================
#                     ФУНКЦІЇ ВІДЕО
# ============================================================

def build_cmd(url, fmt, audio_only):
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
    fmt = user["format"]
    include_desc = user["include_description"]
    video_plus_audio = user["video_plus_audio"]

    out_video = os.path.join(DOWNLOAD_DIR, f"{chat_id}_video.%(ext)s")
    cmd = build_cmd(url, fmt, False)
    cmd.insert(-1, "-o")
    cmd.insert(-1, out_video)

    try:
        subprocess.run(cmd, check=True)
    except:
        bot.send_message(chat_id, "❌ Помилка завантаження")
        return

    video_files = glob.glob(os.path.join(DOWNLOAD_DIR, f"{chat_id}_video.*"))
    if not video_files:
        bot.send_message(chat_id, "❌ Відео не знайдено.")
        return

    video_file = video_files[0]

    # Відправка відео
    with open(video_file, "rb") as f:
        bot.send_video(chat_id, f)

    os.remove(video_file)


# ============================================================
#                        /start
# ============================================================

@bot.message_handler(commands=["start"])
def start(message):
    u = get_user(message.from_user)
    lang = u["language"]
    bot.send_message(message.chat.id, texts[lang]["welcome"], reply_markup=main_menu(lang))


# ============================================================
#              ОБРОБКА ВСІХ ПОВІДОМЛЕНЬ
# ============================================================

@bot.message_handler(func=lambda m: True)
def handler(m):
    u = get_user(m.from_user)
    lang = u["language"]
    t = texts[lang]
    text = (m.text or "").lower()

    if text.startswith("http://") or text.startswith("https://"):
        bot.send_message(m.chat.id, "⏳ Завантаження…")
        download_and_send(m.text, m.chat.id, lang, u)
        u["videos_downloaded"] += 1
        save_users(users)
        return

    if text in [t["menu"].lower(), "menu", "меню"]:
        bot.send_message(m.chat.id, t["enter_url"], reply_markup=main_menu(lang))
        return

    if text in [t["help"].lower(), "help"]:
        bot.send_message(m.chat.id, t["help_text"], reply_markup=back_menu(lang))
        return

    if text.startswith(t["language"].lower()):
        kb = types.InlineKeyboardMarkup()
        for flag, code in [("🇺🇦", "uk"), ("🇬🇧", "en"), ("🇷🇺", "ru"), ("🇫🇷", "fr"), ("🇩🇪", "de")]:
            kb.add(types.InlineKeyboardButton(flag, callback_data=f"lang_{code}"))
        bot.send_message(m.chat.id, "🌍 Обери мову:", reply_markup=kb)
        return

    bot.send_message(m.chat.id, t["not_understood"])


# ============================================================
#                        CALLBACK
# ============================================================

@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    user = get_user(c.from_user)
    code = c.data.replace("lang_", "")
    if code in texts:
        user["language"] = code
        save_users(users)
        bot.answer_callback_query(c.id, "OK")
        bot.send_message(c.message.chat.id, texts[code]["lang_saved"], reply_markup=main_menu(code))


# ============================================================
#                       WEBHOOK FLASK
# ============================================================

@app.route("/", methods=["GET"])
def home():
    return "Bot is running!", 200


@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook_receiver():
    json_str = request.get_data(as_text=True)
    update = Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200


# ============================================================
#                        ЗАПУСК
# ============================================================

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)

    print("✅ Webhook встановлено!")
    print("➡", WEBHOOK_URL)

    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

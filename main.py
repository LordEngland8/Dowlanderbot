import os
import json
import glob
import subprocess
from datetime import datetime
from telebot import TeleBot, types
from flask import Flask, request

# ============================================================
#                       КОНФІГ
# ============================================================

TOKEN = os.getenv("TOKEN") or os.getenv("TELEGRAM_TOKEN", "")
if not TOKEN or ":" not in TOKEN:
    raise ValueError("❌ TOKEN не встановлено або невірний!")

WEBHOOK_HOST = "https://dowlanderbot-2.onrender.com"
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = WEBHOOK_HOST + WEBHOOK_PATH

bot = TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

USER_FILE = "users.json"
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ================================================
#         ЗБЕРЕЖЕННЯ КОРИСТУВАЧІВ
# ================================================

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
#                       ТЕКСТИ
# ============================================================

texts = {
    "uk": {"menu":"Меню","profile":"Профіль","subscription":"Підписка","settings":"Налаштування","language":"Мова","help":"Про бота","back":"Назад",
           "lang_saved":"✅ Мову збережено! 🇺🇦","welcome":"👋 Привіт! Надішли мені посилання на відео.",
           "enter_url":"📎 Надішли посилання на відео!","free_version":"💎 Безкоштовна версія.",
           "help_text":"🤖 Бот може:\n• Завантажувати відео з багатьох сайтів\n• Показувати профіль\n• Має налаштування",
           "not_understood":"😅 Я не розумію.",
           "lbl_name":"Ім’я","lbl_subscription":"Підписка","lbl_downloaded":"Завантажено",
           "lbl_format":"Формат","lbl_only_audio":"Тільки аудіо","lbl_description":"Опис відео",
           "lbl_video_plus_audio":"Відео + Аудіо","lbl_since":"З",
           "yes":"Так","no":"Ні","subscription_names":{"free":"Безкоштовна 💎"}},
    "en": {"menu":"Menu","profile":"Profile","subscription":"Subscription","settings":"Settings","language":"Language","help":"Help","back":"Back",
           "lang_saved":"✅ Language saved! 🇬🇧","welcome":"👋 Send me a video link.",
           "enter_url":"📎 Send a link!","free_version":"💎 Free version.",
           "help_text":"🤖 Bot can download videos, show profile, has settings.",
           "not_understood":"😅 I don't understand.",
           "lbl_name":"Name","lbl_subscription":"Subscription","lbl_downloaded":"Downloaded",
           "lbl_format":"Format","lbl_only_audio":"Audio only","lbl_description":"Video description",
           "lbl_video_plus_audio":"Video + Audio","lbl_since":"Since",
           "yes":"Yes","no":"No","subscription_names":{"free":"Free 💎"}},
    "ru": {"menu":"Меню","profile":"Профиль","subscription":"Подписка","settings":"Настройки","language":"Язык","help":"О боте","back":"Назад",
           "lang_saved":"✅ Язык сохранён! 🇷🇺","welcome":"👋 Пришли ссылку.",
           "enter_url":"📎 Пришли ссылку!","free_version":"💎 Бесплатно.",
           "help_text":"🤖 Может скачивать видео, показывать профиль.",
           "not_understood":"😅 Не понимаю.",
           "lbl_name":"Имя","lbl_subscription":"Подписка","lbl_downloaded":"Скачано",
           "lbl_format":"Формат","lbl_only_audio":"Только аудио","lbl_description":"Описание",
           "lbl_video_plus_audio":"Видео + Аудио","lbl_since":"С",
           "yes":"Да","no":"Нет","subscription_names":{"free":"Бесплатно 💎"}},
    "fr": {"menu":"Menu","profile":"Profil","subscription":"Abonnement","settings":"Paramètres","language":"Langue","help":"Aide","back":"Retour",
           "lang_saved":"✅ Langue sauvegardée! 🇫🇷","welcome":"👋 Envoie un lien vidéo.",
           "enter_url":"📎 Envoie un lien!","free_version":"💎 Version gratuite.",
           "help_text":"🤖 Téléchargement vidéo, profil, paramètres.",
           "not_understood":"😅 Je ne comprends pas.",
           "lbl_name":"Nom","lbl_subscription":"Abonnement","lbl_downloaded":"Téléchargé",
           "lbl_format":"Format","lbl_only_audio":"Audio seul","lbl_description":"Description",
           "lbl_video_plus_audio":"Vidéo + Audio","lbl_since":"Depuis",
           "yes":"Oui","no":"Non","subscription_names":{"free":"Gratuit 💎"}},
    "de": {"menu":"Menü","profile":"Profil","subscription":"Abo","settings":"Einstellungen","language":"Sprache","help":"Hilfe","back":"Zurück",
           "lang_saved":"✅ Sprache gespeichert! 🇩🇪","welcome":"👋 Schicke mir einen Videolink.",
           "enter_url":"📎 Link senden!","free_version":"💎 Kostenlos.",
           "help_text":"🤖 Videos herunterladen, Profil anzeigen, Einstellungen.",
           "not_understood":"😅 Ich verstehe nicht.",
           "lbl_name":"Name","lbl_subscription":"Abo","lbl_downloaded":"Heruntergeladen",
           "lbl_format":"Format","lbl_only_audio":"Nur Audio","lbl_description":"Beschreibung",
           "lbl_video_plus_audio":"Video + Audio","lbl_since":"Seit",
           "yes":"Ja","no":"Nein","subscription_names":{"free":"Kostenlos 💎"}}
}

# ============================================================
#                 КЛАВІАТУРИ
# ============================================================

def main_menu(lang):
    t = texts[lang]
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(
        types.KeyboardButton(f"📋 {t['menu']}"),
        types.KeyboardButton(f"👤 {t['profile']}"),
        types.KeyboardButton(f"⚙️ {t['settings']}"),
        types.KeyboardButton(f"💎 {t['subscription']}"),
        types.KeyboardButton(f"🌍 {t['language']}"),
        types.KeyboardButton(f"ℹ️ {t['help']}")
    )
    return kb

def back_menu(lang):
    t = texts[lang]
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton(f"⬅️ {t['back']}"))
    return kb

# ============================================================
#                 АНТИ-СПАМ + ГРУПИ
# ============================================================

def is_bot_message(m):
    try:
        return m.from_user.id == bot.get_me().id
    except:
        return False

def ignore_group_message(m):
    if m.chat.type not in ["group", "supergroup"]:
        return False
    try:
        username = bot.get_me().username.lower()
        return f"@{username}" not in m.text.lower() and not m.text.lower().startswith(("http://","https://"))
    except:
        return True

# ============================================================
#                       ЗАВАНТАЖЕННЯ
# ============================================================

def build_cmd(url, fmt):
    if fmt == "mp3":
        return ["yt-dlp", "-x", "--audio-format", "mp3", url]
    elif fmt == "webm":
        return ["yt-dlp", "-S", "ext:webm", "-f", "bv*+ba/b", url]
    return ["yt-dlp", "-S", "ext:mp4:m4a", "-f", "bv*+ba/b", url]

def download_and_send(url, chat_id, lang, user):
    t = texts[lang]
    fmt = user["format"]

    video_path = f"{DOWNLOAD_DIR}/{chat_id}_video.%(ext)s"
    cmd = build_cmd(url, fmt)
    cmd.insert(-1, "-o")
    cmd.insert(-1, video_path)

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        bot.send_message(chat_id, "❌ Помилка завантаження.")
        return

    files = glob.glob(f"{DOWNLOAD_DIR}/{chat_id}_video.*")
    if not files:
        bot.send_message(chat_id, "❌ Відео не знайдено.")
        return

    video_file = files[0]

    try:
        with open(video_file, "rb") as f:
            bot.send_video(chat_id, f)
    except:
        bot.send_message(chat_id, "❌ Не можу відправити файл.")
    finally:
        try: os.remove(video_file)
        except: pass

# ============================================================
#                       ОБРОБНИКИ
# ============================================================

@bot.message_handler(commands=["start"])
def start(m):
    u = get_user(m.from_user)
    lang = u["language"]
    bot.send_message(m.chat.id, texts[lang]["welcome"], reply_markup=main_menu(lang))


@bot.message_handler(func=lambda m: True)
def message_handler(m):

    if is_bot_message(m):
        return

    if ignore_group_message(m):
        return

    u = get_user(m.from_user)
    lang = u["language"]
    t = texts[lang]

    txt = (m.text or "").lower()

    # Посилання
    if txt.startswith(("http://","https://")):
        msg = bot.send_message(m.chat.id, "⏳ Завантаження…")
        download_and_send(m.text, m.chat.id, lang, u)
        bot.delete_message(m.chat.id, msg.message_id)
        return

    # Меню
    if t["menu"].lower() in txt or "menu" in txt:
        bot.send_message(m.chat.id, t["enter_url"], reply_markup=main_menu(lang))
        return

    if t["profile"].lower() in txt:
        bot.send_message(m.chat.id, "👤 Профіль недоступний у групах." if m.chat.type!="private" else
                         f"{t['lbl_name']}: {u['name']}\n"
                         f"{t['lbl_subscription']}: {t['subscription_names'][u['subscription']]}\n"
                         f"{t['lbl_downloaded']}: {u['videos_downloaded']}",
                         reply_markup=back_menu(lang))
        return

    if t["settings"].lower() in txt:
        bot.send_message(m.chat.id, "⚙️ Налаштування недоступні у групах." if m.chat.type!="private" else
                         "⚙️ Скоро…",
                         reply_markup=back_menu(lang))
        return

    if t["language"].lower() in txt:
        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk"),
            types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
            types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
            types.InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr"),
            types.InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de")
        )
        bot.send_message(m.chat.id, "🌍 Виберіть мову:", reply_markup=kb)
        return

    if t["help"].lower() in txt:
        bot.send_message(m.chat.id, t["help_text"], reply_markup=back_menu(lang))
        return

    bot.send_message(m.chat.id, t["not_understood"], reply_markup=main_menu(lang))

# ============================================================
#                       CALLBACK
# ============================================================

@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    if c.data.startswith("lang_"):
        lang = c.data.split("_")[1]
        u = get_user(c.from_user)
        u["language"] = lang
        save_users(users)
        bot.answer_callback_query(c.id, texts[lang]["lang_saved"])
        bot.edit_message_text(texts[lang]["lang_saved"], c.message.chat.id, c.message.message_id)

# ============================================================
#                     FLASK WEBHOOK
# ============================================================

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook_receiver():
    update = types.Update.de_json(request.get_json())
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def home():
    return "Bot is running!", 200

# ============================================================
#                       ЗАПУСК
# ============================================================

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

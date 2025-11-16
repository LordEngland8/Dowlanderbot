import os
import json
import glob
import subprocess
from datetime import datetime
from telebot import TeleBot, types
from flask import Flask, request, abort
import threading

# ============================================================
#                      КОНФІГ
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
#                      КОРИСТУВАЧІ
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

    if users[uid]["language"] not in ["uk", "en", "ru", "fr", "de"]:
        users[uid]["language"] = "uk"
        save_users(users)

    return users[uid]

# ============================================================
#                      ПЕРЕКЛАД
# ============================================================

texts = {
    "uk": {"menu":"Меню","profile":"Профіль","subscription":"Підписка","settings":"Налаштування","language":"Мова","help":"Про бота","back":"Назад",
           "lang_saved":"✅ Мову збережено! 🇺🇦","welcome":"👋 Привіт! Надішли посилання на відео.",
           "enter_url":"📎 Надішли посилання на відео!","free_version":"💎 Безкоштовна версія",
           "help_text":"🤖 Бот уміє:\n• Завантажувати відео\n• Показувати профіль\n• Має налаштування",
           "not_understood":"😅 Не розумію, обери кнопку нижче.",
           "lbl_name":"Ім’я","lbl_subscription":"Підписка","lbl_downloaded":"Завантажено","lbl_format":"Формат",
           "lbl_only_audio":"Тільки звук","lbl_description":"Опис відео","lbl_video_plus_audio":"Відео + Аудіо","lbl_since":"З",
           "yes":"Так","no":"Ні","subscription_names":{"free":"Безкоштовна","premium":"Преміум"}},
    "en": {"menu":"Menu","profile":"Profile","subscription":"Subscription","settings":"Settings","language":"Language","help":"About bot","back":"Back",
           "lang_saved":"✅ Language saved!","welcome":"👋 Hello! Send a video link.",
           "enter_url":"📎 Send a video link!","free_version":"💎 Free version",
           "help_text":"🤖 The bot can:\n• Download videos\n• Display profile\n• Settings available",
           "not_understood":"😅 I don't understand.",
           "lbl_name":"Name","lbl_subscription":"Subscription","lbl_downloaded":"Downloaded","lbl_format":"Format",
           "lbl_only_audio":"Audio only","lbl_description":"Description","lbl_video_plus_audio":"Video + Audio","lbl_since":"Since",
           "yes":"Yes","no":"No","subscription_names":{"free":"Free","premium":"Premium"}},
    "ru": {"menu":"Меню","profile":"Профиль","subscription":"Подписка","settings":"Настройки","language":"Язык","help":"О боте","back":"Назад",
           "lang_saved":"✅ Язык сохранён!","welcome":"👋 Привет! Пришли ссылку на видео.",
           "enter_url":"📎 Пришли ссылку на видео!","free_version":"💎 Бесплатная версия",
           "help_text":"🤖 Бот умеет:\n• Скачать видео\n• Показать профиль\n• Настройки есть",
           "not_understood":"😅 Не понимаю.",
           "lbl_name":"Имя","lbl_subscription":"Подписка","lbl_downloaded":"Скачано","lbl_format":"Формат",
           "lbl_only_audio":"Только аудио","lbl_description":"Описание","lbl_video_plus_audio":"Видео + Аудио","lbl_since":"С",
           "yes":"Да","no":"Нет","subscription_names":{"free":"Бесплатная","premium":"Премиум"}},
    "fr": {"menu":"Menu","profile":"Profil","subscription":"Abonnement","settings":"Paramètres","language":"Langue","help":"À propos","back":"Retour",
           "lang_saved":"✅ Langue enregistrée!","welcome":"👋 Bonjour! Envoie un lien vidéo.",
           "enter_url":"📎 Envoie un lien vidéo!","free_version":"💎 Version gratuite",
           "help_text":"🤖 Le bot peut:\n• Télécharger des vidéos\n• Profil\n• Paramètres",
           "not_understood":"😅 Je ne comprends pas.",
           "lbl_name":"Nom","lbl_subscription":"Abonnement","lbl_downloaded":"Téléchargé","lbl_format":"Format",
           "lbl_only_audio":"Audio seul","lbl_description":"Description","lbl_video_plus_audio":"Vidéo + Audio","lbl_since":"Depuis",
           "yes":"Oui","no":"Non","subscription_names":{"free":"Gratuit","premium":"Premium"}},
    "de": {"menu":"Menü","profile":"Profil","subscription":"Abo","settings":"Einstellungen","language":"Sprache","help":"Über","back":"Zurück",
           "lang_saved":"✅ Sprache gespeichert!","welcome":"👋 Hallo! Sende einen Videolink.",
           "enter_url":"📎 Sende einen Videolink!","free_version":"💎 Kostenlose Version",
           "help_text":"🤖 Bot kann:\n• Videos laden\n• Profil zeigen\n• Einstellungen",
           "not_understood":"😅 Ich verstehe nicht.",
           "lbl_name":"Name","lbl_subscription":"Abo","lbl_downloaded":"Geladen","lbl_format":"Format",
           "lbl_only_audio":"Nur Audio","lbl_description":"Beschreibung","lbl_video_plus_audio":"Video + Audio","lbl_since":"Seit",
           "yes":"Ja","no":"Nein","subscription_names":{"free":"Kostenlos","premium":"Premium"}}
}

# ============================================================
#                    КЛАВІАТУРИ
# ============================================================

def main_menu(lang):
    t = texts[lang]
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

def back_menu(lang):
    t = texts[lang]
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton(f"⬅️ {t['back']}"))
    return kb

def ask_language(cid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    langs = [("🇺🇦 Українська","uk"),("🇬🇧 English","en"),("🇷🇺 Русский","ru"),
             ("🇫🇷 Français","fr"),("🇩🇪 Deutsch","de")]
    for name, code in langs:
        kb.add(types.InlineKeyboardButton(name, callback_data=f"lang_{code}"))
    bot.send_message(cid, "🌍 Вибери мову:", reply_markup=kb)

# ============================================================
#                 ФУНКЦІЯ ЗАВАНТАЖЕННЯ ВІДЕО
# ============================================================

def download_and_send(url: str, chat_id: int, lang: str, user: dict):
    t = texts.get(lang, texts["uk"])

    fmt = user.get("format", "mp4").lower()
    video_plus_audio = bool(user.get("video_plus_audio", True))
    include_desc = bool(user.get("include_description", True))

    wait_msg = bot.send_message(chat_id, "⏳ Завантаження… зачекай.")
    wait_msg_id = wait_msg.message_id

    # --- команда для відео ---
    def build_cmd(fmt: str):
        if fmt == "mp3":
            return ["yt-dlp", "-x", "--audio-format", "mp3"]
        elif fmt == "webm":
            return ["yt-dlp", "-S", "ext:webm", "-f", "bv*+ba/b"]
        else:
            return ["yt-dlp", "-S", "ext:mp4:m4a", "-f", "bv*+ba/b"]

    cmd = build_cmd(fmt)

    outtmpl_video = os.path.join(DOWNLOAD_DIR, f"{chat_id}_video.%(ext)s")
    cmd += ["-o", outtmpl_video, url]

    # --- качаємо відео ---
    try:
        subprocess.run(cmd, check=True)
    except Exception as e:
        bot.edit_message_text(
            f"❌ Помилка при завантаженні:\n`{e}`",
            chat_id,
            wait_msg_id,
            parse_mode="Markdown"
        )
        return

    # --- шукаємо відео ---
    video_candidates = glob.glob(os.path.join(DOWNLOAD_DIR, f"{chat_id}_video.*"))
    if not video_candidates:
        bot.edit_message_text("❌ Відео не знайдено.", chat_id, wait_msg_id)
        return

    video_file = sorted(video_candidates, key=os.path.getmtime)[-1]

    # --- окреме аудіо ---
    audio_file = None
    if video_plus_audio:
        audio_path = os.path.join(DOWNLOAD_DIR, f"{chat_id}_audio.mp3")
        cmd_audio = ["yt-dlp", "-x", "--audio-format", "mp3", "-o", audio_path, url]

        try:
            subprocess.run(cmd_audio, check=True)
            audio_file = audio_path
        except Exception:
            audio_file = None

    # --- метадані ---
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
        except:
            caption = None

    # --- надсилання відео ---
    try:
        with open(video_file, "rb") as f:
            bot.send_video(chat_id, f, caption=caption)
    except:
        bot.edit_message_text(
            "❌ Не вдалося надіслати відео (можливо, файл великий).",
            chat_id,
            wait_msg_id
        )
        return

    # --- надсилання аудіо ---
    if audio_file:
        try:
            with open(audio_file, "rb") as f:
                bot.send_audio(chat_id, f, caption=caption)
        except:
            pass

    # --- очищення ---
    try:
        os.remove(video_file)
        if audio_file:
            os.remove(audio_file)
    except:
        pass

    bot.edit_message_text("✅ Готово!", chat_id, wait_msg_id)

# ============================================================
#                        CALLBACK
# ============================================================

@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    user = get_user(c.from_user)
    lang = user["language"]
    t = texts[lang]

    if c.data.startswith("lang_"):
        user["language"] = c.data.split("_")[1]
        save_users(users)
        bot.edit_message_text(texts[user["language"]]["lang_saved"], c.message.chat.id)
        bot.send_message(c.message.chat.id, t["menu"], reply_markup=main_menu(user["language"]))
        return

    if c.data == "set_format_mp4":
        user["format"] = "mp4"
    elif c.data == "set_format_mp3":
        user["format"] = "mp3"
        user["audio_only"] = True
    elif c.data == "set_format_webm":
        user["format"] = "webm"

    if c.data == "toggle_desc":
        user["include_description"] = not user["include_description"]

    if c.data == "toggle_vpa":
        user["video_plus_audio"] = not user["video_plus_audio"]

    save_users(users)

# ============================================================
#                        ОБРОБКА ПОВІДОМЛЕНЬ
# ============================================================

@bot.message_handler(commands=["start"])
def start(message):
    u = get_user(message.from_user)
    lang = u["language"]
    bot.send_message(message.chat.id, texts[lang]["welcome"], reply_markup=main_menu(lang))

@bot.message_handler(func=lambda m: True)
def handle_all(m):
    u = get_user(m.from_user)
    lang = u["language"]
    t = texts[lang]

    # антиспам: ігнор своїх повідомлень
    if m.from_user.id == bot.get_me().id:
        return

    # групи: працює тільки через @username або посилання
    if m.chat.type in ["group", "supergroup"]:
        username = bot.get_me().username.lower()
        if f"@{username}" not in (m.text or "").lower() and not (m.text or "").startswith(("http://", "https://")):
            return

    # якщо це посилання — качаємо
    if (m.text or "").startswith(("http://", "https://")):
        url = m.text.strip()
        threading.Thread(target=download_and_send, args=(url, m.chat.id, lang, u)).start()
        return

    # інші кнопки — тільки у приватному чаті
    if m.chat.type != "private":
        return

    txt = (m.text or "").lower()

    if "меню" in txt or "menu" in txt:
        bot.send_message(m.chat.id, t["enter_url"], reply_markup=main_menu(lang))
        return

    if "проф" in txt or "profil" in txt or "prof" in txt:
        sub_key = u.get("subscription")
        sub_text = t["subscription_names"].get(sub_key, sub_key)

        msg = (
            f"👤 {t['profile']}\n\n"
            f"🆔 `{m.from_user.id}`\n"
            f"👋 {t['lbl_name']}: {u['name']}\n"
            f"💎 {t['lbl_subscription']}: {sub_text}\n"
            f"🎥 {t['lbl_downloaded']}: {u['videos_downloaded']}\n"
            f"🎞️ {t['lbl_format']}: {u['format']}\n"
            f"📝 {t['lbl_description']}: {t['yes'] if u['include_description'] else t['no']}\n"
            f"🎬 {t['lbl_video_plus_audio']}: {t['yes'] if u['video_plus_audio'] else t['no']}\n"
            f"📅 {t['lbl_since']}: {u['joined']}"
        )

        bot.send_message(m.chat.id, msg, parse_mode="Markdown", reply_markup=back_menu(lang))
        return

    if "нал" in txt or "sett" in txt:
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("🎞 MP4", callback_data="set_format_mp4"),
            types.InlineKeyboardButton("🎧 MP3", callback_data="set_format_mp3"),
            types.InlineKeyboardButton("🌐 WEBM", callback_data="set_format_webm")
        )
        kb.add(types.InlineKeyboardButton(
            f"📝 {t['lbl_description']}: {t['yes'] if u['include_description'] else t['no']}",
            callback_data="toggle_desc"
        ))
        kb.add(types.InlineKeyboardButton(
            f"🎬 {t['lbl_video_plus_audio']}: {t['yes'] if u['video_plus_audio'] else t['no']}",
            callback_data="toggle_vpa"
        ))
        bot.send_message(m.chat.id, t["settings"], reply_markup=kb)
        return

    if "мова" in txt or "lang" in txt:
        ask_language(m.chat.id)
        return

    if "підпис" in txt or "sub" in txt:
        sub_key = u.get("subscription")
        sub_text = t["subscription_names"].get(sub_key, sub_key)
        bot.send_message(m.chat.id, sub_text, reply_markup=back_menu(lang))
        return

    if "help" in txt or "про" in txt:
        bot.send_message(m.chat.id, t["help_text"], reply_markup=back_menu(lang))
        return

    if "назад" in txt or "back" in txt:
        bot.send_message(m.chat.id, t["menu"], reply_markup=main_menu(lang))
        return

    bot.send_message(m.chat.id, t["not_understood"], reply_markup=main_menu(lang))

# ============================================================
#                      FLASK + WEBHOOK
# ============================================================

@app.route("/", methods=["GET"])
def index():
    return "Bot is running!"

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook_receiver():
    if request.headers.get("content-type") == "application/json":
        json_data = request.get_data().decode("utf-8")
        update = types.Update.de_json(json_data)
        bot.process_new_updates([update])
        return "OK", 200
    else:
        abort(403)

# ============================================================
#                        ЗАПУСК
# ============================================================

def set_webhook():
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)

if __name__ == "__main__":
    print("✅ Webhook встановлено!")
    set_webhook()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

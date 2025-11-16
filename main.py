import os
import json
import glob
import subprocess
from datetime import datetime
from telebot import TeleBot, types
from flask import Flask
import threading

# ====== КОНФІГ ======
# Читаємо токен з TOKEN (Render) або TELEGRAM_TOKEN (локально)
TOKEN = os.getenv("TOKEN") or os.getenv("TELEGRAM_TOKEN", "")
bot = TeleBot(TOKEN)
USER_FILE = "users.json"
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ====== ЗБЕРЕЖЕННЯ КОРИСТУВАЧІВ ======
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
            "video_plus_audio": True   # прапорець для UX; фактично зливаємо best відео+аудіо
        }
        save_users(users)

    # санітизація мови
    if users[uid]["language"] not in ["uk", "en", "ru", "fr", "de"]:
        users[uid]["language"] = "uk"
        save_users(users)
    return users[uid]

# ====== ПЕРЕКЛАДИ ======
texts = {
    "uk": {"menu":"Меню","profile":"Профіль","subscription":"Підписка","settings":"Налаштування","language":"Мова","help":"Про бота","back":"Назад",
           "lang_saved":"✅ Мову збережено! 🇺🇦","welcome":"👋 Привіт! Надішли посилання на відео (YouTube, TikTok, Instagram, Facebook, Twitter тощо)",
           "enter_url":"📎 Надішли посилання на відео!","free_version":"💎 Безкоштовна версія. Premium скоро ✨",
           "help_text":"🤖 Бот уміє:\n• Завантажувати відео з багатьох сайтів (yt-dlp)\n• Показувати профіль\n• Має гнучкі налаштування",
           "not_understood":"😅 Не розумію, обери кнопку нижче.",
           "lbl_name":"Ім’я","lbl_subscription":"Підписка","lbl_downloaded":"Завантажено","lbl_format":"Формат",
           "lbl_only_audio":"Тільки звук","lbl_description":"Опис відео","lbl_video_plus_audio":"Відео + Аудіо","lbl_since":"З",
           "yes":"✅ Так","no":"❌ Ні","subscription_names":{"free":"Безкоштовна 💎","premium":"Преміум 💠"}},
    "en": {"menu":"Menu","profile":"Profile","subscription":"Subscription","settings":"Settings","language":"Language","help":"About bot","back":"Back",
           "lang_saved":"✅ Language saved! 🇬🇧","welcome":"👋 Hello! Send a link (YouTube, TikTok, Instagram, Facebook, Twitter, etc.)",
           "enter_url":"📎 Send me a video link!","free_version":"💎 Free version. Premium coming soon ✨",
           "help_text":"🤖 The bot can:\n• Download from many sites (yt-dlp)\n• Show profile\n• Has flexible settings",
           "not_understood":"😅 I don't understand, choose a button below.",
           "lbl_name":"Name","lbl_subscription":"Subscription","lbl_downloaded":"Downloaded","lbl_format":"Format",
           "lbl_only_audio":"Audio only","lbl_description":"Video description","lbl_video_plus_audio":"Video + Audio","lbl_since":"Since",
           "yes":"✅ Yes","no":"❌ No","subscription_names":{"free":"Free 💎","premium":"Premium 💠"}},
    "ru": {"menu":"Меню","profile":"Профиль","subscription":"Подписка","settings":"Настройки","language":"Язык","help":"О боте","back":"Назад",
           "lang_saved":"✅ Язык сохранён! 🇷🇺","welcome":"👋 Привет! Пришли ссылку (YouTube, TikTok, Instagram, Facebook, Twitter и т.д.)",
           "enter_url":"📎 Пришли ссылку на видео!","free_version":"💎 Бесплатная версия. Premium скоро ✨",
           "help_text":"🤖 Бот умеет:\n• Скачивать с многих сайтов (yt-dlp)\n• Показывать профиль\n• Имеет гибкие настройки",
           "not_understood":"😅 Не понимаю, выбери кнопку ниже.",
           "lbl_name":"Имя","lbl_subscription":"Подписка","lbl_downloaded":"Скачано","lbl_format":"Формат",
           "lbl_only_audio":"Только аудио","lbl_description":"Описание видео","lbl_video_plus_audio":"Видео + Аудио","lbl_since":"С",
           "yes":"✅ Да","no":"❌ Нет","subscription_names":{"free":"Бесплатная 💎","premium":"Премиум 💠"}},
    "fr": {"menu":"Menu","profile":"Profil","subscription":"Abonnement","settings":"Paramètres","language":"Langue","help":"À propos du bot","back":"Retour",
           "lang_saved":"✅ Langue enregistrée! 🇫🇷","welcome":"👋 Bonjour ! Envoie un lien (YouTube, TikTok, Instagram, etc.)",
           "enter_url":"📎 Envoie un lien vidéo !","free_version":"💎 Version gratuite. Premium bientôt ✨",
           "help_text":"🤖 Le bot peut :\n• Télécharger depuis de nombreux sites (yt-dlp)\n• Afficher le profil\n• Paramètres flexibles",
           "not_understood":"😅 Je ne comprends pas, choisis un bouton.",
           "lbl_name":"Nom","lbl_subscription":"Abonnement","lbl_downloaded":"Téléchargé","lbl_format":"Format",
           "lbl_only_audio":"Audio uniquement","lbl_description":"Description","lbl_video_plus_audio":"Vidéo + Audio","lbl_since":"Depuis",
           "yes":"✅ Oui","no":"❌ Non","subscription_names":{"free":"Gratuit 💎","premium":"Premium 💠"}},
    "de": {"menu":"Menü","profile":"Profil","subscription":"Abonnement","settings":"Einstellungen","language":"Sprache","help":"Über den Bot","back":"Zurück",
           "lang_saved":"✅ Sprache gespeichert! 🇩🇪","welcome":"👋 Hallo! Sende einen Link (YouTube, TikTok, Instagram, Facebook, Twitter usw.)",
           "enter_url":"📎 Sende einen Videolink!","free_version":"💎 Kostenlose Version. Premium bald ✨",
           "help_text":"🤖 Der Bot kann:\n• Von vielen Seiten laden (yt-dlp)\n• Profil anzeigen\n• Flexible Einstellungen",
           "not_understood":"😅 Ich verstehe nicht, wähle einen Button unten.",
           "lbl_name":"Name","lbl_subscription":"Abonnement","lbl_downloaded":"Heruntergeladen","lbl_format":"Format",
           "lbl_only_audio":"Nur Audio","lbl_description":"Videobeschreibung","lbl_video_plus_audio":"Video + Audio","lbl_since":"Seit",
           "yes":"✅ Ja","no":"❌ Nein","subscription_names":{"free":"Kostenlos 💎","premium":"Premium 💠"}}
}

# ====== КЛАВІАТУРИ ======
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
    langs = [("🇺🇦 Українська","uk"),("🇬🇧 English","en"),("🇷🇺 Русский","ru"),("🇫🇷 Français","fr"),("🇩🇪 Deutsch","de")]
    for text, code in langs:
        kb.add(types.InlineKeyboardButton(text, callback_data=f"lang_{code}"))
    bot.send_message(cid, "🌍 Вибери мову:", reply_markup=kb)

def show_settings(chat_id, user, lang):
    t = texts.get(lang, texts["uk"])
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(f"🎞️ MP4", callback_data="set_format_mp4"),
        types.InlineKeyboardButton(f"🎧 MP3", callback_data="set_format_mp3"),
        types.InlineKeyboardButton(f"🌐 WEBM", callback_data="set_format_webm")
    )
    # Кнопку "Тільки звук" прибрано з інтерфейсу
    kb.add(
        types.InlineKeyboardButton(f"📝 {t['lbl_description']}: {t['yes'] if user['include_description'] else t['no']}", callback_data="toggle_desc")
    )
    kb.add(types.InlineKeyboardButton(f"🎬 {t['lbl_video_plus_audio']}: {t['yes'] if user['video_plus_audio'] else t['no']}", callback_data="toggle_vpa"))
    kb.add(types.InlineKeyboardButton(f"⬅️ {t['back']}", callback_data="back_to_menu"))
    bot.send_message(chat_id, f"⚙️ {t['settings']}", reply_markup=kb)


# ====== CALLBACK ======
@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    user = get_user(c.from_user)
    lang = user.get("language", "uk")
    t = texts.get(lang, texts["uk"])

    if c.data.startswith("lang_"):
        user["language"] = c.data.split("_")[1]
        save_users(users)
        bot.delete_message(c.message.chat.id, c.message.message_id)
        bot.send_message(c.message.chat.id, texts[user["language"]]["lang_saved"], reply_markup=main_menu(user["language"]))
        return

    if c.data == "back_to_menu":
        bot.delete_message(c.message.chat.id, c.message.message_id)
        bot.send_message(c.message.chat.id, t["menu"], reply_markup=main_menu(lang))
        return

    if c.data.startswith("set_format_"):
        user["format"] = c.data.split("_")[2]
        # якщо вибрано mp3 — автоматично увімкнемо audio_only
        user["audio_only"] = (user["format"] == "mp3")
        bot.answer_callback_query(c.id, f"✅ {t['lbl_format']}: {user['format'].upper()}")
    elif c.data == "toggle_audio":
        user["audio_only"] = not user["audio_only"]
        # якщо ручне переключення — синхронізуємо формат
        if user["audio_only"]:
            user["format"] = "mp3"
        elif user["format"] == "mp3":
            user["format"] = "mp4"
        bot.answer_callback_query(c.id, f"🎧 {t['lbl_only_audio']}: {t['yes'] if user['audio_only'] else t['no']}")
    elif c.data == "toggle_desc":
        user["include_description"] = not user["include_description"]
        bot.answer_callback_query(c.id, f"📝 {t['lbl_description']}: {t['yes'] if user['include_description'] else t['no']}")
    elif c.data == "toggle_vpa":
        user["video_plus_audio"] = not user["video_plus_audio"]
        bot.answer_callback_query(c.id, f"🎬 {t['lbl_video_plus_audio']}: {t['yes'] if user['video_plus_audio'] else t['no']}")

    save_users(users)
    # Прибрати стару розмітку і показати оновлену
    try:
        bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=None)
    except Exception:
        pass
    show_settings(c.message.chat.id, user, lang)

# ====== ЗАВАНТАЖЕННЯ ВІДЕО (yt-dlp) ======
def build_yt_dlp_cmd(url: str, fmt: str, audio_only: bool) -> list:
    """
    Вибір найкращого набору параметрів:
    - audio_only/mp3: -x --audio-format mp3
    - mp4: пріоритезуємо h264+aac, об’єднаємо в mp4
    - webm: пріоритезуємо webm
    """
    cmd = ["yt-dlp"]
    if audio_only or fmt == "mp3":
        cmd += ["-x", "--audio-format", "mp3"]
    elif fmt == "webm":
        # кращий webm
        cmd += ["-S", "ext:webm", "-f", "bv*+ba/b"]
    else:
        # дефолт mp4: найкраще відео/аудіо злиті в mp4
        cmd += ["-S", "ext:mp4:m4a", "-f", "bv*+ba/b"]

    cmd += [url]
    return cmd


def download_and_send(url: str, chat_id: int, lang: str, user: dict):
    t = texts.get(lang, texts["uk"])
    fmt = (user.get("format") or "mp4").lower()
    video_plus_audio = bool(user.get("video_plus_audio"))
    include_desc = bool(user.get("include_description"))

    # Формуємо команду для завантаження відео
    cmd = build_yt_dlp_cmd(url, fmt, False)

    # Шлях до збереження відео
    outtmpl_video = os.path.join(DOWNLOAD_DIR, f"{chat_id}_video.%(ext)s")

    # Вставляємо -o перед URL для відео
    cmd.insert(-1, "-o")
    cmd.insert(-1, outtmpl_video)

    # Завантажуємо відео
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        bot.send_message(chat_id, f"❌ Помилка при завантаженні:\n`{e}`", parse_mode="Markdown")
        return False

    # Якщо "Відео + Аудіо" включено, завантажуємо аудіо
    audio_file = None
    if video_plus_audio:
        outtmpl_audio = os.path.join(DOWNLOAD_DIR, f"{chat_id}_audio.mp3")
        cmd_audio = ["yt-dlp", "-x", "--audio-format", "mp3", "-o", outtmpl_audio, url]

        try:
            subprocess.run(cmd_audio, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            audio_file = sorted(
                glob.glob(os.path.join(DOWNLOAD_DIR, f"{chat_id}_audio.mp3")),
                key=os.path.getmtime,
                reverse=True
            )[0]
        except Exception as e:
            bot.send_message(chat_id, f"❌ Помилка при завантаженні аудіо:\n`{e}`", parse_mode="Markdown")
            return False

    # Шукаємо відео
    video_candidates = glob.glob(os.path.join(DOWNLOAD_DIR, f"{chat_id}_video.*"))
    if not video_candidates:
        bot.send_message(chat_id, "❌ Не вдалося знайти відео після завантаження.")
        return False

    video_file = sorted(video_candidates, key=os.path.getmtime, reverse=True)[0]

    # Підготовка підпису (caption)
    caption = None
    if include_desc:
        try:
            meta_cmd = ["yt-dlp", "--get-title", "--get-description", url]
            meta = subprocess.check_output(meta_cmd, stderr=subprocess.DEVNULL).decode("utf-8",
                                                                                       errors="ignore").splitlines()
            title = meta[0].strip() if meta else ""
            descr = "\n".join(meta[1:]).strip() if len(meta) > 1 else ""

            if len(descr) > 900:
                descr = descr[:900] + "…"
            if len(title) > 200:
                title = title[:200] + "…"
            caption = (title + ("\n\n" + descr if descr else "")).strip() or None
        except Exception:
            caption = None

    # Відправлення відео / аудіо
    try:
        with open(video_file, "rb") as f:
            bot.send_video(chat_id, f, caption=caption)

        if audio_file:
            with open(audio_file, "rb") as f:
                bot.send_audio(chat_id, f, caption=caption)

    except Exception as e:
        bot.send_message(chat_id, f"❌ Не вдалося надіслати файл:\n`{e}`", parse_mode="Markdown")
        return False

    finally:
        try:
            os.remove(video_file)
            if audio_file:
                os.remove(audio_file)
        except Exception:
            pass

    return True


# ====== /start ======
@bot.message_handler(commands=["start"])
def start(message):
    u = get_user(message.from_user)
    lang = u.get("language", "uk")
    bot.send_message(message.chat.id, texts[lang]["welcome"], reply_markup=main_menu(lang))

# ====== ОБРОБКА ПОВІДОМЛЕНЬ ======
@bot.message_handler(func=lambda m: True)
def handle_message(m):
    u = get_user(m.from_user)
    lang = u.get("language", "uk")
    t = texts.get(lang, texts["uk"])
    text_low = (m.text or "").lower()

    chat_type = m.chat.type
    is_private = chat_type == "private"
    is_group = chat_type in ["group", "supergroup"]
    is_channel = chat_type == "channel"

    if is_group:
        try:
            me = bot.get_me()
            username = me.username.lower() if me.username else ""
        except Exception:
            username = ""
        if not (username and f"@{username}" in text_low) and not text_low.startswith(("http://", "https://")):
            return

    if is_channel:
        if not (m.text and m.text.startswith(("http://", "https://"))):
            return

    equivalents = {
        "menu": ["menu", "меню", "menü"],
        "profile": ["profile", "профиль", "профіль", "profil"],
        "settings": ["settings", "налаштування", "настройки", "paramètres", "einstellungen"],
        "language": ["language", "мова", "язык", "langue", "sprache"],
        "subscription": ["subscription", "підписка", "подписка", "abonnement", "mitgliedschaft"],
        "help": ["help", "про", "о боте", "à propos", "über", "about"],
        "back": ["back", "назад", "retour", "zurück"],
    }

    # 1️⃣ Посилання — завантаження
    if (m.text or "").startswith(("http://", "https://")):
        msg = bot.send_message(m.chat.id, "⏳ Завантаження… це може зайняти трохи часу.")
        ok = download_and_send(m.text.strip(), m.chat.id, lang, u)
        try:
            bot.delete_message(m.chat.id, msg.message_id)
        except:
            pass
        if ok:
            u["videos_downloaded"] += 1
            save_users(users)
        return

    # 2️⃣ Кнопки меню — тільки в приваті
    if is_private:
        if any(x in text_low for x in equivalents["menu"]):
            bot.send_message(m.chat.id, t["enter_url"], reply_markup=main_menu(lang))
            return

        if any(x in text_low for x in equivalents["profile"]):
            sub_key = u.get("subscription", "free")
            sub_text = texts[lang]["subscription_names"].get(sub_key, sub_key)
            msg = (
                f"👤 **{t['profile']}**\n\n"
                f"🆔 `{m.from_user.id}`\n"
                f"👋 {t['lbl_name']}: {u['name']}\n"
                f"💎 {t['lbl_subscription']}: {sub_text}\n"
                f"🎥 {t['lbl_downloaded']}: {u['videos_downloaded']}\n"
                f"🎞️ {t['lbl_format']}: {u['format'].upper()}\n"
                f"🎧 {t['lbl_only_audio']}: {t['yes'] if u['audio_only'] else t['no']}\n"
                f"📝 {t['lbl_description']}: {t['yes'] if u['include_description'] else t['no']}\n"
                f"🎬 {t['lbl_video_plus_audio']}: {t['yes'] if u['video_plus_audio'] else t['no']}\n"
                f"📅 {t['lbl_since']}: {u['joined']}"
            )
            bot.send_message(m.chat.id, msg, parse_mode="Markdown", reply_markup=back_menu(lang))
            return

        if any(x in text_low for x in equivalents["settings"]):
            show_settings(m.chat.id, u, lang)
            return

        if any(x in text_low for x in equivalents["language"]):
            ask_language(m.chat.id)
            return

        if any(x in text_low for x in equivalents["subscription"]):
            sub_key = u.get("subscription", "free")
            sub_text = texts[lang]["subscription_names"].get(sub_key, sub_key)
            bot.send_message(m.chat.id, f"{sub_text}\n\n{t['free_version']}", reply_markup=back_menu(lang))
            return

        if any(x in text_low for x in equivalents["help"]):
            bot.send_message(m.chat.id, t["help_text"], reply_markup=back_menu(lang))
            return

        if any(x in text_low for x in equivalents["back"]):
            bot.send_message(m.chat.id, t["menu"], reply_markup=main_menu(lang))
            return

        bot.send_message(m.chat.id, t["not_understood"], reply_markup=main_menu(lang))


# ====== FLASK ДЛЯ RENDER ======
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


# ====== ЗАПУСК БОТА ТА FLASK ======
if __name__ == "__main__":
    print("✅ Бот запущено (Render + Flask)!")
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # ВАЖЛИВО: тільки ОДИН polling → не буде 409
    bot.infinity_polling(timeout=60, long_polling_timeout=90, skip_pending=True)

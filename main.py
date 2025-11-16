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
    raise ValueError("❌ TOKEN не встановлено! Додай TOKEN в env.")

WEBHOOK_HOST = "https://dowlanderbot-2.onrender.com"
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = WEBHOOK_HOST + WEBHOOK_PATH

# threaded=False → безпечно для вебхука
bot = TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

USER_FILE = "users.json"
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# ============================================================
#                 СИСТЕМА КОРИСТУВАЧІВ
# ============================================================

def load_users():
    """Завантажити базу користувачів з файлу."""
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_users(data):
    """Зберегти базу користувачів у файл."""
    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


users = load_users()


def get_user(u):
    """Отримати (або створити) запис користувача."""
    uid = str(u.id)

    if uid not in users:
        users[uid] = {
            "name": u.first_name or "User",
            "subscription": "free",
            "videos_downloaded": 0,
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "language": "uk",
            "format": "mp4",             # mp4 / mp3 / webm
            "audio_only": False,         # запасне поле
            "include_description": True, # поки не використовується, але в профілі показуємо
            "video_plus_audio": True     # надсилати ще й окремий аудіофайл
        }
        save_users(users)

    # Якщо раптом мова поламалась → фіксимо на укр
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
        "help_text": (
            "🤖 Бот вміє:\n"
            "• Завантажувати відео з багатьох сайтів (yt-dlp)\n"
            "• Показувати профіль\n"
            "• Має гнучкі налаштування"
        ),
        "not_understood": "😅 Не розумію, обери кнопку.",

        "lbl_name": "Ім’я",
        "lbl_subscription": "Підписка",
        "lbl_downloaded": "Завантажено",
        "lbl_format": "Формат",
        "lbl_only_audio": "Тільки звук",
        "lbl_description": "Опис відео",
        "lbl_video_plus_audio": "Відео + Аудіо",
        "lbl_since": "З",
        "yes": "Так",
        "no": "Ні",

        "subscription_names": {
            "free": "Безкоштовна 💎"
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
        "welcome": "👋 Hello! Send a video link.",
        "enter_url": "📎 Send a link!",
        "free_version": "💎 Free version.",
        "help_text": (
            "🤖 Bot can:\n"
            "• Download videos\n"
            "• Show profile\n"
            "• Has settings"
        ),
        "not_understood": "😅 I don't understand. Please use buttons.",

        "lbl_name": "Name",
        "lbl_subscription": "Subscription",
        "lbl_downloaded": "Downloaded",
        "lbl_format": "Format",
        "lbl_only_audio": "Audio only",
        "lbl_description": "Description",
        "lbl_video_plus_audio": "Video + Audio",
        "lbl_since": "Since",
        "yes": "Yes",
        "no": "No",

        "subscription_names": {
            "free": "Free 💎"
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
        "welcome": "👋 Привет! Пришли ссылку на видео.",
        "enter_url": "📎 Пришли ссылку!",
        "free_version": "💎 Бесплатная версия.",
        "help_text": (
            "🤖 Бот умеет:\n"
            "• Скачать видео\n"
            "• Показать профиль\n"
            "• Имеет настройки"
        ),
        "not_understood": "😅 Не понимаю, выбери кнопку.",

        "lbl_name": "Имя",
        "lbl_subscription": "Подписка",
        "lbl_downloaded": "Скачано",
        "lbl_format": "Формат",
        "lbl_only_audio": "Только звук",
        "lbl_description": "Описание",
        "lbl_video_plus_audio": "Видео + Аудио",
        "lbl_since": "С",
        "yes": "Да",
        "no": "Нет",

        "subscription_names": {
            "free": "Бесплатная 💎"
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

        "lang_saved": "🇫🇷 Langue enregistrée !",
        "welcome": "👋 Bonjour ! Envoie un lien vidéo.",
        "enter_url": "📎 Envoie un lien !",
        "free_version": "💎 Version gratuite.",
        "help_text": (
            "🤖 Le bot peut :\n"
            "• Télécharger des vidéos\n"
            "• Afficher le profil\n"
            "• A des paramètres"
        ),
        "not_understood": "😅 Je n'ai pas compris, utilise les boutons.",

        "lbl_name": "Nom",
        "lbl_subscription": "Abonnement",
        "lbl_downloaded": "Téléchargé",
        "lbl_format": "Format",
        "lbl_only_audio": "Audio uniquement",
        "lbl_description": "Description",
        "lbl_video_plus_audio": "Vidéo + Audio",
        "lbl_since": "Depuis",
        "yes": "Oui",
        "no": "Non",

        "subscription_names": {
            "free": "Gratuit 💎"
        }
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
        "welcome": "👋 Hallo! Sende einen Videolink.",
        "enter_url": "📎 Link senden!",
        "free_version": "💎 Kostenlose Version.",
        "help_text": (
            "🤖 Der Bot kann:\n"
            "• Videos herunterladen\n"
            "• Profil anzeigen\n"
            "• Einstellungen nutzen"
        ),
        "not_understood": "😅 Ich verstehe nicht, bitte benutze die Buttons.",

        "lbl_name": "Name",
        "lbl_subscription": "Mitgliedschaft",
        "lbl_downloaded": "Heruntergeladen",
        "lbl_format": "Format",
        "lbl_only_audio": "Nur Audio",
        "lbl_description": "Beschreibung",
        "lbl_video_plus_audio": "Video + Audio",
        "lbl_since": "Seit",
        "yes": "Ja",
        "no": "Nein",

        "subscription_names": {
            "free": "Kostenlos 💎"
        }
    }
}


# ============================================================
#                 КЛАВІАТУРИ
# ============================================================

def main_menu(lang: str) -> types.ReplyKeyboardMarkup:
    """Головне меню (reply-клавіатура)."""
    t = texts[lang]
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(f"📋 {t['menu']}", f"👤 {t['profile']}")
    kb.add(f"⚙️ {t['settings']}", f"🌍 {t['language']}")
    kb.add(f"💎 {t['subscription']}", f"ℹ️ {t['help']}")
    return kb


def back_menu(lang: str) -> types.ReplyKeyboardMarkup:
    """Клавіатура з кнопкою Назад."""
    t = texts[lang]
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(f"⬅️ {t['back']}")
    return kb


def settings_keyboard(user: dict) -> types.InlineKeyboardMarkup:
    """
    Інлайн-клавіатура налаштувань.

    Вигляд максимально наближений до скріну:
    ┌ MP4  | MP3 ┐
    ├ WEBM ┤
    ├ Опис відео: ✅ Так/❌ Ні ┤
    └ Відео + Аудіо: ✅ Так/❌ Ні ┘
    """
    lang = user["language"]
    t = texts[lang]

    kb = types.InlineKeyboardMarkup(row_width=2)

    # Формати (без галочок, як на скріні – просто перемикають формат)
    kb.row(
        types.InlineKeyboardButton("MP4", callback_data="toggle_format_mp4"),
        types.InlineKeyboardButton("MP3", callback_data="toggle_format_mp3"),
    )
    kb.add(types.InlineKeyboardButton("WEBM", callback_data="toggle_format_webm"))

    # Опис відео
    desc_state = f"✅ {t['yes']}" if user["include_description"] else f"❌ {t['no']}"
    desc_label = f"{t['lbl_description']}: {desc_state}"
    kb.add(types.InlineKeyboardButton(desc_label, callback_data="toggle_desc"))

    # Відео + Аудіо
    vpa_state = f"✅ {t['yes']}" if user["video_plus_audio"] else f"❌ {t['no']}"
    vpa_label = f"{t['lbl_video_plus_audio']}: {vpa_state}"
    kb.add(types.InlineKeyboardButton(vpa_label, callback_data="toggle_vpa"))

    return kb


# ============================================================
#            АЛІАСИ КОМАНД (усі мови + емодзі)
# ============================================================

CMD = {
    "menu": [
        "меню", "menu", "главное меню", "main menu"
    ],
    "profile": [
        "профіль", "проф", "profile", "профиль"
    ],
    "settings": [
        "налаштування", "налаш", "настройки", "settings", "setting", "config"
    ],
    "language": [
        "мова", "язык", "language", "lang"
    ],
    "subscription": [
        "підписка", "подписка", "subscription", "sub"
    ],
    "help": [
        "про бота", "о боте", "help", "about bot", "info", "инфо"
    ],
    "back": [
        "назад", "back", "retour", "zurück", "вернуться", "⬅️"
    ],
}


def match_cmd(text: str):
    """
    Повертає логічну команду (menu/profile/...) або None.
    Працює по всіх мовах, регістр і емодзі ігноруються.
    """
    text = (text or "").lower().strip()
    for cmd, variants in CMD.items():
        for v in variants:
            if v in text:
                return cmd
    return None


# ============================================================
#                 ЗАВАНТАЖЕННЯ ВІДЕО
# ============================================================

def build_yt_cmd(url: str, fmt: str, output_template: str, audio_only: bool = False):
    """
    Зібрати команду yt-dlp.
    fmt: "mp4" / "mp3" / "webm"
    output_template: шлях з плейсхолдером %(ext)s або шаблон yt-dlp.
    """
    cmd = ["yt-dlp", "-o", output_template]

    # Тільки аудіо
    if audio_only or fmt == "mp3":
        cmd += ["-x", "--audio-format", "mp3"]
        cmd.append(url)
        return cmd

    # Відеоформати
    if fmt == "webm":
        cmd += ["-S", "ext:webm", "-f", "bv*+ba/b"]
    else:  # mp4 за замовчуванням
        cmd += ["-S", "ext:mp4:m4a", "-f", "bv*+ba/b"]

    cmd.append(url)
    return cmd


def download_and_send(url: str, chat_id: int, user: dict, lang: str) -> bool:
    """
    Основна логіка завантаження й надсилання файлів.
    - Якщо format = mp3 → надсилаємо тільки аудіо.
    - Якщо format = mp4/webm:
        * завжди відео;
        * якщо user["video_plus_audio"] = True → ще й аудіо mp3.
    """
    t = texts[lang]
    fmt = user["format"]

    # ---------- Випадок: ТІЛЬКИ АУДІО (MP3) ----------
    if fmt == "mp3":
        audio_path_template = os.path.join(DOWNLOAD_DIR, f"{chat_id}_audio.%(ext)s")
        cmd = build_yt_cmd(url, "mp3", audio_path_template, audio_only=True)

        try:
            subprocess.run(cmd, check=True)
        except Exception:
            bot.send_message(chat_id, "❌ Помилка завантаження аудіо.")
            return False

        audio_files = glob.glob(os.path.join(DOWNLOAD_DIR, f"{chat_id}_audio.*"))
        if not audio_files:
            bot.send_message(chat_id, "❌ Не вдалося знайти аудіофайл.")
            return False

        audio_file = audio_files[0]
        with open(audio_file, "rb") as f:
            bot.send_audio(chat_id, f)

        return True

    # ---------- Випадок: ВІДЕО (MP4 / WEBM) ----------
    video_path_template = os.path.join(DOWNLOAD_DIR, f"{chat_id}_video.%(ext)s")
    cmd = build_yt_cmd(url, fmt, video_path_template, audio_only=False)

    try:
        subprocess.run(cmd, check=True)
    except Exception:
        bot.send_message(chat_id, "❌ Помилка завантаження відео.")
        return False

    video_files = glob.glob(os.path.join(DOWNLOAD_DIR, f"{chat_id}_video.*"))
    if not video_files:
        bot.send_message(chat_id, "❌ Не вдалося знайти відеофайл.")
        return False

    video_file = video_files[0]
    with open(video_file, "rb") as f:
        bot.send_video(chat_id, f)

    # ---------- Додатково аудіо (якщо дозволено) ----------
    if user.get("video_plus_audio", True):
        audio_out = os.path.join(DOWNLOAD_DIR, f"{chat_id}_audio.mp3")
        try:
            subprocess.run(
                ["yt-dlp", "-x", "--audio-format", "mp3", "-o", audio_out, url],
                check=True
            )
            with open(audio_out, "rb") as f:
                bot.send_audio(chat_id, f)
        except Exception:
            # Аудіо — опціонально, тому просто мовчки ігноруємо помилку
            pass

    return True


# ============================================================
#                 CALLBACK (мови + налаштування)
# ============================================================

@bot.callback_query_handler(func=lambda c: True)
def callback(c: types.CallbackQuery):
    user = get_user(c.from_user)
    lang = user["language"]
    t = texts[lang]

    data = c.data or ""

    # ---------- Вибір мови ----------
    if data.startswith("lang_"):
        new_lang = data.split("_", 1)[1]
        if new_lang in texts:
            user["language"] = new_lang
            save_users(users)

            # Видаляємо старе повідомлення з кнопками мов
            try:
                bot.delete_message(c.message.chat.id, c.message.message_id)
            except Exception:
                pass

            bot.answer_callback_query(c.id, t["lang_saved"])
            bot.send_message(
                c.message.chat.id,
                texts[new_lang]["lang_saved"],
                reply_markup=main_menu(new_lang)
            )
        else:
            bot.answer_callback_query(c.id, "❌ Невідома мова.")
        return

    # ---------- Налаштування формату / прапорців ----------
    updated = False

    if data == "toggle_format_mp4":
        user["format"] = "mp4"
        user["audio_only"] = False
        updated = True

    elif data == "toggle_format_mp3":
        user["format"] = "mp3"
        user["audio_only"] = True
        # Для mp3 опція "відео + аудіо" не актуальна
        updated = True

    elif data == "toggle_format_webm":
        user["format"] = "webm"
        user["audio_only"] = False
        updated = True

    elif data == "toggle_desc":
        user["include_description"] = not user["include_description"]
        updated = True

    elif data == "toggle_vpa":
        # Має сенс лише для відеоформатів, але хай перемикається завжди
        user["video_plus_audio"] = not user["video_plus_audio"]
        updated = True

    if updated:
        save_users(users)
        bot.answer_callback_query(c.id, "✔ Збережено!")

        # Оновлюємо клавіатуру під повідомленням "Налаштування"
        try:
            bot.edit_message_reply_markup(
                chat_id=c.message.chat.id,
                message_id=c.message.message_id,
                reply_markup=settings_keyboard(user)
            )
        except Exception:
            # Якщо редагування не вдалось (старе повідомлення, і т.д.) – просто ігноруємо
            pass
    else:
        bot.answer_callback_query(c.id, "❓ Невідома дія.")


# ============================================================
#                 ХЕНДЛЕРИ ПОВІДОМЛЕНЬ
# ============================================================

@bot.message_handler(commands=["start"])
def start(m: types.Message):
    u = get_user(m.from_user)
    lang = u["language"]
    bot.send_message(
        m.chat.id,
        texts[lang]["welcome"],
        reply_markup=main_menu(lang)
    )


@bot.message_handler(func=lambda m: True)
def msg(m: types.Message):
    u = get_user(m.from_user)
    lang = u["language"]
    t = texts[lang]

    text_raw = m.text or ""
    txt = text_raw.strip().lower()

    # ---------- Якщо це посилання – одразу качаємо ----------
    if txt.startswith(("http://", "https://")):
        bot.send_message(m.chat.id, "⏳ Завантаження…")
        ok = download_and_send(text_raw.strip(), m.chat.id, u, lang)
        if ok:
            u["videos_downloaded"] += 1
            save_users(users)
        return

    # ---------- Парсимо логічну команду ----------
    cmd = match_cmd(text_raw)

    # ---------- Головне меню ----------
    if cmd == "menu":
        bot.send_message(m.chat.id, t["enter_url"], reply_markup=main_menu(lang))
        return

    # ---------- Профіль ----------
    if cmd == "profile":
        sub_name = t["subscription_names"].get(u["subscription"], u["subscription"])
        only_audio_flag = (u["format"] == "mp3") or u.get("audio_only", False)

        msg_text = (
            f"👤 {t['profile']}\n\n"
            f"🆔 `{m.from_user.id}`\n"
            f"👋 {t['lbl_name']}: {u['name']}\n"
            f"💎 {t['lbl_subscription']}: {sub_name}\n"
            f"🎥 {t['lbl_downloaded']}: {u['videos_downloaded']}\n"
            f"🎞️ {t['lbl_format']}: {u['format'].upper()}\n"
            f"🎧 {t['lbl_only_audio']}: "
            f\"{t['yes'] if only_audio_flag else t['no']}\"\n"
            f"📝 {t['lbl_description']}: "
            f\"{t['yes'] if u['include_description'] else t['no']}\"\n"
            f"🎬 {t['lbl_video_plus_audio']}: "
            f\"{t['yes'] if u['video_plus_audio'] else t['no']}\"\n"
            f"📅 {t['lbl_since']}: {u['joined']}\n"
        )

        bot.send_message(
            m.chat.id,
            msg_text,
            parse_mode="Markdown",
            reply_markup=back_menu(lang)
        )
        return

    # ---------- Мова ----------
    if cmd == "language":
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk"))
        kb.add(types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"))
        kb.add(types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"))
        kb.add(types.InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr"))
        kb.add(types.InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de"))

        bot.send_message(m.chat.id, "🌍 Обери мову:", reply_markup=kb)
        return

    # ---------- Налаштування ----------
    if cmd == "settings":
        bot.send_message(
            m.chat.id,
            f"⚙️ {t['settings']}:",
            reply_markup=settings_keyboard(u)
        )
        return

    # ---------- Підписка ----------
    if cmd == "subscription":
        bot.send_message(
            m.chat.id,
            t["free_version"],
            reply_markup=back_menu(lang)
        )
        return

    # ---------- Про бота / Help ----------
    if cmd == "help":
        bot.send_message(
            m.chat.id,
            t["help_text"],
            reply_markup=back_menu(lang)
        )
        return

    # ---------- Назад ----------
    if cmd == "back":
        bot.send_message(
            m.chat.id,
            t["enter_url"],
            reply_markup=main_menu(lang)
        )
        return

    # ---------- Якщо нічого не підійшло ----------
    bot.send_message(
        m.chat.id,
        t["not_understood"],
        reply_markup=main_menu(lang)
    )


# ============================================================
#                     WEBHOOK
# ============================================================

@app.route("/", methods=["GET"])
def home():
    return "Bot is running!"


@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook_receiver():
    json_data = request.get_json()
    if not json_data:
        return "No data", 400

    update = types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return "OK", 200


# ============================================================
#               ЗАПУСК FLASK + ВСТАНОВЛЕННЯ WEBHOOK
# ============================================================

if __name__ == "__main__":
    print("🚀 Запуск Flask + Webhook")

    # Скидаємо старий вебхук і ставимо новий
    bot.delete_webhook()
    bot.set_webhook(url=WEBHOOK_URL)

    # Render зазвичай сам дає PORT
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

import os
import json
import glob
import subprocess
from datetime import datetime
from telebot import TeleBot, types

# ===================== КОНФІГ =====================

TOKEN = os.getenv("TOKEN") or os.getenv("TELEGRAM_TOKEN", "")
if not TOKEN or ":" not in TOKEN:
    raise ValueError("❌ TOKEN не встановлено або неправильний!")

bot = TeleBot(TOKEN)
USER_FILE = "users.json"
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ===================== ЗБЕРЕЖЕННЯ =====================

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

# ===================== ПЕРЕКЛАДИ =====================

texts = {
    "uk": {
        "menu":"Меню","profile":"Профіль","subscription":"Підписка","settings":"Налаштування","language":"Мова","help":"Про бота","back":"Назад",
        "lang_saved":"✅ Мову збережено! 🇺🇦",
        "welcome":"👋 Привіт! Надішли посилання на відео (YouTube, TikTok, Instagram, Facebook, Twitter тощо)",
        "enter_url":"📎 Надішли посилання на відео!",
        "free_version":"💎 Безкоштовна версія. Premium скоро ✨",
        "help_text":"🤖 Бот уміє:\n• Завантажувати відео з багатьох сайтів (yt-dlp)\n• Показувати профіль\n• Має гнучкі налаштування",
        "not_understood":"😅 Не розумію, обери кнопку нижче.",

        "lbl_name":"Ім’я",
        "lbl_subscription":"Підписка",
        "lbl_downloaded":"Завантажено",
        "lbl_format":"Формат",
        "lbl_only_audio":"Тільки звук",
        "lbl_description":"Опис відео",
        "lbl_video_plus_audio":"Відео + Аудіо",
        "lbl_since":"З",

        "yes":"Так",
        "no":"Ні",

        "subscription_names": {
            "free":"Безкоштовна 💎",
            "premium":"Преміум 💠"
        }
    },

    "en": {
        "menu":"Menu","profile":"Profile","subscription":"Subscription","settings":"Settings","language":"Language","help":"About bot","back":"Back",
        "lang_saved":"✅ Language saved! 🇬🇧",
        "welcome":"👋 Hello! Send a link (YouTube, TikTok, Instagram, Facebook, Twitter, etc.)",
        "enter_url":"📎 Send me a video link!",
        "free_version":"💎 Free version. Premium coming soon ✨",
        "help_text":"🤖 The bot can:\n• Download from many sites (yt-dlp)\n• Show profile\n• Has flexible settings",
        "not_understood":"😅 I don't understand, choose a button below.",

        "lbl_name":"Name",
        "lbl_subscription":"Subscription",
        "lbl_downloaded":"Downloaded",
        "lbl_format":"Format",
        "lbl_only_audio":"Audio only",
        "lbl_description":"Video description",
        "lbl_video_plus_audio":"Video + Audio",
        "lbl_since":"Since",

        "yes":"Yes",
        "no":"No",

        "subscription_names": {
            "free":"Free 💎",
            "premium":"Premium 💠"
        }
    },

    "ru": {
        "menu":"Меню","profile":"Профиль","subscription":"Подписка","settings":"Настройки","language":"Язык","help":"О боте","back":"Назад",
        "lang_saved":"✅ Язык сохранён! 🇷🇺",
        "welcome":"👋 Привет! Пришли ссылку (YouTube, TikTok, Instagram, Facebook, Twitter и т.д.)",
        "enter_url":"📎 Пришли ссылку на видео!",
        "free_version":"💎 Бесплатная версия. Premium скоро ✨",
        "help_text":"🤖 Бот умеет:\n• Скачивать видео\n• Показывать профиль\n• Имеет гибкие настройки",
        "not_understood":"😅 Не понимаю, выбери кнопку ниже.",

        "lbl_name":"Имя",
        "lbl_subscription":"Подписка",
        "lbl_downloaded":"Скачано",
        "lbl_format":"Формат",
        "lbl_only_audio":"Только аудио",
        "lbl_description":"Описание видео",
        "lbl_video_plus_audio":"Видео + Аудио",
        "lbl_since":"С",

        "yes":"Да",
        "no":"Нет",

        "subscription_names": {
            "free":"Бесплатная 💎",
            "premium":"Премиум 💠"
        }
    },

    "fr": {
        "menu":"Menu","profile":"Profil","subscription":"Abonnement","settings":"Paramètres","language":"Langue","help":"À propos du bot","back":"Retour",
        "lang_saved":"✅ Langue enregistrée! 🇫🇷",
        "welcome":"👋 Bonjour ! Envoie un lien (YouTube, TikTok, Instagram, etc.)",
        "enter_url":"📎 Envoie un lien vidéo !",
        "free_version":"💎 Version gratuite. Premium bientôt ✨",
        "help_text":"🤖 Le bot peut :\n• Télécharger des vidéos\n• Afficher le profil\n• Paramètres flexibles",
        "not_understood":"😅 Je ne comprends pas, choisis un bouton.",

        "lbl_name":"Nom",
        "lbl_subscription":"Abonnement",
        "lbl_downloaded":"Téléchargé",
        "lbl_format":"Format",
        "lbl_only_audio":"Audio uniquement",
        "lbl_description":"Description",
        "lbl_video_plus_audio":"Vidéo + Audio",
        "lbl_since":"Depuis",

        "yes":"Oui",
        "no":"Non",

        "subscription_names": {
            "free":"Gratuit 💎",
            "premium":"Premium 💠"
        }
    },

    "de": {
        "menu":"Menü","profile":"Profil","subscription":"Abonnement","settings":"Einstellungen","language":"Sprache","help":"Über den Bot","back":"Zurück",
        "lang_saved":"✅ Sprache gespeichert! 🇩🇪",
        "welcome":"👋 Hallo! Sende einen Link (YouTube, TikTok, Instagram, usw.)",
        "enter_url":"📎 Sende einen Videolink!",
        "free_version":"💎 Kostenlose Version. Premium bald ✨",
        "help_text":"🤖 Der Bot kann:\n• Videos herunterladen\n• Profil anzeigen\n• Flexible Einstellungen",
        "not_understood":"😅 Ich verstehe nicht, wähle einen Button unten.",

        "lbl_name":"Name",
        "lbl_subscription":"Abonnement",
        "lbl_downloaded":"Heruntergeladen",
        "lbl_format":"Format",
        "lbl_only_audio":"Nur Audio",
        "lbl_description":"Videobeschreibung",
        "lbl_video_plus_audio":"Video + Audio",
        "lbl_since":"Seit",

        "yes":"Ja",
        "no":"Nein",

        "subscription_names": {
            "free":"Kostenlos 💎",
            "premium":"Premium 💠"
        }
    }
}

# ===================== КЛАВІАТУРИ =====================

def main_menu(lang="uk"):
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
    langs = [("🇺🇦 Українська","uk"),("🇬🇧 English","en"),("🇷🇺 Русский","ru"),("🇫🇷 Français","fr"),("🇩🇪 Deutsch","de")]
    for text, code in langs:
        kb.add(types.InlineKeyboardButton(text, callback_data=f"lang_{code}"))
    bot.send_message(cid, "🌍 Вибери мову:", reply_markup=kb)

def show_settings(chat_id, user, lang):
    t = texts[lang]
    kb = types.InlineKeyboardMarkup(row_width=2)

    kb.add(
        types.InlineKeyboardButton("🎞 MP4", callback_data="set_format_mp4"),
        types.InlineKeyboardButton("🎧 MP3", callback_data="set_format_mp3"),
        types.InlineKeyboardButton("🌐 WEBM", callback_data="set_format_webm"),
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

# ===================== CALLBACK =====================

@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    user = get_user(c.from_user)
    lang = user["language"]
    t = texts[lang]

    if c.data.startswith("lang_"):
        user["language"] = c.data.split("_")[1]
        save_users(users)
        bot.answer_callback_query(c.id)
        bot.send_message(c.message.chat.id, t["lang_saved"], reply_markup=main_menu(user["language"]))
        return

    if c.data == "back_to_menu":
        bot.send_message(c.message.chat.id, t["menu"], reply_markup=main_menu(lang))
        return

    if c.data.startswith("set_format_"):
        user["format"] = c.data.split("_")[2]
        user["audio_only"] = (user["format"] == "mp3")
        save_users(users)
        bot.answer_callback_query(c.id, f"Format set: {user['format']}")
        show_settings(c.message.chat.id, user, lang)
        return

    if c.data == "toggle_desc":
        user["include_description"] = not user["include_description"]
        save_users(users)
        bot.answer_callback_query(c.id)
        show_settings(c.message.chat.id, user, lang)
        return

    if c.data == "toggle_vpa":
        user["video_plus_audio"] = not user["video_plus_audio"]
        save_users(users)
        bot.answer_callback_query(c.id)
        show_settings(c.message.chat.id, user, lang)
        return

# ===================== ЗАВАНТАЖЕННЯ ВІДЕО =====================

def build_yt_dlp_cmd(url, fmt, audio_only):
    cmd = ["yt-dlp"]
    if audio_only or fmt == "mp3":
        cmd += ["-x", "--audio-format", "mp3"]
    elif fmt == "webm":
        cmd += ["-S", "ext:webm", "-f", "bv*+ba/b"]
    else:
        cmd += ["-S", "ext:mp4:m4a", "-f", "bv*+ba/b"]
    cmd += [url]
    return cmd

def download_and_send(url, chat_id, lang, user):
    t = texts[lang]
    fmt = user["format"]
    include_desc = user["include_description"]
    vpa = user["video_plus_audio"]

    # ---- відео ----
    video_out = os.path.join(DOWNLOAD_DIR, f"{chat_id}_video.%(ext)s")
    cmd = build_yt_dlp_cmd(url, fmt, False)
    cmd.insert(-1, "-o")
    cmd.insert(-1, video_out)

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

    # ---- опис ----
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

    # ---- аудіо ----
    audio_file = None
    if vpa:
        audio_out = os.path.join(DOWNLOAD_DIR, f"{chat_id}_audio.mp3")
        try:
            subprocess.run(["yt-dlp", "-x", "--audio-format", "mp3", "-o", audio_out, url],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            audio_file = audio_out
        except:
            audio_file = None

    # ---- надсилання ----
    try:
        bot.send_video(chat_id, open(video_file, "rb"), caption=caption)
        if audio_file:
            bot.send_audio(chat_id, open(audio_file, "rb"), caption=caption)
    except Exception as e:
        bot.send_message(chat_id, f"❌ Не вдалося надіслати файл: {e}")
        return False

    # ---- очистка ----
    try:
        os.remove(video_file)
        if audio_file:
            os.remove(audio_file)
    except:
        pass

    return True

# ===================== ОБРОБКА ПОВІДОМЛЕНЬ =====================

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
        msg = bot.send_message(m.chat.id, "⏳ Завантаження...")
        ok = download_and_send(m.text.strip(), m.chat.id, lang, u)
        try:
            bot.delete_message(m.chat.id, msg.message_id)
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
        msg = (
            f"👤 **{t['profile']}**\n\n"
            f"🆔 `{m.from_user.id}`\n"
            f"👋 {t['lbl_name']}: {u['name']}\n"
            f"💎 {t['lbl_subscription']}: {t['subscription_names']['free']}\n"
            f"🎥 {t['lbl_downloaded']}: {u['videos_downloaded']}\n"
            f"🎞 {t['lbl_format']}: {u['format'].upper()}\n"
            f"📝 {t['lbl_description']}: {t['yes'] if u['include_description'] else t['no']}\n"
            f"🎬 {t['lbl_video_plus_audio']}: {t['yes'] if u['video_plus_audio'] else t['no']}\n"
            f"📅 {t['lbl_since']}: {u['joined']}"
        )
        bot.send_message(m.chat.id, msg, parse_mode="Markdown", reply_markup=back_menu(lang))
        return

    if "налашт" in text or "settings" in text:
        show_settings(m.chat.id, u, lang)
        return

    if "мова" in text or "language" in text:
        ask_language(m.chat.id)
        return

    if "підпис" in text or "subscription" in text:
        bot.send_message(m.chat.id, t["free_version"], reply_markup=back_menu(lang))
        return

    if "help" in text or "про бота" in text:
        bot.send_message(m.chat.id, t["help_text"], reply_markup=back_menu(lang))
        return

    if "назад" in text or "back" in text:
        bot.send_message(m.chat.id, t["menu"], reply_markup=main_menu(lang))
        return

    bot.send_message(m.chat.id, t["not_understood"], reply_markup=main_menu(lang))

# ===================== ЗАПУСК БОТА =====================

if __name__ == "__main__":
    print("✅ Bot started (Polling only, Render Worker mode)")
    bot.infinity_polling(timeout=60, long_polling_timeout=90, skip_pending=True)

import os
import json
import glob
import subprocess
from datetime import datetime

from telebot import TeleBot, types
from flask import Flask, request

# ============================================================
#                     ПІДКЛЮЧЕННЯ МОВ
# ============================================================

from languages import texts   # <--- ВАЖЛИВО


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

    if users[uid]["language"] not in texts:
        users[uid]["language"] = "uk"
        save_users(users)

    return users[uid]


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
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(f"⬅️ {texts[lang]['back']}")
    return kb


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
#            АЛІАСИ КОМАНД
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
#                      CALLBACK (ОНОВЛЕНИЙ!)
# ============================================================

@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    user = get_user(c.from_user)
    lang = user["language"]
    t = texts[lang]

    # ==================== зміна мови ====================
    if c.data.startswith("lang_"):
        new_lang = c.data.replace("lang_", "")
        if new_lang in texts:
            user["language"] = new_lang
            save_users(users)
            t_new = texts[new_lang]

            # без поп-апа щоб не було помилки
            bot.answer_callback_query(c.id)

            bot.edit_message_text(
                t_new["welcome"],
                c.message.chat.id,
                c.message.message_id,
                reply_markup=main_menu(new_lang)
            )
        return

    # ==================== зміна формату ====================
    if c.data.startswith("format_"):
        user["format"] = c.data.replace("format_", "")
        user["audio_only"] = (user["format"] == "mp3")
        save_users(users)

        bot.answer_callback_query(c.id)
        bot.edit_message_reply_markup(
            c.message.chat.id,
            c.message.message_id,
            reply_markup=settings_keyboard(user)
        )
        return

    # ==================== toggle video + audio ====================
    if c.data == "toggle_vpa":
        user["video_plus_audio"] = not user["video_plus_audio"]
        save_users(users)

        bot.answer_callback_query(c.id)
        bot.edit_message_reply_markup(
            c.message.chat.id,
            c.message.message_id,
            reply_markup=settings_keyboard(user)
        )
        return


# ============================================================
#                  ЗАВАНТАЖЕННЯ
# ============================================================

def download_from_url(url, chat_id, user, lang):
    t = texts[lang]

    if "youtube.com" in url or "youtu.be" in url:
        bot.send_message(chat_id, t["yt_disabled"])
        return False

    if "tiktok.com" in url:
        return download_tiktok(url, chat_id, user, lang)

    if "instagram.com" in url:
        return download_instagram(url, chat_id, user, lang)

    bot.send_message(chat_id, t["unsupported"])
    return False


# (⚠ Для скорочення не переписую TikTok/IG функції —
#   вони повністю залишаються без змін у тебе)


# ============================================================
#                     ХЕНДЛЕРИ
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
        bot.send_message(m.chat.id, t["loading"])

        ok = download_from_url(m.text, m.chat.id, u, lang)

        if ok:
            u["videos_downloaded"] += 1
            save_users(users)

        return

    cmd = match_cmd(txt)

    if cmd == "menu":
        bot.send_message(m.chat.id, t["enter_url"], reply_markup=main_menu(lang))
        return

    if cmd == "profile":
        msg_text = (
            f"👤 {t['profile']}\n\n"
            f"🆔 `{m.from_user.id}`\n"
            f"👋 {t['lbl_name']}: {u['name']}\n"
            f"🎥 {t['lbl_downloaded']}: {u['videos_downloaded']}\n"
            f"🎞️ {t['lbl_format']}: {u['format'].upper()}\n"
            f"🎬 {t['lbl_video_plus_audio']}: {t['yes'] if u['video_plus_audio'] else t['no']}\n"
            f"📅 {t['lbl_since']}: {u['joined']}\n"
        )
        bot.send_message(m.chat.id, msg_text, parse_mode="Markdown", reply_markup=back_menu(lang))
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
#                    RUN SERVER
# ============================================================

if __name__ == "__main__":
    print("🚀 Запуск Flask + Webhook")

    bot.delete_webhook()
    bot.set_webhook(url=WEBHOOK_URL)

    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))





import logging
import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters
import warnings

# Logging sozlamalari
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot sozlamalari
BOT_TOKEN = "7283695653:AAGV3bTqdnHdQlqLjF8ztgiEG6Qmv7hQT9s"
ADMIN_ID = 6472114736
ADMIN_USERNAME = "@ASLIDDIN_NORQOBILOV"
PRIMARY_CHANNEL = "@kinolar_olami0504"

# Ma'lumotlar bazasi
users = {}  # {user_id: {"blocked": False}}
movies = {}  # {code: {"name": "", "genre": "", "duration": "", "quality": "", "description": "", "file_id": "", "message_id": "", "downloads": 0}}
admin_sessions = {}  # {user_id: {"state": "", "data": {}}}
channels = []


# SQLite ma'lumotlar bazasi bilan ishlash
def init_db():
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()

    # Users jadvalini yaratish
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            blocked INTEGER DEFAULT 0
        )
    """)

    # Movies jadvalini yaratish
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            code TEXT PRIMARY KEY,
            name TEXT,
            genre TEXT,
            duration TEXT,
            quality TEXT,
            description TEXT,
            file_id TEXT,
            message_id TEXT,
            downloads INTEGER DEFAULT 0
        )
    """)

    # Channels jadvalini yaratish
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            channel TEXT PRIMARY KEY
        )
    """)

    conn.commit()
    conn.close()


def load_all_data():
    global users, movies, channels
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()

    # Users ma'lumotlarini o'qish
    cursor.execute("SELECT user_id, blocked FROM users")
    users = {row[0]: {"blocked": bool(row[1])} for row in cursor.fetchall()}

    # Movies ma'lumotlarini o'qish
    cursor.execute(
        "SELECT code, name, genre, duration, quality, description, file_id, message_id, downloads FROM movies")
    movies = {
        row[0]: {
            "name": row[1],
            "genre": row[2],
            "duration": row[3],
            "quality": row[4],
            "description": row[5],
            "file_id": row[6],
            "message_id": row[7],
            "downloads": row[8]
        } for row in cursor.fetchall()
    }

    # Channels ma'lumotlarini o'qish
    cursor.execute("SELECT channel FROM channels")
    channels = [row[0] for row in cursor.fetchall()]

    # PRIMARY_CHANNEL majburiy obuna ro'yxatida bo'lmasligi uchun
    if PRIMARY_CHANNEL in channels:
        channels.remove(PRIMARY_CHANNEL)
        cursor.execute("DELETE FROM channels WHERE channel = ?", (PRIMARY_CHANNEL,))
        conn.commit()

    conn.close()


def save_user(user_id, blocked):
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO users (user_id, blocked) VALUES (?, ?)",
        (user_id, int(blocked))
    )
    conn.commit()
    conn.close()
    users[user_id] = {"blocked": blocked}


def save_movie(code, data):
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO movies (code, name, genre, duration, quality, description, file_id, message_id, downloads)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (code, data["name"], data["genre"], data["duration"], data["quality"], data["description"],
         data["file_id"], data["message_id"], data["downloads"])
    )
    conn.commit()
    conn.close()
    movies[code] = data


def delete_movie(code):
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM movies WHERE code = ?", (code,))
    conn.commit()
    conn.close()
    if code in movies:
        del movies[code]


def save_channel(channel):
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO channels (channel) VALUES (?)", (channel,))
    conn.commit()
    conn.close()
    if channel not in channels:
        channels.append(channel)


def delete_channel(channel):
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM channels WHERE channel = ?", (channel,))
    conn.commit()
    conn.close()
    if channel in channels:
        channels.remove(channel)


# Foydalanuvchining kanalga obuna ekanligini tekshirish
def check_subscription(context, user_id):
    try:
        for channel in channels:
            chat_member = context.bot.get_chat_member(channel, user_id)
            if chat_member.status not in ["member", "administrator", "creator"]:
                return False
        return True
    except Exception as e:
        logger.error(f"Obuna tekshirishda xato: {e}")
        return False


# Obuna bo'lish menyusini yaratish
def subscription_menu():
    keyboard = [
        [InlineKeyboardButton(f"Kanal: {channel}", url=f"https://t.me/{channel[1:]}")]
        for channel in channels
    ]
    keyboard.append([InlineKeyboardButton("✅ Tasdiqlash", callback_data="check_subscription")])
    return InlineKeyboardMarkup(keyboard)


# Asosiy menyuni yaratish
def main_menu():
    keyboard = [
        [
            InlineKeyboardButton("🔍 Kino qidirish", callback_data="search_movie"),
            InlineKeyboardButton("🏆 Top 10 kinolar", callback_data="top_10")
        ],
        [
            InlineKeyboardButton("📞 Admin bilan bog'lanish", callback_data="contact_admin"),
            InlineKeyboardButton("🎥 Video qo'llanma", callback_data="video_guide")
        ],
        [InlineKeyboardButton("ℹ️ Bot haqida", callback_data="about_bot")]
    ]
    return InlineKeyboardMarkup(keyboard)


# Admin menyusini yaratish
def admin_menu():
    keyboard = [
        [
            InlineKeyboardButton("➕ Kino qo'shish", callback_data="add_movie"),
            InlineKeyboardButton("🗑️ Kino o'chirish", callback_data="delete_movie")
        ],
        [
            InlineKeyboardButton("📢 Reklama yuborish", callback_data="send_ad"),
            InlineKeyboardButton("🚫 Foydalanuvchi bloklash", callback_data="block_user")
        ],
        [
            InlineKeyboardButton("📊 Statistika", callback_data="statistics"),
            InlineKeyboardButton("📺 Kanallar boshqaruvi", callback_data="manage_channels")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


# Kanallar boshqaruvi menyusi
def channels_menu():
    keyboard = [
        [
            InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_channel"),
            InlineKeyboardButton("🗑️ Kanal o'chirish", callback_data="delete_channel")
        ],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]
    ]
    return InlineKeyboardMarkup(keyboard)


# Start buyrug'i
def start(update, context):
    user_id = update.message.from_user.id
    if user_id not in users:
        save_user(user_id, False)

    if users[user_id]["blocked"]:
        update.message.reply_text("❌ Siz bloklangansiz!")
        return

    if not check_subscription(context, user_id):
        update.message.reply_text(
            "📢 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=subscription_menu()
        )
        return

    update.message.reply_text(
        "🎉 Xush kelibsiz! Quyidagi imkoniyatlardan foydalaning:",
        reply_markup=main_menu()
    )


# Admin paneliga kirish
def admin(update, context):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        update.message.reply_text("🚫 Sizda admin huquqlari yo'q!")
        return
    admin_sessions[user_id] = {"state": None, "data": {}}
    update.message.reply_text("🔐 Admin paneli:", reply_markup=admin_menu())


# Tugma bosilganda ishlaydigan funksiya
def button(update, context):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id

    if user_id in users and users[user_id]["blocked"]:
        query.message.reply_text("❌ Siz bloklangansiz!")
        return

    if query.data == "check_subscription":
        if check_subscription(context, user_id):
            query.message.reply_text(
                "✅ Obuna tasdiqlandi! Quyidagi imkoniyatlardan foydalaning:",
                reply_markup=main_menu()
            )
        else:
            query.message.reply_text(
                "❌ Siz hali to'liq obuna bo'lmadingiz!",
                reply_markup=subscription_menu()
            )
        return

    if user_id != ADMIN_ID and not check_subscription(context, user_id):
        query.message.reply_text(
            "❌ Siz hali to'liq obuna bo'lmadingiz!\nQuyidagi kanallarga obuna bo'ling:",
            reply_markup=subscription_menu()
        )
        return

    if query.data == "search_movie":
        query.message.reply_text("🔍 Kino kodini kiriting:")
        context.user_data["state"] = "searching"
    elif query.data == "top_10":
        if not movies:
            query.message.reply_text("😕 Hozircha kinolar yo'q.")
            return
        sorted_movies = sorted(movies.items(), key=lambda x: x[1]["downloads"], reverse=True)[:10]
        response = "🏆 Top 10 kinolar:\n" + "\n".join(
            [f"{code} - {data['name']} (👀 {data['downloads']} marta yuklangan)" for code, data in sorted_movies]
        )
        query.message.reply_text(response)
    elif query.data == "contact_admin":
        query.message.reply_text(f"📞 Admin bilan bog'lanish: {ADMIN_USERNAME}")
    elif query.data == "video_guide":
        query.message.reply_text("🎥 Video qo'llanma: [Havola yoki video kodi]")
    elif query.data == "about_bot":
        query.message.reply_text("ℹ️ Bu bot kino qidirish va ko'rish imkonini beradi!\nAdmin: " + ADMIN_USERNAME)
    elif query.data == "add_movie":
        if user_id != ADMIN_ID:
            query.message.reply_text("🚫 Sizda admin huquqlari yo'q!")
            return
        query.message.reply_text("🎬 Kino faylini (mp4) yuboring:")
        admin_sessions[user_id]["state"] = "add_movie_file"
    elif query.data == "delete_movie":
        if user_id != ADMIN_ID:
            query.message.reply_text("🚫 Sizda admin huquqlari yo'q!")
            return
        query.message.reply_text("🗑️ O'chirish uchun kino kodini kiriting:")
        admin_sessions[user_id]["state"] = "delete_movie"
    elif query.data == "send_ad":
        if user_id != ADMIN_ID:
            query.message.reply_text("🚫 Sizda admin huquqlari yo'q!")
            return
        query.message.reply_text("📢 Reklama matni yoki rasmini yuboring:")
        admin_sessions[user_id]["state"] = "send_ad"
    elif query.data == "block_user":
        if user_id != ADMIN_ID:
            query.message.reply_text("🚫 Sizda admin huquqlari yo'q!")
            return
        query.message.reply_text("🚫 Bloklash uchun foydalanuvchi ID sini kiriting:")
        admin_sessions[user_id]["state"] = "block_user"
    elif query.data == "statistics":
        if user_id != ADMIN_ID:
            query.message.reply_text("🚫 Sizda admin huquqlari yo'q!")
            return
        stats = f"📊 Statistika:\n👥 Obunachilar: {len(users)}\n🎬 Kinolar: {len(movies)}\n📺 Majburiy kanallar: {len(channels)}"
        query.message.reply_text(stats)
    elif query.data == "manage_channels":
        if user_id != ADMIN_ID:
            query.message.reply_text("🚫 Sizda admin huquqlari yo'q!")
            return
        channels_list = "\n".join([f"{i + 1}. {channel}" for i, channel in enumerate(channels)])
        query.message.reply_text(
            f"📺 Mavjud majburiy kanallar:\n{channels_list}\n\nKino kanali: {PRIMARY_CHANNEL}\n\nTanlov qilingiz:",
            reply_markup=channels_menu()
        )
    elif query.data == "add_channel":
        if user_id != ADMIN_ID:
            query.message.reply_text("🚫 Sizda admin huquqlari yo'q!")
            return
        query.message.reply_text("➕ Qo'shish uchun kanal username'ni kiriting (@username):")
        admin_sessions[user_id]["state"] = "add_channel"
    elif query.data == "delete_channel":
        if user_id != ADMIN_ID:
            query.message.reply_text("🚫 Sizda admin huquqlari yo'q!")
            return
        query.message.reply_text("🗯️ O'chirish uchun kanal username'ni kiriting (@username):")
        admin_sessions[user_id]["state"] = "delete_channel"
    elif query.data == "back_to_admin":
        if user_id != ADMIN_ID:
            query.message.reply_text("🚫 Sizda admin huquqlari yo'q!")
            return
        query.message.reply_text("🔐 Admin paneli:", reply_markup=admin_menu())


# Xabarlar bilan ishlash
def handle_message(update, context):
    user_id = update.message.from_user.id
    if user_id not in users:
        save_user(user_id, False)

    if users[user_id]["blocked"]:
        update.message.reply_text("❌ Siz bloklangansiz!")
        return

    if user_id != ADMIN_ID and not check_subscription(context, user_id):
        update.message.reply_text(
            "❌ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=subscription_menu()
        )
        return

    if "state" in context.user_data and context.user_data["state"] == "searching":
        code = update.message.text.strip()
        if code in movies:
            movie = movies[code]
            movie["downloads"] += 1
            save_movie(code, movie)
            caption = (
                f"🎬 Kino: {movie['name']}\n"
                f"🔢 Kod: {code}\n"
                f"🎭 Janr: {movie['genre']}\n"
                f"⏱️ Davomiylik: {movie['duration']}\n"
                f"📺 Sifat: {movie['quality']}\n"
                f"📝 Tavsif: {movie['description']}\n"
                f"👀 Yuklamalar: {movie['downloads']}"
            )
            update.message.reply_video(video=movie["file_id"], caption=caption)
        else:
            update.message.reply_text("😕 Kino topilmadi!")
        context.user_data["state"] = None
        return

    if user_id in admin_sessions and admin_sessions[user_id]["state"]:
        state = admin_sessions[user_id]["state"]
        if state == "add_movie_file":
            if update.message.video:
                admin_sessions[user_id]["data"]["file_id"] = update.message.video.file_id
                update.message.reply_text("🔢 Kino kodini kiriting:")
                admin_sessions[user_id]["state"] = "add_movie_code"
            else:
                update.message.reply_text("❌ Iltimos, mp4 fayl yuboring!")
        elif state == "add_movie_code":
            code = update.message.text.strip()
            if code in movies:
                update.message.reply_text("❌ Bu kod allaqachon mavjud! Boshqa kod kiriting:")
                return
            admin_sessions[user_id]["data"]["code"] = code
            update.message.reply_text("🎬 Kino nomini kiriting:")
            admin_sessions[user_id]["state"] = "add_movie_name"
        elif state == "add_movie_name":
            admin_sessions[user_id]["data"]["name"] = update.message.text.strip()
            update.message.reply_text("🎭 Kino janrini kiriting:")
            admin_sessions[user_id]["state"] = "add_movie_genre"
        elif state == "add_movie_genre":
            admin_sessions[user_id]["data"]["genre"] = update.message.text.strip()
            update.message.reply_text("⏱️ Kino davomiyligini kiriting (masalan, 2 soat):")
            admin_sessions[user_id]["state"] = "add_movie_duration"
        elif state == "add_movie_duration":
            admin_sessions[user_id]["data"]["duration"] = update.message.text.strip()
            update.message.reply_text("📺 Kino sifatini kiriting (masalan, 1080p):")
            admin_sessions[user_id]["state"] = "add_movie_quality"
        elif state == "add_movie_quality":
            admin_sessions[user_id]["data"]["quality"] = update.message.text.strip()
            update.message.reply_text("📝 Kino tavsifini kiriting:")
            admin_sessions[user_id]["state"] = "add_movie_description"
        elif state == "add_movie_description":
            data = admin_sessions[user_id]["data"]
            data["description"] = update.message.text.strip()
            caption = (
                f"🎬 Kino: {data['name']}\n"
                f"🔢 Kod: {data['code']}\n"
                f"🎭 Janr: {data['genre']}\n"
                f"⏱️ Davomiylik: {data['duration']}\n"
                f"📺 Sifat: {data['quality']}\n"
                f"📝 Tavsif: {data['description']}"
            )
            try:
                message = context.bot.send_video(
                    chat_id=PRIMARY_CHANNEL,
                    video=data["file_id"],
                    caption=caption
                )
                movie_data = {
                    "name": data["name"],
                    "genre": data["genre"],
                    "duration": data["duration"],
                    "quality": data["quality"],
                    "description": data["description"],
                    "file_id": data["file_id"],
                    "message_id": str(message.message_id),
                    "downloads": 0
                }
                save_movie(data["code"], movie_data)
                update.message.reply_text("✅ Kino muvaffaqiyatli qo'shildi!")
            except Exception as e:
                update.message.reply_text(f"❌ Xatolik yuz berdi: {str(e)}")
            admin_sessions[user_id]["state"] = None
            admin_sessions[user_id]["data"] = {}
        elif state == "delete_movie":
            code = update.message.text.strip()
            if code in movies:
                try:
                    context.bot.delete_message(
                        chat_id=PRIMARY_CHANNEL,
                        message_id=movies[code]["message_id"]
                    )
                    delete_movie(code)
                    update.message.reply_text("✅ Kino o'chirildi!")
                except Exception as e:
                    update.message.reply_text(f"❌ Xatolik yuz berdi: {str(e)}")
            else:
                update.message.reply_text("😕 Kino topilmadi!")
            admin_sessions[user_id]["state"] = None
        elif state == "send_ad":
            if update.message.text:
                for uid in users:
                    if not users[uid]["blocked"]:
                        try:
                            context.bot.send_message(chat_id=uid, text=update.message.text)
                        except:
                            pass
                update.message.reply_text("✅ Reklama yuborildi!")
            elif update.message.photo:
                for uid in users:
                    if not users[uid]["blocked"]:
                        try:
                            context.bot.send_photo(
                                chat_id=uid,
                                photo=update.message.photo[-1].file_id,
                                caption=update.message.caption or ""
                            )
                        except:
                            pass
                update.message.reply_text("✅ Reklama rasm sifatida yuborildi!")
            else:
                update.message.reply_text("❌ Iltimos, matn yoki rasm yuboring!")
            admin_sessions[user_id]["state"] = None
        elif state == "block_user":
            try:
                block_id = int(update.message.text.strip())
                if block_id in users:
                    save_user(block_id, True)
                    update.message.reply_text(f"✅ Foydalanuvchi {block_id} bloklandi!")
                else:
                    update.message.reply_text("😕 Foydalanuvchi topilmadi!")
            except ValueError:
                update.message.reply_text("❌ Iltimos, to'g'ri ID kiriting!")
            admin_sessions[user_id]["state"] = None
        elif state == "add_channel":
            channel = update.message.text.strip()
            if not channel.startswith("@"):
                update.message.reply_text("❌ Kanal username @ bilan boshlanishi kerak!")
                return
            if channel == PRIMARY_CHANNEL:
                update.message.reply_text("❌ Kino kanali majburiy obunaga qo'shilmaydi!")
                return
            if channel in channels:
                update.message.reply_text("❌ Bu kanal allaqachon mavjud!")
                return
            try:
                context.bot.get_chat(channel)
                save_channel(channel)
                update.message.reply_text(f"✅ {channel} kanali qo'shildi!")
                admin_sessions[user_id]["state"] = None
            except Exception as e:
                update.message.reply_text(f"❌ Xatolik: Kanal topilmadi yoki botda admin emas! {str(e)}")
        elif state == "delete_channel":
            channel = update.message.text.strip()
            if channel not in channels:
                update.message.reply_text("❌ Bu kanal ro'yxatda yo'q!")
                return
            delete_channel(channel)
            update.message.reply_text(f"✅ {channel} kanali o'chirildi!")
            admin_sessions[user_id]["state"] = None


# Botni ishga tushirish
def main():
    init_db()
    load_all_data()
    updater = Updater(BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("admin", admin))
    dispatcher.add_handler(CallbackQueryHandler(button))
    dispatcher.add_handler(MessageHandler(Filters.all & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
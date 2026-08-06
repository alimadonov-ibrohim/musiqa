import asyncio
import os
import shutil
import uuid

import yt_dlp
from telegram import KeyboardButton, ReplyKeyboardMarkup, Update, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ═══════════════════ SOZLAMALAR ═══════════════════
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FFMPEG_DIR = os.path.join(BASE_DIR, "bin")
SONGS_DIR = os.path.join(BASE_DIR, "songs")
os.makedirs(SONGS_DIR, exist_ok=True)

MAX_RESULTS = 5
MAX_NAME_LEN = 60         # Telegram audio nomi uchun xavfsiz uzunlik

# ──── Telegram Mini App (WebApp) ─────────────────────────────────
WEB_APP_URL = os.environ.get(
    "WEB_APP_URL", "https://alimadonov-ibrohim.github.io/musiqa/"
)

WEB_APP_PREFIX = "webapp::"  # Mini App'dan keladigan xabarlar prefiksi


def load_token() -> str:
    token = (os.environ.get("BOT_TOKEN") or "").strip()
    if token:
        return token
    token_path = os.path.join(BASE_DIR, "token.txt")
    if os.path.exists(token_path):
        with open(token_path, encoding="utf-8") as f:
            return f.read().strip()
    return ""


BOT_TOKEN = load_token()


def find_ffmpeg() -> str:
    for root, _dirs, files in os.walk(FFMPEG_DIR):
        for name in files:
            if name.lower() == "ffmpeg.exe":
                return os.path.join(root, name)
    return ""


# ──── yt-dlp orqali qidiruv (API kalit shart emas) ───────────────────
def search_youtube_sync(query: str, max_results: int = MAX_RESULTS) -> list:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
    results = []
    for entry in info.get("entries", []):
        video_id = entry.get("id")
        if not video_id:
            continue
        results.append(
            {
                "video_id": video_id,
                "title": entry.get("title") or "Nomalum nom",
                "channel": entry.get("channel") or entry.get("uploader") or "",
            }
        )
    return results


async def search_youtube(query: str, max_results: int = MAX_RESULTS):
    return await asyncio.to_thread(search_youtube_sync, query, max_results)


# ──── To'liq audio yuklab olish (vaqt chegarasisiz) ──────────────────
def download_full_audio(video_id: str) -> dict:
    workdir = os.path.join(SONGS_DIR, uuid.uuid4().hex)
    os.makedirs(workdir, exist_ok=True)

    ffmpeg = find_ffmpeg()
    opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(workdir, "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 5,
        "socket_timeout": 60,
    }
    if ffmpeg:
        opts["ffmpeg_location"] = ffmpeg
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(video_id, download=True)

    ext = "mp3" if ffmpeg else "m4a"
    path = os.path.join(workdir, f"{video_id}.{ext}")
    if not os.path.exists(path):
        candidates = [
            f
            for f in os.listdir(workdir)
            if f.endswith((".mp3", ".m4a", ".webm", ".ogg"))
        ]
        if not candidates:
            raise RuntimeError("Yuklab olingan fayl topilmadi")
        path = os.path.join(workdir, candidates[0])

    return {
        "path": path,
        "workdir": workdir,
        "title": info.get("title", ""),
        "channel": info.get("uploader") or info.get("channel") or "",
        "duration": int(info.get("duration") or 0),
    }


# ──── Bot buyurnuhar ────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes):
    keyboard = [
        [
            KeyboardButton(
                "🎶 Musiqa Qidiruv (Mini App)",
                web_app=WebAppInfo(url=WEB_APP_URL),
            )
        ]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "🎵 *Musiqa Qidiruv Bot*\n\n"
        "Musiqa yoki qo'shiq nomini yozing, men uni topib, "
        "**to'liq** (vaqt chegarasisiz) yuklab yuboraman.\n\n"
        "Yoki pastdagi **Mini App** tugmasini bosing — chiroyli interfeysdan "
        "qidirib, qo'shiqni tanlang.\n\n"
        "Namunalar:\n"
        "`Yulduz Usmonova - Jonim`\n"
        "`Jony - Fendi`",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )


async def handle_message(update: Update, context: ContextTypes):
    query = (update.message.text or "").strip()
    if not query:
        return

    if query.startswith(WEB_APP_PREFIX):
        query = query[len(WEB_APP_PREFIX):].strip()
        if not query:
            return

    status = await update.message.reply_text(f"🔍 «{query}» qidirilmoqda...")

    try:
        results = await search_youtube(query)
    except Exception as e:
        await status.edit_text(f"❌ Qidiruvda xatolik: {e}")
        return

    if not results:
        await status.edit_text("❌ Hech narsa topilmadi. Boshqa nom bilan sinab ko'ring.")
        return

    best = results[0]
    await status.edit_text(
        f"🎵 Topildi: **{best['title']}**\n"
        f"👤 {best['channel']}\n"
        f"📥 Yuklab olinmoqda, biroz kuting...",
        parse_mode="Markdown",
    )

    try:
        song = await asyncio.to_thread(download_full_audio, best["video_id"])
    except Exception as e:
        await status.edit_text(f"❌ Yuklab olishda xatolik: {e}")
        return

    try:
        with open(song["path"], "rb") as f:
            await update.message.reply_audio(
                audio=f,
                title=song["title"][:MAX_NAME_LEN] or best["title"][:MAX_NAME_LEN],
                performer=(song["channel"] or "Unknown")[:MAX_NAME_LEN],
                duration=song["duration"],
                caption=f"🎵 {best['title']}",
            )
        await status.delete()
    except Exception as e:
        await status.edit_text(f"❌ Yuborishda xatolik: {e}")
    finally:
        shutil.rmtree(song["workdir"], ignore_errors=True)


def build_application(token: str) -> Application:
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app


if __name__ == "__main__":
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN topilmadi!")

    app = build_application(BOT_TOKEN)
    print("Bot ishga tushdi... (to'xtatish uchun Ctrl+C)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
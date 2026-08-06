import json
import os
import sys

from telegram import Update

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from main import build_application

TOKEN = os.environ.get("BOT_TOKEN", "").strip()
WEBHOOK_PATH = "/api/webhook"

bot_app = build_application(TOKEN) if TOKEN else None


async def send_response(send, status, payload):
    body = json.dumps(payload).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                [b"content-type", b"application/json; charset=utf-8"],
                [b"content-length", str(len(body)).encode()],
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def asgi_app(scope, receive, send):
    if scope["type"] != "http":
        return

    method = scope.get("method", "GET")
    path = scope.get("path", "/").rstrip("/")

    if method == "GET":
        await send_response(
            send, 200, {"status": "ok", "service": "musiqa-bot-webhook"}
        )
        return

    if method != "POST" or path != WEBHOOK_PATH:
        await send_response(send, 404, {"error": "not found"})
        return

    if bot_app is None:
        await send_response(send, 500, {"error": "BOT_TOKEN env o'rnatilmagan"})
        return

    chunks = []
    while True:
        message = await receive()
        chunks.append(message.get("body", b""))
        if not message.get("more_body"):
            break
    body = b"".join(chunks)

    try:
        data = json.loads(body)
        update = Update.de_json(data, bot_app.bot)
        await bot_app.process_update(update)
    except Exception as e:
        print(f"Update xatolik: {e}", flush=True)
        await send_response(send, 500, {"ok": False, "error": str(e)})
        return

    await send_response(send, 200, {"ok": True})


app = asgi_app

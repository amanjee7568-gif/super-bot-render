# -*- coding: utf-8 -*-
import os
import json
import hmac
import hashlib
import logging
from flask import Flask, request, jsonify
import requests

# -------- Settings / Env --------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise SystemExit("❌ BOT_TOKEN env var missing")

# प्राथमिकता क्रम: WEBHOOK_URL > RENDER_EXTERNAL_URL + /telegram > WEBHOOK_BASE + /telegram
DEFAULT_PATH = os.getenv("WEBHOOK_PATH", "telegram").strip("/")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
WEBHOOK_BASE = os.getenv("WEBHOOK_BASE", "").rstrip("/")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")

if not WEBHOOK_URL:
    base = RENDER_EXTERNAL_URL or WEBHOOK_BASE
    if base:
        WEBHOOK_URL = f"{base}/{DEFAULT_PATH}"

PORT = int(os.getenv("PORT", "8000"))
HOST = "0.0.0.0"
# Cashfree webhook verify optional (अगर use नहीं कर रहे तो सेट करने की ज़रूरत नहीं)
CASHFREE_WEBHOOK_SECRET = os.getenv("CASHFREE_WEBHOOK_SECRET", "")

# -------- Logging --------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger(__name__)

# -------- Telegram Bot (pyTelegramBotAPI) --------
try:
    import telebot
except Exception as e:
    raise SystemExit(f"❌ pyTelegramBotAPI not installed: {e}")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=False)

# --- Basic handlers (आपके existing handlers न हों तो भी bot test चल जाए) ---
@bot.message_handler(commands=['start', 'help'])
def _start(m):
    bot.reply_to(
        m,
        "✅ Bot live है!\n"
        "• /start — welcome\n"
        "• कोई भी message भेजो — मैं echo कर दूँगा 🙂"
    )

@bot.message_handler(func=lambda m: True, content_types=['text', 'photo', 'document', 'audio', 'voice', 'video', 'sticker', 'location', 'contact'])
def _echo(m):
    try:
        if getattr(m, "text", None):
            bot.reply_to(m, f"Echo: <code>{m.text}</code>")
        else:
            bot.reply_to(m, "📩 Received!")
    except Exception as e:
        log.exception("handler error: %s", e)

# -------- Flask App --------
app = Flask(__name__)

@app.get("/")
def root_ok():
    """
    Health check + current config info
    """
    return jsonify({
        "ok": True,
        "message": "Super Bot Render: Flask is running",
        "webhook_url": WEBHOOK_URL or "(not-set)",
        "path": DEFAULT_PATH,
        "render_external_url": RENDER_EXTERNAL_URL or "(not-set)"
    }), 200

@app.get("/set_webhook")
def set_webhook_manual():
    """
    Browser से hit करके webhook reset कर सकते हो:
    https://<your-domain>/set_webhook
    """
    if not WEBHOOK_URL:
        return jsonify({"ok": False, "error": "WEBHOOK_URL not resolved. Set WEBHOOK_URL or RENDER_EXTERNAL_URL/WEBHOOK_BASE."}), 400

    ok, resp = set_telegram_webhook(WEBHOOK_URL)
    code = 200 if ok else 500
    return jsonify({"ok": ok, "telegram_response": resp}), code

@app.get("/delete_webhook")
def delete_webhook_manual():
    resp = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook").json()
    return jsonify(resp), 200 if resp.get("ok") else 500

# Telegram webhook endpoint
@app.post(f"/{DEFAULT_PATH}")
def telegram_webhook():
    try:
        update = request.get_json(force=True, silent=False)
    except Exception:
        log.warning("Invalid JSON on webhook")
        return "bad request", 400

    try:
        # pyTelegramBotAPI expects raw Update dict
        bot.process_new_updates([telebot.types.Update.de_json(json.dumps(update))])
    except Exception as e:
        log.exception("Update processing failed: %s", e)
        return "error", 200  # Telegram expects 200 to stop retries

    return "ok", 200

@app.get(f"/{DEFAULT_PATH}")
def telegram_get_check():
    # GET पर 200 दे दो — आसान debug
    return "telegram endpoint ready", 200

# Optional: Cashfree webhook (अगर use करते हों)
@app.post("/cashfree/webhook")
def cashfree_webhook():
    if not CASHFREE_WEBHOOK_SECRET:
        log.info("Cashfree secret not set; skipping verification")
        data = request.get_json(silent=True) or {}
        log.info("Cashfree payload: %s", data)
        return "ok", 200

    signature = request.headers.get("x-webhook-signature", "")
    payload = request.get_data()  # raw bytes
    expected = hmac.new(
        CASHFREE_WEBHOOK_SECRET.encode("utf-8"),
        payload,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        log.warning("Cashfree signature mismatch")
        return "unauthorized", 401

    data = request.get_json(silent=True) or {}
    log.info("Cashfree verified payload: %s", data)
    # TODO: अपने बिजनेस लॉजिक के अनुसार payment status handle करें
    return "ok", 200

# -------- Helper: set webhook --------
def set_telegram_webhook(url: str):
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
            params={"url": url, "drop_pending_updates": "true"},
            timeout=15,
        )
        j = resp.json()
        if j.get("ok"):
            log.info("✅ Webhook set to: %s", url)
            return True, j
        log.error("❌ setWebhook failed: %s", j)
        return False, j
    except Exception as e:
        log.exception("setWebhook exception: %s", e)
        return False, {"error": str(e)}

# -------- Startup --------
if __name__ == "__main__":
    # Auto set webhook if URL resolved
    if WEBHOOK_URL:
        set_telegram_webhook(WEBHOOK_URL)
    else:
        log.warning("WEBHOOK_URL not resolved; open /set_webhook after deploy")

    log.info("🚀 Starting Flask on %s:%s", HOST, PORT)
    # Flask dev server is fine on Render for simple bots; for heavy traffic use gunicorn
    app.run(host=HOST, port=PORT)

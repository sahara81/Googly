import os
import re
import requests
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN environment variable set nahi mila!")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def get_google_rating(query: str) -> str:
    search_text = f"{query} rating"
    params = {"q": search_text, "hl": "en"}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }

    try:
        res = requests.get("https://www.google.com/search", params=params, headers=headers, timeout=10)
        res.raise_for_status()
    except Exception as e:
        print("Google HTTP error:", e)
        return "❌ Google se rating fetch karte waqt error aa gaya."

    soup = BeautifulSoup(res.text, "html.parser")
    text = soup.get_text(" ", strip=True)

    match = re.search(r"(\d{1,3})%\s+Google users", text)
    if match:
        return f"👍 {match.group(1)}% Google users liked this."

    return "⚠️ Google users rating nahi mila."


def send_message(chat_id: int, text: str):
    try:
        requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
    except Exception as e:
        print("Telegram send error:", e)


@app.route("/", methods=["GET"])
def home():
    return "Bot Running Successfully 🎯", 200


@app.route(f"/webhook/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    update = request.get_json(silent=True, force=True) or {}
    message = update.get("message")

    if not message:
        return jsonify({"ok": True})

    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    if text.startswith("/start"):
        send_message(
            chat_id,
            "👋 Welcome!\n\nUse command:\n`/rate <movie or series name>`\n\nExample:\n`/rate Dark`\n`/rate Mirzapur`"
        )
        return jsonify({"ok": True})

    if text.startswith("/rate"):
        parts = text.split(" ", 1)

        if len(parts) == 1 or not parts[1].strip():
            send_message(chat_id, "Usage: `/rate <title>`\nExample: `/rate Money Heist`")
            return jsonify({"ok": True})

        query = parts[1].strip()
        send_message(chat_id, f"🔍 Searching Google rating for *{query}*...")

        rating = get_google_rating(query)
        send_message(chat_id, f"🎬 *{query}*\n\n{rating}")
        return jsonify({"ok": True})

    send_message(chat_id, "Unknown command. Use:\n`/rate <title>`")
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

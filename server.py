import os
import re
import requests
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup

app = Flask(__name__)

# Telegram token env se lo
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN environment variable set nahi mila!")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


# ----------------- GOOGLE RATING FUNCTION -----------------
def get_google_rating(query: str) -> str:
    # Search ko thoda specific banaya
    search_text = f"{query} movie google users rating"
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
        return "Google se rating fetch karte waqt error aa gaya."

    soup = BeautifulSoup(res.text, "html.parser")

    # 1) Pehle exact 'Google users' rating block pakadne ki koshish
    rating_block = None
    try:
        rating_block = soup.select_one("div[data-attrid='kc:/ugc:thumbs_up']")
    except Exception as e:
        print("select_one error:", e)

    if rating_block:
        text = rating_block.get_text(" ", strip=True)
        m = re.search(r"(\d{1,3})%", text)
        if m:
            return f"{m.group(1)}% Google users liked this."

    # 2) Agar upar se nahi mila, full text me fallback search
    full_text = soup.get_text(" ", strip=True)

    patterns = [
        r"(\d{1,3})%\s+Google users",
        r"Google users[^0-9]*(\d{1,3})%"
    ]

    for pat in patterns:
        m = re.search(pat, full_text)
        if m:
            return f"{m.group(1)}% Google users liked this."

    # 3) Still nahi mila
    return "Is title ke liye Google users rating nahi mila."


# ----------------- TELEGRAM SEND FUNCTION -----------------
def send_message(chat_id: int, text: str):
    try:
        r = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
            },
            timeout=10,
        )
        print("sendMessage status:", r.status_code, r.text)
    except Exception as e:
        print("Telegram send error:", e)


# ----------------- ROUTES -----------------
@app.route("/", methods=["GET"])
def home():
    return "Bot Running Successfully", 200


# IMPORTANT: webhook path me env se aaya hua token hi use ho raha hai
@app.route(f"/webhook/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    update = request.get_json(silent=True, force=True) or {}
    print("Update:", update)

    message = update.get("message")
    if not message:
        return jsonify({"ok": True})

    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    if not isinstance(text, str):
        return jsonify({"ok": True})

    # /start command
    if text.startswith("/start"):
        send_message(
            chat_id,
            "Welcome!\n"
            "Use:\n"
            "/rate <movie ya series ka naam>\n\n"
            "Example:\n"
            "/rate Avengers\n"
            "/rate Mirzapur\n"
            "/rate Dark"
        )
        return jsonify({"ok": True})

    # /rate command
    if text.startswith("/rate"):
        parts = text.split(" ", 1)

        if len(parts) == 1 or not parts[1].strip():
            send_message(chat_id, "Usage: /rate <title>\nExample: /rate Money Heist")
            return jsonify({"ok": True})

        query = parts[1].strip()
        send_message(chat_id, f"\"{query}\" ke liye Google rating dhoond raha hun...")

        rating = get_google_rating(query)
        reply = f"Title: {query}\n\n{rating}"
        send_message(chat_id, reply)
        return jsonify({"ok": True})

    # Unknown message
    send_message(chat_id, "Unknown command. Use: /rate <title>")
    return jsonify({"ok": True})


if __name__ == "__main__":
    # Local run ke liye
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

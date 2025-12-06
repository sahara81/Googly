import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN env var missing")
if not SERPAPI_KEY:
    raise RuntimeError("SERPAPI_KEY env var missing")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
SERPAPI_URL = "https://serpapi.com/search"


# ----------------- GOOGLE USERS RATING VIA SERPAPI -----------------
def get_google_rating(query: str) -> str:
    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_KEY,
        "hl": "en",
        "gl": "in",
        "device": "desktop",
    }

    try:
        r = requests.get(SERPAPI_URL, params=params, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print("SerpAPI HTTP error:", e)
        return "Google se rating fetch karte waqt error aa gaya. (SerpAPI)"

    data = r.json()
    kg = data.get("knowledge_graph") or {}

    # docs ke hisaab se: knowledge_graph.user_statistics.platform/statistic 
    user_stats = kg.get("user_statistics")

    # expected structure: dict with keys platform + statistic
    if isinstance(user_stats, dict):
        platform = user_stats.get("platform", "")
        stat = user_stats.get("statistic", "")
        if platform and stat:
            return f"{platform}: {stat}"

    return "Is title ke liye Google users rating SerpAPI se nahi mili."


# ----------------- TELEGRAM SEND FUNCTION -----------------
def send_message(chat_id: int, text: str):
    try:
        resp = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
        print("sendMessage:", resp.status_code, resp.text)
    except Exception as e:
        print("Telegram send error:", e)


# ----------------- ROUTES -----------------
@app.route("/", methods=["GET"])
def home():
    return "Bot Running Successfully", 200


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

    # /start
    if text.startswith("/start"):
        send_message(
            chat_id,
            "Google Users Rating Bot 😈\n\n"
            "Use:\n"
            "/rate <movie ya series ka naam>\n\n"
            "Example:\n"
            "/rate Dark\n"
            "/rate Avengers Endgame\n"
            "/rate Mirzapur"
        )
        return jsonify({"ok": True})

    # /rate
    if text.startswith("/rate"):
        parts = text.split(" ", 1)
        if len(parts) == 1 or not parts[1].strip():
            send_message(chat_id, "Usage: /rate <title>\nExample: /rate Money Heist")
            return jsonify({"ok": True})

        query = parts[1].strip()
        send_message(chat_id, f"\"{query}\" ke liye Google users rating dhoond raha hun...")

        rating = get_google_rating(query)
        reply = f"Title: {query}\n\n{rating}"
        send_message(chat_id, reply)
        return jsonify({"ok": True})

    # unknown
    send_message(chat_id, "Unknown command. Use: /rate <title>")
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

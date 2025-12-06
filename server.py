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
    # Search text generic rakha, movie/series both ke liye chalega
    search_text = f"{query} google users rating"
    params = {"q": search_text}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }

    try:
        res = requests.get("https://www.google.com/search", params=params, headers=headers, timeout=10)
        print("Google final URL:", res.url)
        res.raise_for_status()
    except Exception as e:
        print("Google HTTP error:", e)
        return "Google se rating fetch karte waqt error aa gaya."

    soup = BeautifulSoup(res.text, "html.parser")

    # ---------- 1) Specific Google users block dhoondo ----------
    try:
        block = soup.select_one("div[data-attrid='kc:/ugc:thumbs_up']")
    except Exception as e:
        print("select_one error:", e)
        block = None

    if block:
        text = block.get_text(" ", strip=True)
        print("Block text:", text)
        m = re.search(r"(\d{1,3})\s*%", text)
        if m:
            return f"{m.group(1)}% Google users liked this."

    # ---------- 2) aria-label based search (kuch pages aise hote hain) ----------
    try:
        span = soup.select_one("span[aria-label*='Google users']")
        if span:
            text = span.get("aria-label", "")
            print("aria-label text:", text)
            m = re.search(r"(\d{1,3})\s*%", text)
            if m:
                return f"{m.group(1)}% Google users liked this."
    except Exception as e:
        print("aria-label search error:", e)

    # ---------- 3) Fallback: poore page me se likely line dhoondo ----------
    full_text = soup.get_text(" ", strip=True)
    print("Page text snippet:", full_text[:400])

    patterns = [
        r"(\d{1,3})\s*%\s*Google users",
        r"Google users[^0-9]{0,30}(\d{1,3})\s*%",
        r"(\d{1,3})\s*%\s*of Google users",
    ]

    for pat in patterns:
        m = re.search(pat, full_text)
        if m:
            return f"{m.group(1)}% Google users liked this."

    # ---------- 4) Extreme fallback: koi bhi % lo jisme nearby 'Google' aa raha ho ----------
    perc_candidates = re.finditer(r"(\d{1,3})\s*%", full_text)
    for match in perc_candidates:
        start = max(0, match.start() - 80)
        end = min(len(full_text), match.end() + 80)
        snippet = full_text[start:end]
        if "Google" in snippet or "users" in snippet:
            print("Snippet candidate:", snippet)
            return f"{match.group(1)}% (likely Google users rating, exact text parse nahi ho paya)."

    # ---------- 5) Still nahi mila ----------
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
            "Welcome!\n"
            "Use:\n"
            "/rate <movie ya series ka naam>\n\n"
            "Example:\n"
            "/rate Avengers\n"
            "/rate Mirzapur\n"
            "/rate Dark"
        )
        return jsonify({"ok": True})

    # /rate
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

    # unknown
    send_message(chat_id, "Unknown command. Use: /rate <title>")
    return jsonify({"ok": True})


if __name__ == "__main__":
    # Local test ke liye
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

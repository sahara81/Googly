import os
import requests
from flask import Flask, request, jsonify
from justwatch import JustWatch

app = Flask(__name__)

# -------- ENV VARS --------
TOKEN = os.getenv("TELEGRAM_TOKEN")
SERPAPI = os.getenv("SERPAPI_KEY")
TMDB = os.getenv("TMDB_API_KEY")
OMDB = os.getenv("OMDB_API_KEY")

TG = f"https://api.telegram.org/bot{TOKEN}"
TMDB_URL = "https://api.themoviedb.org/3"
REGION = "US"   # 🔥 FIXED USA REGION

# -------- GOOGLE RATING --------
def google_rating(title):
    try:
        r = requests.get(
            "https://serpapi.com/search",
            params={"engine": "google", "q": title, "api_key": SERPAPI, "hl": "en", "gl": "us"}
        ).json()
        stats = r.get("knowledge_graph", {}).get("user_statistics", {})
        if stats:
            return f"{stats.get('platform')}: {stats.get('statistic')}"
        return "Google rating not available."
    except:
        return "Error fetching Google rating."


# -------- TMDB SEARCH --------
def tmdb_search(title):
    res = requests.get(
        f"{TMDB_URL}/search/multi",
        params={"api_key": TMDB, "query": title}
    ).json().get("results", [])

    for item in res:
        if item.get("media_type") in ("movie", "tv"):
            return item
    return None


# -------- TMDB LANGUAGES --------
def languages(media, tmdb_id):
    data = requests.get(
        f"{TMDB_URL}/{media}/{tmdb_id}",
        params={"api_key": TMDB}
    ).json()

    langs = [x["english_name"] for x in data.get("spoken_languages", [])]
    return ", ".join(langs) if langs else "Not listed"


# -------- IMDb --------
def imdb_rating(media, tmdb_id):
    ext = requests.get(
        f"{TMDB_URL}/{media}/{tmdb_id}/external_ids",
        params={"api_key": TMDB}
    ).json()

    imdb_id = ext.get("imdb_id")
    if not imdb_id:
        return "IMDb rating not found."

    res = requests.get(
        "https://www.omdbapi.com/",
        params={"apikey": OMDB, "i": imdb_id}
    ).json()

    if res.get("Response") == "True":
        return f"{res['imdbRating']}/10 ({res['imdbVotes']} votes)"
    return "IMDb rating not available."


# -------- OTT (USA ONLY via JustWatch) --------
def ott(title):
    try:
        jw = JustWatch(country=REGION)
        item = jw.search_for_item(query=title)["items"][0]
        offers = item.get("offers", [])
        ids = {x["provider_id"] for x in offers if x["monetization_type"] == "flatrate"}

        providers = jw.get_providers()
        names = [p["clear_name"] for p in providers if p["id"] in ids]

        return ", ".join(names) if names else "Not available in USA."
    except:
        return "OTT data not available."


# -------- TELEGRAM SEND --------
def send(chat, text):
    requests.post(f"{TG}/sendMessage", json={"chat_id": chat, "text": text})


# -------- WEBHOOK HANDLER --------
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    text = data.get("message", {}).get("text", "")
    chat = data.get("message", {}).get("chat", {}).get("id")

    if text.startswith("/start"):
        send(chat, "Send:\n/rate <movie/show>\nExample: /rate Money Heist")
        return jsonify(ok=True)

    if text.startswith("/rate"):
        q = text.replace("/rate", "").strip()
        info = tmdb_search(q)

        if not info:
            send(chat, "Not found.")
            return jsonify(ok=True)

        title = info.get("title") or info.get("name")
        year = (info.get("release_date") or info.get("first_air_date") or "")[:4]
        media = info["media_type"]

        reply = f"""
🎬 {title} ({year})

📍 Google: {google_rating(title)}
⭐ IMDb: {imdb_rating(media, info['id'])}

🎤 Languages:
{languages(media, info['id'])}

📺 Available in USA:
{ott(title)}
""".strip()

        send(chat, reply)
        return jsonify(ok=True)

    return jsonify(ok=True)


@app.route("/")
def home():
    return "Running", 200


if __name__ == "__main__":
    app.run()

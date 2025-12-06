import os
import requests
from flask import Flask, request, jsonify
from justwatch import JustWatch

app = Flask(__name__)

# -------- ENV Vars ----------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
SERPAPI_URL = "https://serpapi.com/search"
TMDB_BASE_URL = "https://api.themoviedb.org/3"
OMDB_URL = "https://www.omdbapi.com/"


# ------------- GOOGLE RATING -------------
def get_google_rating(title):
    params = {
        "engine": "google",
        "q": title,
        "api_key": SERPAPI_KEY,
        "hl": "en",
        "gl": "us"
    }

    try:
        r = requests.get(SERPAPI_URL, params=params, timeout=10)
        data = r.json()
        kg = data.get("knowledge_graph", {})
        stats = kg.get("user_statistics", {})
        platform = stats.get("platform")
        stat = stats.get("statistic")

        if platform and stat:
            return f"{platform}: {stat}"
        return "Google rating not available."

    except:
        return "Error getting Google rating."


# ------------- TMDB SEARCH -------------
def tmdb_search(query):
    url = f"{TMDB_BASE_URL}/search/multi"
    params = {"query": query, "api_key": TMDB_API_KEY}

    r = requests.get(url, params=params).json().get("results", [])
    
    for i in r:
        if i.get("media_type") in ("movie", "tv"):
            return {
                "id": i.get("id"),
                "type": i.get("media_type"),
                "title": i.get("title") or i.get("name"),
                "year": (i.get("release_date") or i.get("first_air_date") or "")[:4]
            }
    return None


# ------------- TMDB DETAILS (Languages) -------------
def get_languages(media_type, tmdb_id):
    url = f"{TMDB_BASE_URL}/{media_type}/{tmdb_id}"
    params = {"api_key": TMDB_API_KEY}

    langs = []
    data = requests.get(url, params=params).json()

    for l in data.get("spoken_languages", []):
        langs.append(l.get("english_name"))

    return langs or ["Not listed"]


# ------------- GET IMDb ID -> IMDb Rating -------------
def get_imdb_id(media_type, tmdb_id):
    url = f"{TMDB_BASE_URL}/{media_type}/{tmdb_id}/external_ids"
    r = requests.get(url, params={"api_key": TMDB_API_KEY}).json()
    return r.get("imdb_id")


def get_imdb_rating(imdb_id):
    if not imdb_id:
        return "IMDb rating not found."

    params = {"apikey": OMDB_API_KEY, "i": imdb_id}
    r = requests.get(OMDB_URL, params=params).json()

    if r.get("Response") == "True":
        return f"IMDb: {r.get('imdbRating')}/10 ({r.get('imdbVotes')} votes)"
    return "IMDb rating not available."


# ------------- JUSTWATCH USA OTT -------------
def get_ott_usa(title):
    try:
        jw = JustWatch(country="US")
        res = jw.search_for_item(query=title)
        item = res["items"][0]

        providers = set()
        for offer in item.get("offers", []):
            if offer.get("monetization_type") == "flatrate":
                providers.add(offer.get("provider_id"))

        # Map provider IDs to readable names
        mapping = jw.get_providers()

        readable = []
        for p in mapping:
            if p["id"] in providers:
                readable.append(p["clear_name"])

        return readable or ["Not available in USA."]
    except:
        return ["Error fetching OTT info."]


# ------------- TELEGRAM SEND -------------
def send(chat_id, text):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": text})


# ------------- MAIN BOT -------------
@app.route(f"/webhook/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    update = request.get_json() or {}
    msg = update.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "")

    if text.startswith("/start"):
        send(chat_id, "Send:\n `/rate <movie or show>`")
        return {"ok": True}

    if text.startswith("/rate"):
        name = text.replace("/rate", "").strip()

        tmdb = tmdb_search(name)

        if not tmdb:
            send(chat_id, "Not found on TMDb.")
            return {"ok": True}

        google = get_google_rating(tmdb["title"])
        imdb_id = get_imdb_id(tmdb["type"], tmdb["id"])
        imdb = get_imdb_rating(imdb_id)
        langs = get_languages(tmdb["type"], tmdb["id"])
        ott = get_ott_usa(tmdb["title"])

        reply = f"""
🎬 {tmdb['title']} ({tmdb['year']})

📍 Google: {google}
⭐ {imdb}

🎤 Dubbed / Languages:
{", ".join(langs)}

📺 Available in USA:
{", ".join(ott)}
"""

        send(chat_id, reply.strip())
        return {"ok": True}

    return {"ok": True}


@app.route("/")
def home():
    return "Running", 200


if __name__ == "__main__":
    app.run()

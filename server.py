import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# -------- ENV VARS ----------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN env var missing")
if not SERPAPI_KEY:
    raise RuntimeError("SERPAPI_KEY env var missing")
if not TMDB_API_KEY:
    raise RuntimeError("TMDB_API_KEY env var missing")
if not OMDB_API_KEY:
    raise RuntimeError("OMDB_API_KEY env var missing")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
SERPAPI_URL = "https://serpapi.com/search"
TMDB_BASE_URL = "https://api.themoviedb.org/3"
OMDB_BASE_URL = "https://www.omdbapi.com/"


# ---------- GOOGLE USERS (SerpAPI) ----------
def get_google_rating(title: str) -> str:
    params = {
        "engine": "google",
        "q": title,
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
        return "Google: error while fetching rating."

    data = r.json()
    kg = data.get("knowledge_graph") or {}
    user_stats = kg.get("user_statistics")

    # Expected: {"platform": "Google users", "statistic": "97% liked this TV show"}
    if isinstance(user_stats, dict):
        platform = user_stats.get("platform", "")
        stat = user_stats.get("statistic", "")
        if platform and stat:
            return f"{platform}: {stat}"

    return "Google: users rating not available."


# ---------- TMDb SEARCH (movie / tv) ----------
def search_tmdb(query: str):
    url = f"{TMDB_BASE_URL}/search/multi"
    params = {
        "api_key": TMDB_API_KEY,
        "query": query,
        "language": "en-US",
        "include_adult": "false",
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print("TMDb search error:", e)
        return None

    results = r.json().get("results") or []
    for item in results:
        media_type = item.get("media_type")
        if media_type in ("movie", "tv"):
            return {
                "tmdb_id": item.get("id"),
                "media_type": media_type,
                "title": item.get("title") or item.get("name"),
                "year": (item.get("release_date") or item.get("first_air_date") or "")[:4],
            }
    return None


# ---------- TMDb DETAILS + OTT + LANGUAGES ----------
def get_tmdb_details(media_type: str, tmdb_id: int):
    details_url = f"{TMDB_BASE_URL}/{media_type}/{tmdb_id}"
    providers_url = f"{TMDB_BASE_URL}/{media_type}/{tmdb_id}/watch/providers"

    spoken_languages = []
    ott_list = []

    # Languages
    try:
        r = requests.get(details_url, params={"api_key": TMDB_API_KEY, "language": "en-US"}, timeout=15)
        r.raise_for_status()
        data = r.json()
        langs = data.get("spoken_languages") or []
        for lang in langs:
            name = lang.get("english_name") or lang.get("name")
            if name and name not in spoken_languages:
                spoken_languages.append(name)
    except Exception as e:
        print("TMDb details error:", e)

    # OTT providers (India)
    try:
        r = requests.get(providers_url, params={"api_key": TMDB_API_KEY}, timeout=15)
        r.raise_for_status()
        pdata = r.json()
        country = pdata.get("results", {}).get("IN") or {}
        for key in ("flatrate", "buy", "rent"):
            providers = country.get(key) or []
            for p in providers:
                name = p.get("provider_name")
                if name and name not in ott_list:
                    ott_list.append(name)
    except Exception as e:
        print("TMDb providers error:", e)

    return {
        "spoken_languages": spoken_languages,
        "ott_platforms": ott_list,
    }


# ---------- TMDb -> IMDb ID ----------
def get_imdb_id(media_type: str, tmdb_id: int):
    url = f"{TMDB_BASE_URL}/{media_type}/{tmdb_id}/external_ids"
    try:
        r = requests.get(url, params={"api_key": TMDB_API_KEY}, timeout=15)
        r.raise_for_status()
        data = r.json()
        imdb_id = data.get("imdb_id")
        return imdb_id
    except Exception as e:
        print("TMDb external_ids error:", e)
        return None


# ---------- IMDb rating via OMDb ----------
def get_imdb_rating(imdb_id: str):
    if not imdb_id:
        return "IMDb: not available."

    params = {"apikey": OMDB_API_KEY, "i": imdb_id}
    try:
        r = requests.get(OMDB_BASE_URL, params=params, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print("OMDb HTTP error:", e)
        return "IMDb: error while fetching rating."

    data = r.json()
    if data.get("Response") != "True":
        return "IMDb: not available."

    rating = data.get("imdbRating")
    votes = data.get("imdbVotes")
    if rating:
        if votes:
            return f"IMDb: {rating}/10 (based on {votes} votes)"
        return f"IMDb: {rating}/10"
    return "IMDb: not available."


# ---------- TELEGRAM SEND ----------
def send_message(chat_id: int, text: str):
    try:
        resp = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=15,
        )
        print("sendMessage:", resp.status_code, resp.text)
    except Exception as e:
        print("Telegram send error:", e)


# ---------- ROUTES ----------
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
            "Google + IMDb + Dubbed + OTT Bot 😈\n\n"
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

        # Step 1: TMDb search
        tmdb_result = search_tmdb(query)
        if not tmdb_result:
            google_info = get_google_rating(query)
            reply = (
                f"Title: {query}\n\n"
                f"{google_info}\n"
                "TMDb/IMDb/OTT data not found."
            )
            send_message(chat_id, reply)
            return jsonify({"ok": True})

        media_type = tmdb_result["media_type"]
        tmdb_id = tmdb_result["tmdb_id"]
        title = tmdb_result["title"]
        year = tmdb_result["year"]

        # Step 2: Google users rating (title + year)
        google_info = get_google_rating(f"{title} {year}" if year else title)

        # Step 3: TMDb details -> languages + OTT
        extra = get_tmdb_details(media_type, tmdb_id)
        langs = extra["spoken_languages"]
        otts = extra["ott_platforms"]

        langs_text = ", ".join(langs) if langs else "Not clear / not listed."
        ott_text = ", ".join(otts) if otts else "No OTT info for India (TMDb)."

        # Step 4: IMDb rating
        imdb_id = get_imdb_id(media_type, tmdb_id)
        imdb_info = get_imdb_rating(imdb_id)

        reply_lines = [
            f"Title: {title} ({year})" if year else f"Title: {title}",
            "",
            google_info,
            imdb_info,
            "",
            "Dubbed / Spoken languages (TMDb):",
            langs_text,
            "",
            "OTT in India (TMDb watch/providers):",
            ott_text,
        ]
        reply = "\n".join(reply_lines)

        send_message(chat_id, reply)
        return jsonify({"ok": True})

    # unknown
    send_message(chat_id, "Unknown command. Use: /rate <title>")
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

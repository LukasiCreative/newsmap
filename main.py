import streamlit as st
import streamlit.components.v1 as components
import requests
import folium
import re
import json
import html
import os
import time
import base64
import xml.etree.ElementTree as ET
from pathlib import Path
from bs4 import BeautifulSoup
from streamlit_folium import st_folium
from concurrent.futures import ThreadPoolExecutor, as_completed

# ================================================================
# PAGE CONFIG
# ================================================================
st.set_page_config(
    page_title="CRISIS COMMAND",
    layout="wide",
    page_icon="🛰️",
    initial_sidebar_state="collapsed"
)

# ================================================================
# HTML HELPER
# ================================================================
def _flatten_html(markup):
    return re.sub(r"(?m)^[ \t]+", "", markup)

# ================================================================
# LOADING PLACEHOLDER (Centered towards the upper part of the screen)
# ================================================================
placeholder = st.empty()
with placeholder:
    st.markdown(
        """
        <div style="display:flex; justify-content:center; align-items:flex-start; padding-top:22vh; height:100vh; background:#262626; box-sizing:border-box;">
            <div style="text-align:center; color:white; font-family:sans-serif;">
                <div style="font-size:52px; margin-bottom:14px;">🛰️</div>
                <h1 style="margin:0 0 8px 0; font-size:26px; font-weight:800; letter-spacing:0.5px;">Loading Crisis Data...</h1>
                <p style="margin:0; color:#9ca3af; font-size:14px;">Please wait while we fetch live intelligence.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ================================================================
# CRITICAL CSS – map fullscreen, ticker fixed overlay at bottom
# ================================================================
st.markdown(
    _flatten_html("""
    <style>
        /* Hide all Streamlit chrome */
        #MainMenu, footer, header, [data-testid="stHeader"],
        [data-testid="stToolbar"], [data-testid="stToolbarActions"],
        [data-testid="stDecoration"], [data-testid="stStatusWidget"],
        [data-testid="stAppDeployButton"], [data-testid="stHeaderActionElements"],
        div[class*="viewerBadge"], div[class*="stDeployButton"],
        div[class*="StatusWidget"], div[class*="Toolbar"], div[class*="Decoration"] {
            display: none !important;
        }

        /* Make the whole app container fill the viewport (dvh accounts for mobile browser chrome) */
        html, body, .stApp, .stAppViewContainer, .stAppViewBlockContainer,
        .main, .main .block-container {
            margin: 0 !important;
            padding: 0 !important;
            width: 100% !important;
            height: 100vh !important;
            height: 100dvh !important;
            overflow: hidden !important;
            background: #262626 !important;
            transform: none !important;
            filter: none !important;
        }

        /* The map container must also fill the viewport */
        div[data-testid="stElementContainer"]:has(iframe.leaflet-container) {
            height: 100vh !important;
            height: 100dvh !important;
            width: 100% !important;
            padding: 0 !important;
            margin: 0 !important;
        }
        iframe.leaflet-container {
            width: 100% !important;
            height: 100% !important;
            display: block !important;
        }

        /* Ticker layer: pinned to the bottom edge of the app window, above the map */
        #news-ticker-overlay {
            position: fixed !important;
            left: 0 !important;
            right: 0 !important;
            bottom: 0 !important;
            width: 100% !important;
            height: clamp(155px, 26dvh, 215px) !important;
            padding-bottom: env(safe-area-inset-bottom, 0px) !important;
            margin: 0 !important;
            z-index: 2147483000 !important;
            pointer-events: auto !important;
            background: #111827 !important;
            box-shadow: 0 -5px 18px rgba(0,0,0,0.6) !important;
        }
        #news-ticker-overlay * { box-sizing: border-box; }
        #ticker-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            height: 28px;
            padding: 0 14px;
            font-family: Arial, sans-serif;
            font-size: 11px;
            font-weight: 900;
            letter-spacing: .5px;
            text-transform: uppercase;
            color: #e5e7eb;
            border-top: 1px solid rgba(255,255,255,.15);
        }
        #ticker-content {
            height: calc(100% - 28px);
            padding: 4px 16px 12px;
            overflow: hidden;
            font-family: Arial, sans-serif;
            opacity: 1;
            transition: opacity .4s ease;
        }
        #ticker-content.fade { opacity: 0; }
        #news-ticker-overlay .headline-top {
            display: flex;
            align-items: center;
            gap: 6px;
            margin-bottom: 4px;
        }
        #news-ticker-overlay .source {
            padding: 2px 6px;
            border-radius: 3px;
            background: #3b70b4;
            color: white;
            font-size: 10px;
            font-weight: 900;
            letter-spacing: .4px;
            text-transform: uppercase;
            white-space: nowrap;
        }
        #news-ticker-overlay .location {
            color: #ff8b8b;
            font-size: 10px;
            font-weight: 800;
            letter-spacing: .4px;
            text-transform: uppercase;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        #news-ticker-overlay .title a {
            color: white;
            font-size: 19px;
            font-weight: 800;
            line-height: 1.3;
            text-decoration: none;
            cursor: pointer;
            display: -webkit-box;
            -webkit-line-clamp: 4;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }
        #news-ticker-overlay .title a:hover,
        #news-ticker-overlay .title a:active { color: #75b9f5; }
        #news-ticker-overlay .banner {
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100%;
            background: white;
            overflow: hidden;
        }
        #news-ticker-overlay .banner img {
            display: block;
            width: 100%;
            height: auto;
            max-height: 100%;
            object-fit: contain;
        }
        #news-ticker-overlay .banner-fallback {
            color: #202938;
            font-family: Georgia, serif;
            font-size: 18px;
            font-weight: 700;
            text-align: center;
            padding: 8px;
        }

        /* The ticker driver component is headless: it only renders the overlay above */
        div[data-testid="stCustomComponentV1"]:not(:has(iframe.leaflet-container)),
        div[data-testid="stElementContainer"]:has(div[data-testid="stCustomComponentV1"]:not(:has(iframe.leaflet-container))) {
            display: none !important;
        }

        /* Map component fills the window */
        div[data-testid="stCustomComponentV1"]:has(iframe.leaflet-container) {
            height: 100vh !important;
            height: 100dvh !important;
            width: 100% !important;
        }
    </style>
    """),
    unsafe_allow_html=True
)

# ================================================================
# CONSTANTS
# ================================================================
WAR_KEYWORDS = [
    "war", "bomb", "explosion", "strike", "missile", "shelling",
    "attack", "military", "air strike", "invasion", "blast", "combat",
    "troop", "forces", "clash", "conflict", "casualty", "offensive",
    "army", "gaza", "ukraine", "israel", "lebanon", "syria", "drone",
    "hezbollah", "houthi"
]
GEO_DATABASE = {
    "Gaza": [31.50, 34.46], "Ukraine": [48.37, 31.16],
    "Israel": [31.04, 34.85], "Lebanon": [33.85, 35.86],
    "Syria": [34.80, 38.99], "Taiwan": [23.69, 120.96],
    "Yemen": [15.55, 48.51], "Russia": [61.52, 105.31],
    "Iran": [32.42, 53.68], "Kyiv": [50.45, 30.52],
    "Beirut": [33.89, 35.50], "Tehran": [35.68, 51.38],
    "Moscow": [55.75, 37.61], "Tel Aviv": [32.08, 34.78],
    "Sweden": [60.12, 18.64], "Iraq": [33.22, 43.68],
    "Egypt": [26.82, 30.80], "Sudan": [12.86, 30.22],
    "Somalia": [5.15, 46.20], "Libya": [26.34, 17.23],
    "Poland": [51.92, 19.15], "Germany": [51.17, 10.45],
    "France": [46.23, 2.21], "Turkey": [38.96, 35.24]
}
REQUEST_HEADERS = {
    "User-Agent": "CrisisCommand/2.0 (+https://gdacs.org; disaster-feed-client)",
    "Accept": "application/json, application/xml, text/xml, application/atom+xml, */*",
}

# ================================================================
# HELPERS
# ================================================================
def clean_text(value):
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def find_location(title, summary):
    text = f"{title} {summary}".lower()
    for name in sorted(GEO_DATABASE, key=len, reverse=True):
        if name.lower() in text:
            return name, GEO_DATABASE[name]
    return "Global", [20.0, 0.0]

def relevant(title, summary):
    text = f"{title} {summary}".lower()
    return any(re.search(rf"\b{re.escape(keyword)}\b", text) for keyword in WAR_KEYWORDS)

def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _xml_local_text(node, *names):
    wanted = {name.lower() for name in names}
    for child in list(node):
        local = child.tag.rsplit("}", 1)[-1].lower()
        if local in wanted and child.text:
            return clean_text(child.text)
    return ""

def _xml_local_attr(node, child_name, attr_name):
    for child in list(node):
        local = child.tag.rsplit("}", 1)[-1].lower()
        if local == child_name.lower():
            return child.attrib.get(attr_name, "")
    return ""

# ================================================================
# FEED CONFIG
# ================================================================
FEED_CONFIG = [
    {"source": "GDACS", "format": "XML/RSS", "feed_url": "https://www.gdacs.org/contentdata/xml/rss.xml", "site_url": "https://gdacs.org", "parser": "gdacs"},
    {"source": "GDACS (NEW)", "format": "XML/RSS", "feed_url": "https://new.gdacs.org/xml/rss.xml", "site_url": "https://new.gdacs.org", "parser": "gdacs"},
    {"source": "RELIEFWEB", "format": "JSON", "feed_url": "https://api.reliefweb.int/v2/reports", "site_url": "https://reliefweb.int", "parser": "reliefweb"},
    {"source": "USGS", "format": "GeoJSON", "feed_url": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson", "site_url": "https://usgs.gov", "parser": "usgs_geojson"},
    {"source": "USGS (ATOM)", "format": "ATOM/XML", "feed_url": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.atom", "site_url": "https://usgs.gov", "parser": "usgs_atom"},
]

# ================================================================
# WORKER FETCH FUNCTIONS (Plain Python functions called in threads)
# ================================================================
def fetch_rss(url, source_name, limit=8, only_relevant=False):
    articles = []
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=6)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        items = list(root.findall(".//item"))
        if not items:
            items = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1].lower() == "entry"]
        for item in items:
            title = _xml_local_text(item, "title")
            description = _xml_local_text(item, "description", "summary", "content")
            link = _xml_local_text(item, "link")
            if not link:
                link = _xml_local_attr(item, "link", "href")
            if not title or not link:
                continue
            if only_relevant and not relevant(title, description):
                continue
            lat = lon = None
            for node in item.iter():
                local = node.tag.rsplit("}", 1)[-1].lower()
                if local in {"point", "where"} and node.text:
                    parts = node.text.replace(",", " ").split()
                    if len(parts) >= 2:
                        lat = _safe_float(parts[0])
                        lon = _safe_float(parts[1])
                        break
                if local in {"lat", "latitude"}:
                    lat = _safe_float(node.text)
                if local in {"long", "lon", "longitude"}:
                    lon = _safe_float(node.text)
            location_name, coords = find_location(title, description)
            if lat is None or lon is None:
                lat, lon = coords
            articles.append({
                "title": title,
                "link": link,
                "location_name": location_name,
                "lat": float(lat),
                "lon": float(lon),
                "source": source_name,
                "summary": description[:190] if description else "Open original source for details.",
                "is_un_data": source_name.upper().startswith("GDACS"),
            })
            if len(articles) >= limit:
                break
    except Exception:
        pass
    return articles

def fetch_reliefweb(limit=15):
    articles = []
    appname = os.getenv("RELIEFWEB_APPNAME", "crisis-command-streamlit")
    url = "https://api.reliefweb.int/v2/reports"
    payload = {
        "limit": limit,
        "sort": ["date:desc"],
        "preset": "latest",
        "query": {"value": "war OR conflict OR attack OR explosion OR military OR missile"},
        "fields": {"include": ["title", "url", "primary_country", "source", "date"]}
    }
    try:
        response = requests.post(url, params={"appname": appname}, json=payload,
                                 headers={**REQUEST_HEADERS, "Content-Type": "application/json"}, timeout=6)
        response.raise_for_status()
        for item in response.json().get("data", []):
            fields = item.get("fields", {})
            title = clean_text(fields.get("title", ""))
            if not title:
                continue
            countries = fields.get("primary_country") or {}
            country_name = countries.get("name") if isinstance(countries, dict) else None
            location = countries.get("location") if isinstance(countries, dict) else {}
            lat = _safe_float(location.get("lat")) if isinstance(location, dict) else None
            lon = _safe_float(location.get("lon")) if isinstance(location, dict) else None
            if lat is None or lon is None:
                if country_name in GEO_DATABASE:
                    lat, lon = GEO_DATABASE[country_name]
                else:
                    lat, lon = 20.0, 0.0
            source = fields.get("source") or {}
            source_name = source.get("shortname", "RELIEFWEB") if isinstance(source, dict) else "RELIEFWEB"
            date_value = fields.get("date") or {}
            date_text = date_value.get("created") if isinstance(date_value, dict) else str(date_value or "")
            summary = "Live ReliefWeb operational intelligence update"
            if date_text:
                summary += f" — {date_text[:19]}"
            articles.append({
                "title": title,
                "link": fields.get("url") or "https://reliefweb.int",
                "location_name": country_name or "Global",
                "lat": float(lat),
                "lon": float(lon),
                "source": str(source_name).upper(),
                "summary": summary,
                "is_un_data": True,
            })
    except Exception:
        pass
    return articles

def fetch_usgs_geojson(limit=20):
    articles = []
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=6)
        response.raise_for_status()
        data = response.json()
        for feature in data.get("features", [])[:limit]:
            props = feature.get("properties") or {}
            geometry = feature.get("geometry") or {}
            coords = geometry.get("coordinates") or []
            if len(coords) < 2:
                continue
            lon = _safe_float(coords[0])
            lat = _safe_float(coords[1])
            if lat is None or lon is None:
                continue
            title = clean_text(props.get("title") or "USGS earthquake")
            link = props.get("url") or "https://earthquake.usgs.gov/"
            magnitude = props.get("mag")
            place = clean_text(props.get("place") or "Global")
            time_ms = props.get("time")
            time_text = ""
            if time_ms:
                time_text = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(time_ms / 1000))
            summary = f"Magnitude {magnitude} — {place}"
            if time_text:
                summary += f" — {time_text}"
            articles.append({
                "title": title,
                "link": link,
                "location_name": place,
                "lat": lat,
                "lon": lon,
                "source": "USGS",
                "summary": summary,
                "is_un_data": True,
            })
    except Exception:
        pass
    return articles

def fetch_usgs_atom(limit=12):
    articles = fetch_rss("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.atom", "USGS", limit=limit, only_relevant=False)
    return [{**article, "is_un_data": True} for article in articles]

# ================================================================
# PARALLEL FETCH AND DEDUPLICATION (Cached at top level)
# ================================================================
@st.cache_data(ttl=120, show_spinner=False)
def fetch_all_crisis_data():
    media_feeds = [
        ("BBC (UK)", "https://feeds.bbci.co.uk/news/rss.xml"),
        ("SKY NEWS", "https://feeds.skynews.com/feeds/rss/home.xml"),
        ("AL JAZEERA", "https://www.aljazeera.com/xml/rss/all.xml"),
        ("THE GUARDIAN", "https://www.theguardian.com/world/rss"),
        ("FRANCE 24", "https://www.france24.com/en/rss"),
        ("SWEDISH ARMED FORCES", "https://www.mynewsdesk.com/forsvarsmakten/latest_news?format=rss"),
        ("CRISIS GROUP", "https://www.crisisgroup.org/rss.xml"),
        ("RADIO FREE EUROPE", "https://www.rferl.org/rss"),
        ("DEFENSE ONE", "https://defenseone.com/feed"),
        ("DEFENSE NEWS", "https://defensenews.com/feed"),
        ("RUSI", "https://rusi.org/feed"),
        ("LONG WAR JOURNAL", "https://longwarjournal.org/feed"),
        ("THE WAR ZONE", "https://www.twz.com/feed"),
        ("CFR", "https://www.cfr.org/rss"),
        ("US STATE DEPT", "https://www.state.gov/rss-feed/state-news/"),
    ]

    combined = []

    # Run all feed requests concurrently in background threads
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = []

        # Primary feeds
        futures.append(executor.submit(fetch_rss, FEED_CONFIG[0]["feed_url"], "GDACS", 8, False))
        futures.append(executor.submit(fetch_rss, FEED_CONFIG[1]["feed_url"], "GDACS", 8, False))
        futures.append(executor.submit(fetch_reliefweb, 15))
        futures.append(executor.submit(fetch_usgs_geojson, 20))
        futures.append(executor.submit(fetch_usgs_atom, 12))

        # Media feeds
        for source, url in media_feeds:
            futures.append(executor.submit(fetch_rss, url, source, 8, True))

        for future in as_completed(futures):
            try:
                res = future.result()
                if res:
                    combined.extend(res)
            except Exception:
                pass

    # Deduplicate alerts
    seen = set()
    mapped = []
    for article in combined:
        title_key = article["title"].strip().lower()
        key = (title_key, round(article["lat"], 3), round(article["lon"], 3))
        if key in seen:
            continue
        seen.add(key)
        mapped.append(article)

    return mapped

# Retrieve all data at once
mapped_alerts = fetch_all_crisis_data()

# ================================================================
# REMOVE LOADING PLACEHOLDER
# ================================================================
placeholder.empty()

# ================================================================
# CHECK BANNER PARAMETER
# ================================================================
banner_idx = st.query_params.get("banner")
if banner_idx is not None:
    try:
        banner_idx = int(banner_idx)
    except:
        banner_idx = None
else:
    banner_idx = None

# ================================================================
# ARTICLE VIEW (if user clicks link in popup – now opens in new tab)
# ================================================================
requested_article = st.query_params.get("article")
if requested_article is not None:
    try:
        article_idx = int(requested_article)
    except (TypeError, ValueError):
        article_idx = None
    article = mapped_alerts[article_idx] if (article_idx is not None and 0 <= article_idx < len(mapped_alerts)) else None

    st.markdown(
        _flatten_html("""
        <style>
        .stApp, .stAppViewContainer, .stAppViewBlockContainer,
        .main, .main .block-container {
            padding: 0 !important;
            margin: 0 !important;
            max-width: 100% !important;
            width: 100% !important;
            background-color: #111827 !important;
        }
        div[data-testid="stButton"] {
            position: fixed !important;
            top: 40px !important;
            left: 40px !important;
            z-index: 2147483647 !important;
            width: auto !important;
        }
        div[data-testid="stButton"] button {
            background-color: #181d29 !important;
            color: #ffffff !important;
            border: 2px solid rgba(255,255,255,.18) !important;
            border-radius: 8px !important;
            padding: 10px 20px !important;
            font-size: 13px !important;
            font-weight: 800 !important;
            font-family: Arial, sans-serif !important;
            box-shadow: 0 6px 20px rgba(0,0,0,.5) !important;
        }
        .article-wrap {
            max-width: 680px;
            margin: 120px auto 40px;
            padding: 0 24px;
            font-family: Arial, sans-serif;
            color: #e5e7eb;
        }
        .article-source-pill {
            display: inline-block;
            background: #3b70b4;
            color: white;
            border-radius: 5px;
            padding: 5px 10px;
            font-size: 11px;
            font-weight: 800;
            margin-bottom: 12px;
        }
        .article-location {
            color: #75b9f5;
            font-size: 13px;
            font-weight: 900;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }
        .article-title {
            color: white;
            font-size: 28px;
            font-weight: 800;
            line-height: 1.25;
            margin-bottom: 18px;
        }
        .article-summary {
            color: #aab5c7;
            font-size: 16px;
            line-height: 1.6;
            margin-bottom: 30px;
        }
        .article-open-btn {
            display: inline-block;
            background: #3182ce;
            color: white;
            text-decoration: none !important;
            font-weight: 800;
            font-size: 14px;
            padding: 12px 24px;
            border-radius: 8px;
            font-family: Arial, sans-serif;
            cursor: pointer;
        }
        </style>
        """),
        unsafe_allow_html=True
    )

    if st.button("← Back to Map", key="back_to_map"):
        st.query_params.clear()
        st.rerun()

    if article:
        article_url = str(article["link"])
        st.markdown(
            '<div class="article-wrap">'
            f'<div class="article-source-pill">{html.escape(str(article["source"]))}</div>'
            f'<div class="article-location">📍 {html.escape(str(article["location_name"]))}</div>'
            f'<div class="article-title">{html.escape(str(article["title"]))}</div>'
            f'<div class="article-summary">{html.escape(str(article["summary"]))}</div>'
            f'<a class="article-open-btn" href="{html.escape(article_url)}" target="_blank">Open Full Article Source ↗</a>'
            '</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div class="article-wrap">'
            '<div class="article-title">Article not found</div>'
            '<div class="article-summary">This item may have expired from the live tracking logs.</div>'
            '</div>',
            unsafe_allow_html=True
        )
    st.stop()

# ================================================================
# TICKER DATA (red pins only)
# ================================================================
ticker_items = []
for alert_idx, item in enumerate(mapped_alerts):
    if item.get("is_un_data"):
        continue
    title_text = BeautifulSoup(str(item.get("title", "")), "html.parser").get_text()
    title_text = clean_text(title_text)
    source_text = clean_text(str(item.get("source", "")))
    location_text = clean_text(str(item.get("location_name", "")))
    if not title_text:
        continue
    ticker_items.append({
        "title": title_text,
        "source": source_text,
        "location": location_text,
        "url": f"?article={alert_idx}"
    })

# ================================================================
# BANNER IMAGE
# ================================================================
BANNER_PATH = Path(__file__).resolve().parent / "infriendshipwith.png"
banner_data = ""
if BANNER_PATH.exists():
    try:
        banner_bytes = BANNER_PATH.read_bytes()
        banner_data = "data:image/png;base64," + base64.b64encode(banner_bytes).decode("ascii")
    except Exception:
        banner_data = ""

# ================================================================
# BUILD MAP – ALWAYS DARK TILES & FIT ALL RED PINS
# ================================================================
live_pin_items = []
for alert_idx, item in enumerate(mapped_alerts):
    try:
        lat = float(item.get("lat"))
        lon = float(item.get("lon"))
        if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
            live_pin_items.append((alert_idx, item, lat, lon))
    except (TypeError, ValueError):
        continue

# Extract ALL red pins (media / crisis news pins)
red_pins = [p for p in live_pin_items if not p[1]["is_un_data"]]
target_pins = red_pins if red_pins else live_pin_items

# Calculate bounding box encompassing ALL target pins
init_lat, init_lon, init_zoom = 20.0, 0.0, 2
bounds_js = None

banner_article = None
if banner_idx is not None and 0 <= banner_idx < len(mapped_alerts):
    banner_article = mapped_alerts[banner_idx]

if banner_article is not None:
    init_lat, init_lon = banner_article["lat"], banner_article["lon"]
    init_zoom = 8
    bounds_js = f"__mapObj.setView([{init_lat}, {init_lon}], 8);"
elif target_pins:
    lats = [p[2] for p in target_pins]
    lons = [p[3] for p in target_pins]
    init_lat = (min(lats) + max(lats)) / 2.0
    init_lon = (min(lons) + max(lons)) / 2.0
    
    if len(target_pins) == 1:
        init_zoom = 7
        bounds_js = f"__mapObj.setView([{lats[0]}, {lons[0]}], 7);"
    else:
        min_lat = min(lats)
        max_lat = max(lats)
        min_lon = min(lons)
        max_lon = max(lons)
        
        # Add a 6% buffer around all sides to guarantee no pin touches edges
        lat_span = max(0.5, max_lat - min_lat)
        lon_span = max(0.5, max_lon - min_lon)
        south = max(-85.0, min_lat - (lat_span * 0.06))
        north = min(85.0, max_lat + (lat_span * 0.06))
        west = max(-180.0, min_lon - (lon_span * 0.06))
        east = min(180.0, max_lon + (lon_span * 0.06))
        
        # paddingTopLeft: 40px margin, paddingBottomRight: 220px to account for the ticker overlay
        bounds_js = f"__mapObj.fitBounds([[{south},{west}],[{north},{east}]],{{paddingTopLeft:[40,40],paddingBottomRight:[40,220]}});"

m = folium.Map(
    location=[init_lat, init_lon],
    zoom_start=init_zoom,
    min_zoom=2,
    zoom_control=False,
    scrollWheelZoom=True,
    touchZoom=True
)

folium.TileLayer(
    tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    attr="&copy; OpenStreetMap &copy; CARTO",
    name="Dark Matter",
    subdomains="abcd",
    no_wrap=True
).add_to(m)

m.get_root().html.add_child(
    folium.Element("""
    <style>
        html, body { background: #262626 !important; margin: 0; padding: 0; }
        .leaflet-container { background: #262626 !important; }
    </style>
    """)
)

# --- Add markers; clicking a pin pushes its headline into the ticker ---
for alert_idx, item, lat, lon in live_pin_items:
    if item["is_un_data"]:
        marker_color = "#3182ce"
        border_color = "#63b3ed"
    else:
        marker_color = "#ff4b4b"
        border_color = "#ff8080"

    # Popup link opens article
    popup_html = (
        '<div style="font-family:sans-serif;font-size:12px;width:240px;color:#1a1f2c;line-height:1.4;">'
        f'<span style="color:#718096;font-weight:800;font-size:10px;text-transform:uppercase;">'
        f'📍 {html.escape(str(item["location_name"]))} — {html.escape(str(item["source"]))}'
        '</span><br>'
        f'<a href="?article={alert_idx}" target="_top" '
        f'style="text-decoration:none;font-weight:700;color:{marker_color};display:inline-block;margin-top:4px;cursor:pointer;">'
        f'{html.escape(str(item["title"]))} ↗'
        '</a>'
        '</div>'
    )

    marker = folium.CircleMarker(
        location=[lat, lon],
        radius=11 if item["is_un_data"] else 9,
        popup=folium.Popup(popup_html, max_width=280),
        color=border_color,
        fill=True,
        fill_color=marker_color,
        fill_opacity=0.75
    )
    marker.add_to(m)

# --- Ensure all red pins fit inside the view immediately on start ---
if live_pin_items and bounds_js:
    map_var = m.get_name()
    js_cmd = bounds_js.replace("__mapObj", map_var)
    fit_script = f"""
    <script>
    function __fitRedPins() {{
        try {{
            var __mapObj = {map_var};
            if (__mapObj) {{
                __mapObj.invalidateSize();
                {js_cmd}
            }}
        }} catch(e) {{}}
    }}
    window.addEventListener('DOMContentLoaded', __fitRedPins);
    window.addEventListener('load', function() {{
        __fitRedPins();
        setTimeout(__fitRedPins, 150);
        setTimeout(__fitRedPins, 500);
        setTimeout(__fitRedPins, 1000);
    }});
    window.addEventListener('resize', __fitRedPins);
    if (window.ResizeObserver) {{
        new ResizeObserver(__fitRedPins).observe(document.body);
    }}
    </script>
    """
    m.get_root().html.add_child(folium.Element(fit_script))

# ================================================================
# RENDER: MAP FIRST, TICKER OVERLAY AT BOTTOM
# ================================================================

st_folium(
    m,
    width="100%",
    height=600,
    returned_objects=[],
    key="tactical_map_flush_v33"
)

# Ticker – fixed overlay at bottom
ticker_json = json.dumps(ticker_items, ensure_ascii=False)
pin_lookup_json = json.dumps({
    str(alert_idx): {
        "title": clean_text(str(item.get("title", ""))),
        "source": clean_text(str(item.get("source", ""))),
        "location": clean_text(str(item.get("location_name", ""))),
        "url": f"?article={alert_idx}",
    }
    for alert_idx, item in enumerate(mapped_alerts)
}, ensure_ascii=False)
banner_json = json.dumps(banner_data)

banner_article_json = None
if banner_idx is not None and 0 <= banner_idx < len(mapped_alerts):
    banner_article_json = json.dumps({
        "title": clean_text(mapped_alerts[banner_idx]["title"]),
        "source": clean_text(mapped_alerts[banner_idx]["source"]),
        "location": clean_text(mapped_alerts[banner_idx]["location_name"]),
        "url": f"?article={banner_idx}"
    })

components.html(
    f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body>
        <script>
            // This component is headless: Streamlit sandboxes component iframes so
            // links inside them cannot navigate the app window. The ticker is
            // therefore built in the app document itself, where a click on a
            // headline navigates the whole window (fullscreen article view).
            const frame = window.frameElement;
            const doc = frame ? frame.ownerDocument : document;
            const win = doc.defaultView;

            function appUrl(query) {{
                return win.location.origin + win.location.pathname + query;
            }}

            function buildOverlay() {{
                let layer = doc.getElementById("news-ticker-overlay");
                if (!layer) {{
                    layer = doc.createElement("div");
                    layer.id = "news-ticker-overlay";
                    doc.body.appendChild(layer);
                }}
                layer.innerHTML =
                    '<div id="ticker-header">' +
                    '<span>🛰️ LIVE DATA SOURCES</span>' +
                    '<span>LIVE PIN HEADLINES</span>' +
                    '</div><div id="ticker-content"></div>';
                return layer;
            }}

            const overlay = buildOverlay();
            const content = doc.getElementById("ticker-content");

            const headlines = {ticker_json};
            const pinLookup = {pin_lookup_json};
            const banner = {banner_json};
            const bannerArticle = {banner_article_json if banner_article_json is not None else 'null'};
            const DISPLAY_TIME = 7000;   // 7 seconds per item
            const FADE_TIME = 400;
            let currentIndex = 0;
            let holdUntil = 0;   // pauses rotation while a clicked pin is shown

            function renderHeadline(item) {{
                const wrapper = doc.createElement("div");
                wrapper.className = "headline";
                const top = doc.createElement("div");
                top.className = "headline-top";
                const source = doc.createElement("span");
                source.className = "source";
                source.textContent = item.source;
                const location = doc.createElement("span");
                location.className = "location";
                location.textContent = "📍 " + item.location;
                top.appendChild(source);
                top.appendChild(location);
                const title = doc.createElement("div");
                title.className = "title";
                const link = doc.createElement("a");
                link.href = appUrl(item.url);
                link.textContent = item.title + " ↗";
                title.appendChild(link);
                wrapper.appendChild(top);
                wrapper.appendChild(title);
                return wrapper;
            }}

            function renderBanner() {{
                const wrapper = doc.createElement("div");
                wrapper.className = "banner";
                if (banner) {{
                    const image = doc.createElement("img");
                    image.src = banner;
                    image.alt = "In friendship with Air Brussels Times";
                    wrapper.appendChild(image);
                }} else {{
                    const fallback = doc.createElement("div");
                    fallback.className = "banner-fallback";
                    fallback.textContent = "In friendship with: Air Brussels Times";
                    wrapper.appendChild(fallback);
                }}
                return wrapper;
            }}

            function setContent(node) {{
                content.innerHTML = "";
                content.appendChild(node);
            }}

            // A pin click on the map pushes that headline into the ticker.
            function showPinHeadline(index) {{
                const item = pinLookup[String(index)];
                if (!item) return;
                holdUntil = Date.now() + 15000;
                content.classList.remove("fade");
                setContent(renderHeadline(item));
            }}

            // Full-window navigation, driven from the app document so the article
            // page replaces the map instead of opening in a sandboxed frame.
            function navigateApp(query) {{
                const url = appUrl(query);
                const link = doc.createElement("a");
                link.href = url;
                link.style.display = "none";
                doc.body.appendChild(link);
                link.click();
                setTimeout(function () {{
                    link.remove();
                    if (win.location.search.indexOf(query.replace("?", "")) === -1) {{
                        window.open(url, "_blank");
                    }}
                }}, 400);
            }}

            // The map is a sibling iframe: watch it for an open popup, mirror the
            // headline down here and make its link open the fullscreen article.
            let lastPopupIndex = null;
            function popupLink() {{
                let frames;
                try {{
                    frames = win.frames;
                }} catch (e) {{
                    return null;
                }}
                for (let i = 0; i < frames.length; i++) {{
                    try {{
                        const link = frames[i].document.querySelector(
                            '.leaflet-popup-content a[href^="?article="]'
                        );
                        if (link) return link;
                    }} catch (e) {{}}
                }}
                return null;
            }}

            setInterval(function () {{
                const link = popupLink();
                const idx = link
                    ? parseInt(link.getAttribute("href").split("=")[1], 10)
                    : null;
                if (link && !link.dataset.crisisBound) {{
                    link.dataset.crisisBound = "1";
                    link.addEventListener("click", function (event) {{
                        event.preventDefault();
                        navigateApp(link.getAttribute("href"));
                    }});
                }}
                if (idx === lastPopupIndex) return;
                lastPopupIndex = idx;
                if (idx !== null && !isNaN(idx)) showPinHeadline(idx);
            }}, 400);

            function displayCurrent() {{
                if (Date.now() < holdUntil) return;
                content.classList.add("fade");
                setTimeout(function () {{
                    if (currentIndex < headlines.length) {{
                        setContent(renderHeadline(headlines[currentIndex]));
                    }} else {{
                        setContent(renderBanner());
                    }}
                    content.classList.remove("fade");
                }}, FADE_TIME);
            }}

            function startRotation() {{
                setInterval(function () {{
                    currentIndex++;
                    if (currentIndex >= headlines.length + 1) currentIndex = 0;
                    displayCurrent();
                }}, DISPLAY_TIME);
            }}

            if (bannerArticle) {{
                setContent(renderHeadline(bannerArticle));
                setTimeout(function () {{
                    currentIndex = 0;
                    displayCurrent();
                    startRotation();
                }}, DISPLAY_TIME);
            }} else {{
                if (headlines.length > 0) {{
                    setContent(renderHeadline(headlines[0]));
                    currentIndex = 0;
                }} else {{
                    setContent(renderBanner());
                    currentIndex = headlines.length;
                }}
                startRotation();
            }}
        </script>
    </body>
    </html>
    """,
    height=0,
    scrolling=False
)

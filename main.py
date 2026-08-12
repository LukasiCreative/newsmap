import streamlit as st
import requests, folium, re, json, html, os, time
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from streamlit_folium import st_folium

# Hide the "Hosted with Streamlit" footer button and main menu
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .viewerBadge_container__6V6X0 {display: none !important;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)


st.set_page_config(page_title="CRISIS COMMAND", layout="wide", page_icon="🛰️", initial_sidebar_state="collapsed")

# ─── SECTION 1: SYSTEM STYLES (ELIMINATING ALL SPACING GAPS) ───
st.markdown("""
    <style>
        html, body {background-color: #262626 !important;}
        #MainMenu, footer {visibility: hidden; display: none !important;}
        header, [data-testid="stHeader"] {display: none !important; height: 0px !important; min-height: 0px !important;}

        .stApp, .stAppViewContainer, .stAppViewBlockContainer, .main, .main .block-container {
            padding: 0px !important; margin: 0px !important; max-width: 100% !important; width: 100% !important;
            background-color: #262626 !important;
        }

        div[data-testid="stAppViewContainer"] {padding-top: 0px !important; margin-top: 0px !important; background-color: #262626 !important;}
        div[data-testid="stAppViewContainer"] > .main {padding-top: 0px !important; margin-top: 0px !important;}
        div[data-testid="stMainBlockContainer"] {padding-top: 0px !important; margin-top: 0px !important; background-color: #262626 !important;}
        .main .block-container {padding-top: 0px !important; margin-top: 0px !important;}

        div[data-testid="stVerticalBlock"], 
        div[data-testid="stElementContainer"], 
        div[data-testid="stVerticalBlockInsideExecutionFlow"] {
            padding-left: 0rem !important; padding-right: 0rem !important;
            margin-left: 0rem !important; margin-right: 0rem !important;
            padding-top: 0px !important; padding-bottom: 0px !important;
            margin-top: 0px !important; margin-bottom: 0px !important;
            gap: 0px !important; width: 100% !important;
            background-color: transparent !important;
        }

        [data-testid="stElementContainer"]:first-child {margin-top: 0px !important; padding-top: 0px !important;}
        div[data-testid="stMainBlockContainer"] {padding-top: 0px !important;}

        div[data-testid="stCustomComponentV1"], iframe {
            width: 100vw !important; height: 100vh !important; 
            margin: 0px !important; padding: 0px !important; border: none !important;
            background-color: #262626 !important;
            background: #262626 !important;
            color-scheme: dark !important;
        }

        div[data-testid="stButton"] button {
            background-color: #000000 !important;
            color: #ffffff !important;
            border: 1px solid #333333 !important;
            border-radius: 6px !important;
            font-weight: 700 !important;
            font-size: 13px !important;
            letter-spacing: 0.5px !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.6) !important;
            transition: all 0.2s ease !important;
        }
        div[data-testid="stButton"] button:hover {
            background-color: #1a1a1a !important;
            color: #ffffff !important;
            border-color: #666666 !important;
        }
        div[data-testid="stButton"] button:focus, div[data-testid="stButton"] button:active {
            background-color: #111111 !important;
            color: #ffffff !important;
            box-shadow: none !important;
        }

        .threat-heading { color: #ffffff; font-size: 16px; line-height: 1; font-weight: 900; letter-spacing: .7px; margin: 0 0 9px 5px; text-shadow: 0 2px 5px rgba(0,0,0,.8); }

        .threat-card {
            display: block; box-sizing: border-box; min-height: 104px; width: 100%;
            background: rgba(24, 29, 41, .98); border: 2px solid rgba(255,255,255,.12);
            border-left: 6px solid #3182ce; border-radius: 8px; padding: 13px 18px 12px 18px;
            box-shadow: 0 7px 28px rgba(0,0,0,.55);
        }
        .threat-card.media { border-left-color: #e05252; }
        .threat-source { float: right; color: #fff; background: #3b70b4; border-radius: 5px; padding: 5px 9px; font-size: 10px; font-weight: 800; letter-spacing: .3px; }
        .threat-card.media .threat-source { background: #6b7280; }
        .threat-location { color: #75b9f5; font-size: 12px; line-height: 1.1; font-weight: 900; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px; }
        .threat-card.media .threat-location { color: #ff8b8b; }
        .threat-title { color: #ffffff; font-size: 19px; line-height: 1.18; font-weight: 800; margin-right: 120px; }
        .threat-title a { color: #ffffff !important; text-decoration: none !important; }
        .threat-summary { color: #aab5c7; font-size: 12px; line-height: 1.3; margin-top: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    </style>
""", unsafe_allow_html=True)

WAR_KEYWORDS = ["war", "bomb", "explosion", "strike", "missile", "shelling", "attack", "military", "air strike",
                "invasion", "blast", "combat", "troop", "forces", "clash", "conflict", "casualty", "offensive", "army",
                "gaza", "ukraine", "israel", "lebanon", "syria", "drone", "hezbollah", "houthi"]

GEO_DATABASE = {"Gaza": [31.50, 34.46], "Ukraine": [48.37, 31.16], "Israel": [31.04, 34.85], "Lebanon": [33.85, 35.86],
                "Syria": [34.80, 38.99], "Taiwan": [23.69, 120.96], "Yemen": [15.55, 48.51], "Russia": [61.52, 105.31],
                "Iran": [32.42, 53.68], "Kyiv": [50.45, 30.52], "Beirut": [33.89, 35.50], "Tehran": [35.68, 51.38],
                "Moscow": [55.75, 37.61], "Tel Aviv": [32.08, 34.78], "Sweden": [60.12, 18.64], "Iraq": [33.22, 43.68],
                "Egypt": [26.82, 30.80], "Sudan": [12.86, 30.22], "Somalia": [5.15, 46.20], "Libya": [26.34, 17.23],
                "Poland": [51.92, 19.15], "Germany": [51.17, 10.45], "France": [46.23, 2.21], "Turkey": [38.96, 35.24]}

REQUEST_HEADERS = {
    "User-Agent": "CrisisCommand/2.0 (+https://gdacs.org; disaster-feed-client)",
    "Accept": "application/json, application/xml, text/xml, application/atom+xml, */*",
}


def clean_text(value):
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def find_location(title, summary):
    text = f"{title} {summary}".lower()
    for name in sorted(GEO_DATABASE, key=len, reverse=True):
        if name.lower() in text: return name, GEO_DATABASE[name]
    return "Global", [20.0, 0.0]


def relevant(title, summary):
    text = f"{title} {summary}".lower()
    return any(keyword in text for keyword in WAR_KEYWORDS)


def has_actual_headline(title, location_name=""):
    title_str = (title or "").strip()
    loc_str = (location_name or "").strip()
    combined = f"{title_str} {loc_str}".strip()
    if not combined:
        return False
    # Extract all alphabetical words of length >= 2
    words = re.findall(r'[a-zA-Z]{2,}', combined)
    non_meaningful = {
        "m", "km", "mi", "lat", "lon", "xml", "atom", "rss", "null", "undefined", "utc", "geojson", "usgs",
        "of", "in", "at", "and", "or", "the", "a", "an", "deg", "degree", "se", "sw", "ne", "nw",
        "nne", "ene", "ese", "sse", "ssw", "wsw", "wnw", "nnw", "global", "event"
    }
    meaningful_words = [w for w in words if w.lower() not in non_meaningful]
    # Must have at least 2 meaningful words
    return len(meaningful_words) >= 2


def format_usgs_title_and_place(raw_title, raw_place="", mag=None):
    title_str = clean_text(raw_title or "")
    place_str = clean_text(raw_place or "")

    # If place is not provided directly, extract it from title "M 1.5 - 3km SW of Anza, CA"
    if not place_str and " - " in title_str:
        parts = title_str.split(" - ", 1)
        place_str = parts[1].strip()

    # Extract magnitude from title if not given
    if mag is None:
        mag_match = re.search(r'\bM\s*([\d\.\-]+)\b', title_str, re.IGNORECASE)
        if mag_match:
            try:
                mag = float(mag_match.group(1))
            except ValueError:
                mag = None

    # Strip coordinates or purely numeric patterns from place_str
    if re.match(r'^[\d\s.,\-\+°]+$', place_str):
        place_str = ""

    # Find meaningful alphabetic words in place_str (length >= 2)
    words = re.findall(r'[a-zA-Z]{2,}', place_str)
    cardinals_and_units = {
        "km", "mi", "lat", "lon", "n", "s", "e", "w", "ne", "nw", "se", "sw",
        "nne", "ene", "ese", "sse", "ssw", "wsw", "wnw", "nnw", "of", "deg", "degree",
        "utc", "m", "atom", "rss", "geojson", "global", "event"
    }
    meaningful_words = [w for w in words if w.lower() not in cardinals_and_units]

    # If there are no real place words, reject this USGS event!
    if not meaningful_words:
        return None, None

    # We have a valid location with actual words!
    loc_display = place_str

    # Explicitly construct clean headline containing "Earthquake"
    if mag is not None and str(mag) != "None":
        clean_title = f"M{mag} Earthquake - {loc_display}"
    else:
        clean_title = f"Earthquake - {loc_display}"

    return clean_title, loc_display


def get_pin_colors(item):
    text = f"{item.get('title', '')} {item.get('location_name', '')} {item.get('summary', '')}".lower()

    # Check if this item is related to war, bomb, missile, or armed conflict
    is_conflict = any(k in text for k in WAR_KEYWORDS) or bool(re.search(
        r'\b(war|bomb|bombs|missile|missiles|strike|strikes|attack|attacks|explosion|blast|combat|invasion|military|shelling|drone|drones|air strike)\b',
        text))

    if is_conflict:
        # Bright red strictly for war, bomb, and missile pins
        return "#ef4444", "#f87171"

    if re.search(r'\bred\b', text):
        # Non-conflict pins labeled red (e.g. GDACS Red alert) -> Much darker red
        return "#7f1d1d", "#991b1b"
    elif re.search(r'\bgreen\b', text):
        return "#22c55e", "#4ade80"
    elif re.search(r'\borange\b', text):
        return "#f97316", "#fb923c"
    elif re.search(r'\b(yellow|amber)\b', text):
        return "#eab308", "#fde047"
    elif re.search(r'\bblue\b', text):
        return "#3b82f6", "#60a5fa"
    elif re.search(r'\b(purple|violet)\b', text):
        return "#a855f7", "#c084fc"
    elif re.search(r'\b(pink|magenta)\b', text):
        return "#ec4899", "#f472b6"
    elif re.search(r'\b(gray|grey)\b', text):
        return "#6b7280", "#9ca3af"

    if item.get("is_un_data"):
        return "#3182ce", "#63b3ed"
    return "#3b82f6", "#60a5fa"


# ─── SECTION 2: VERIFIED DISASTER DATA FEEDS ───
FEED_CONFIG = [
    {
        "source": "GDACS",
        "format": "XML/RSS",
        "feed_url": "https://www.gdacs.org/contentdata/xml/rss.xml",
        "site_url": "https://gdacs.org",
        "parser": "gdacs",
    },
    {
        "source": "GDACS (NEW)",
        "format": "XML/RSS",
        "feed_url": "https://new.gdacs.org/xml/rss.xml",
        "site_url": "https://new.gdacs.org",
        "parser": "gdacs",
    },
    {
        "source": "RELIEFWEB",
        "format": "JSON",
        "feed_url": "https://api.reliefweb.int/v2/reports",
        "site_url": "https://reliefweb.int",
        "parser": "reliefweb",
    },
    {
        "source": "USGS",
        "format": "GeoJSON",
        "feed_url": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson",
        "site_url": "https://usgs.gov",
        "parser": "usgs_geojson",
    },
    {
        "source": "USGS (ATOM)",
        "format": "ATOM/XML",
        "feed_url": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.atom",
        "site_url": "https://usgs.gov",
        "parser": "usgs_atom",
    },
]


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


def extract_direct_article_url(item):
    links = []
    for child in list(item):
        local = child.tag.rsplit("}", 1)[-1].lower()
        if local == "link":
            href = child.attrib.get("href", "").strip()
            text = (child.text or "").strip()
            rel = child.attrib.get("rel", "").lower()
            if href.startswith("http"):
                if rel in {"alternate", ""} or not rel:
                    links.insert(0, href)
                else:
                    links.append(href)
            elif text.startswith("http"):
                links.append(text)
        elif local in {"guid", "id"}:
            text = (child.text or "").strip()
            if text.startswith("http"):
                links.append(text)

    for l in links:
        if not any(l.lower().endswith(ext) for ext in [".xml", ".atom", "/rss", "/feed", ".rss"]):
            return l
    return links[0] if links else ""


@st.cache_data(ttl=120, show_spinner=False)
def fetch_rss(url, source_name, limit=8, only_relevant=False):
    articles = []
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        items = list(root.findall(".//item"))
        if not items:
            items = [n for n in root.iter() if n.tag.rsplit("}", 1)[-1].lower() == "entry"]

        for item in items:
            title = _xml_local_text(item, "title")
            description = _xml_local_text(item, "description", "summary", "content")
            link = extract_direct_article_url(item)
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
                        lat = _safe_float(parts[0]);
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
                "is_un_data": source_name.upper().startswith("GDACS") or source_name.upper().startswith("RELIEFWEB"),
            })
            if len(articles) >= limit:
                break
    except Exception:
        pass
    return articles


@st.cache_data(ttl=120, show_spinner=False)
def fetch_reliefweb(limit=15):
    articles = []
    appname = os.getenv("RELIEFWEB_APPNAME", "crisis-command-streamlit")
    url = "https://api.reliefweb.int/v2/reports"
    payload = {
        "limit": limit,
        "sort": ["date:desc"],
        "preset": "latest",
        "query": {"value": "war OR conflict OR attack OR explosion OR military OR missile"},
        "fields": {"include": ["title", "url", "primary_country", "source", "date"]},
    }
    try:
        response = requests.post(
            url,
            params={"appname": appname},
            json=payload,
            headers={**REQUEST_HEADERS, "Content-Type": "application/json"},
            timeout=15,
        )
        response.raise_for_status()
        for item in response.json().get("data", []):
            fields = item.get("fields", {})
            title = clean_text(fields.get("title", ""))
            if not title:
                continue
            report_url = fields.get("url") or f"https://reliefweb.int/node/{item.get('id')}"
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
            summary = f"Live ReliefWeb operational intelligence update{(' — ' + date_text[:19]) if date_text else ''}."
            articles.append({
                "title": title,
                "link": report_url,
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


@st.cache_data(ttl=60, show_spinner=False)
def fetch_usgs_geojson(limit=25):
    articles = []
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()
        for feature in data.get("features", []):
            props = feature.get("properties") or {}
            coords = ((feature.get("geometry") or {}).get("coordinates") or [])
            if len(coords) < 2:
                continue
            lon, lat = _safe_float(coords[0]), _safe_float(coords[1])
            if lat is None or lon is None:
                continue

            raw_title = props.get("title") or ""
            raw_place = props.get("place") or ""
            magnitude = props.get("mag")

            title, place = format_usgs_title_and_place(raw_title, raw_place, magnitude)
            if not title or not place:
                continue

            feature_id = feature.get("id") or ""
            link = props.get("url") or (
                f"https://earthquake.usgs.gov/earthquakes/eventpage/{feature_id}/executive" if feature_id else "https://earthquake.usgs.gov/earthquakes/")
            time_ms = props.get("time")
            time_text = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(time_ms / 1000)) if time_ms else ""
            summary = f"Magnitude {magnitude if magnitude is not None else 'N/A'} — {place}{(' — ' + time_text) if time_text else ''}"

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
            if len(articles) >= limit:
                break
    except Exception:
        pass
    return articles


@st.cache_data(ttl=60, show_spinner=False)
def fetch_usgs_atom(limit=12):
    raw_articles = fetch_rss(
        "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.atom",
        "USGS",
        limit=limit * 2,
        only_relevant=False,
    )
    formatted = []
    for art in raw_articles:
        raw_title = art.get("title", "")
        raw_place = art.get("location_name", "")
        if raw_place == "Global":
            raw_place = ""
        title, place = format_usgs_title_and_place(raw_title, raw_place)
        if not title or not place:
            continue
        art["title"] = title
        art["location_name"] = place
        art["summary"] = f"{title} — {art.get('summary', '')}"
        formatted.append(art)
        if len(formatted) >= limit:
            break
    return formatted


def fetch_live_media():
    all_articles = []
    feeds = [
        ("BBC (UK)", "https://feeds.bbci.co.uk/news/rss.xml"),
        ("SKY NEWS", "https://feeds.skynews.com/feeds/rss/home.xml"),
        ("AL JAZEERA", "https://www.aljazeera.com/xml/rss/all.xml"),
        ("THE GUARDIAN", "https://www.theguardian.com/world/rss"),
        ("FRANCE 24", "https://www.france24.com/en/rss"),
    ]
    for source, url in feeds:
        all_articles.extend(fetch_rss(url, source, limit=3, only_relevant=True))
    seen, unique = set(), []
    for article in all_articles:
        key = article["title"].strip().lower()
        if key not in seen:
            seen.add(key);
            unique.append(article)
    return unique


# --- Execute Ingestion Pipelines ---
feed_articles = []
feed_articles.extend(fetch_rss(FEED_CONFIG[0]["feed_url"], "GDACS", limit=8))
feed_articles.extend(fetch_rss(FEED_CONFIG[1]["feed_url"], "GDACS", limit=8))
feed_articles.extend(fetch_reliefweb(limit=15))
feed_articles.extend(fetch_usgs_geojson(limit=25))
feed_articles.extend(fetch_usgs_atom(limit=12))
feed_articles.extend(fetch_live_media())

# De-duplicate across formats & strictly enforce headline filter (words required)
seen, mapped_alerts = set(), []
for article in feed_articles:
    t = article.get("title", "")
    loc = article.get("location_name", "")
    if not has_actual_headline(t, loc):
        continue
    key = (t.strip().lower(), round(article["lat"], 3), round(article["lon"], 3))
    if key in seen:
        continue
    seen.add(key)
    mapped_alerts.append(article)


# ─── SERVER-SIDE ARTICLE CONTENT SCRAPER ───
@st.cache_data(ttl=300, show_spinner=False)
def fetch_full_article_content(url):
    try:
        res = requests.get(url, headers=REQUEST_HEADERS, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        # Strip scripts, styles, navs, footers
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "aside", "form"]):
            tag.decompose()

        # Find main content container
        main_body = soup.find("article") or soup.find("main") or soup.find(
            class_=re.compile(r"content|article|body|report", re.I)) or soup.body
        if not main_body:
            return []

        paragraphs = []
        for p in main_body.find_all("p"):
            text = clean_text(p.get_text())
            if len(text) > 40 and not any(skip in text.lower() for skip in
                                          ["cookies", "subscribe", "rights reserved", "privacy policy", "all rights"]):
                paragraphs.append(text)

        return paragraphs[:12]
    except Exception:
        return []


# ─── ARTICLE VIEW (Direct-to-source iframe, no landing/middle page) ───
requested_article = st.query_params.get("article")
if requested_article is not None:
    try:
        article_idx = int(requested_article)
    except (TypeError, ValueError):
        article_idx = None
    article = mapped_alerts[article_idx] if article_idx is not None and 0 <= article_idx < len(mapped_alerts) else None

    # Global styles: full-bleed iframe showing the actual source article,
    # with a small vertical "back to map" tab fixed to the middle-left of the screen.
    st.markdown("""
    <style>
        html, body, .stApp, .stAppViewContainer, .stAppViewBlockContainer, .main, .main .block-container {
            padding: 0px !important; margin: 0px !important; max-width: 100% !important; width: 100% !important;
            height: 100vh !important; overflow: hidden !important;
            background-color: #111827 !important;
        }

        .article-frame-wrap {
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            width: 100vw !important;
            height: 100vh !important;
            background: #ffffff !important;
            z-index: 2147483647 !important;
        }

        .article-iframe {
            width: 100% !important;
            height: 100% !important;
            border: none !important;
            background: #ffffff !important;
            display: block !important;
        }

        .back-to-map-tab {
            position: fixed !important;
            top: 50% !important;
            left: 10px !important;
            transform: translateY(-50%) !important;
            z-index: 2147483647 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 6px !important;
            padding: 12px 7px !important;
            background: #181d29 !important;
            color: #ffffff !important;
            border: 2px solid rgba(255, 255, 255, 0.28) !important;
            border-radius: 8px !important;
            font-size: 11px !important;
            font-weight: 800 !important;
            letter-spacing: 0.6px !important;
            text-decoration: none !important;
            text-transform: uppercase !important;
            writing-mode: vertical-rl !important;
            text-orientation: mixed !important;
            box-shadow: 0 6px 20px rgba(0,0,0,0.55) !important;
            cursor: pointer !important;
            transition: all 0.2s ease-in-out !important;
        }
        .back-to-map-tab:hover {
            background-color: #3182ce !important;
            border-color: #75b9f5 !important;
            transform: translateY(-50%) scale(1.04) !important;
        }

        .article-missing {
            position: fixed !important;
            top: 0 !important; left: 0 !important;
            width: 100vw !important; height: 100vh !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            color: #94a3b8 !important;
            background: #111827 !important;
            font-family: Arial, sans-serif !important;
            z-index: 2147483647 !important;
        }
    </style>
    """, unsafe_allow_html=True)

    if article and article.get("link"):
        article_url = html.escape(str(article["link"]), quote=True)

        st.markdown(f"""<div class="article-frame-wrap">
<iframe class="article-iframe" src="{article_url}" referrerpolicy="no-referrer-when-downgrade" sandbox="allow-scripts allow-same-origin allow-popups allow-forms allow-top-navigation-by-user-activation"></iframe>
</div>
<a href="?" target="_top" class="back-to-map-tab">↑ BACK TO MAP ↑</a>""", unsafe_allow_html=True)
    else:
        st.markdown("""<div class="article-missing">Article not found</div>
<a href="?" target="_top" class="back-to-map-tab">↑ BACK TO MAP ↑</a>""", unsafe_allow_html=True)
    st.stop()

# ─── SOURCE ACCESS PANEL / LIVE PIN HEADLINES ───
CRISIS_KEYWORDS = [
    "war", "bomb", "explosion", "strike", "missile", "shelling", "attack", "military", "air strike",
    "invasion", "blast", "combat", "troop", "forces", "clash", "conflict", "casualty", "offensive", "army",
    "gaza", "ukraine", "israel", "lebanon", "syria", "drone", "hezbollah", "houthi", "terror", "hostage",
    "killed", "fatal", "casualties", "weapon", "defense", "iaea", "ceasefire", "fighting", "rebel", "coup",
    "crisis", "catastrophe", "extreme", "famine", "disaster", "emergency", "devastating", "evacuation",
    "tsunami", "volcano", "cyclone", "hurricane", "red alert", "severe", "critical"
]


def is_war_or_extreme_crisis(item):
    text = f"{item.get('title', '')} {item.get('summary', '')} {item.get('location_name', '')}".lower()
    return any(k in text for k in CRISIS_KEYWORDS)


source_rows = []
source_alert_items = []

for alert_idx, item in enumerate(mapped_alerts):
    title_text = BeautifulSoup(str(item.get("title", "")), "html.parser").get_text()
    title_text = clean_text(title_text)
    source_text = clean_text(str(item.get("source", "")))
    location_text = clean_text(str(item.get("location_name", "")))
    link = f"?article={alert_idx}"

    if not title_text:
        continue

    if not is_war_or_extreme_crisis(item):
        continue

    source_alert_items.append(
        f'<div class="source-row source-row-{len(source_alert_items)}">'
        f'<div class="source-headline-wrap">'
        f'<span class="source-name">{html.escape(source_text)}</span>'
        f'<span class="source-location">📍 {html.escape(location_text)}</span>'
        f'</div>'
        f'<div class="source-headline">'
        f'<a href="{link}" target="_top">{html.escape(title_text)} ↗</a>'
        f'</div>'
        f'</div>'
    )

source_rows = source_alert_items[:8]

if not source_rows:
    source_rows = [
        '<div class="source-row source-row-0 source-row-empty">'
        '<div class="source-headline-wrap">'
        '<span class="source-name">LIVE FEEDS</span>'
        '<span class="source-location">📡 MONITORING</span>'
        '</div>'
        '<div class="source-headline">'
        '<span>No live headlines available yet — feeds are still being monitored.</span>'
        '</div>'
        '</div>'
    ]

# Append full-banner overlay item for "In friendship with: The Brussels Times" at end of feed sequence
brussels_times_banner_html = (
    f'<div class="source-row source-row-banner-overlay source-row-{len(source_rows)}">'
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 130" width="100%" height="100%" preserveAspectRatio="xMidYMid meet">'
    '<defs>'
    '<style>'
    '@import url("https://fonts.googleapis.com/css2?family=UnifrakturMaguntia&amp;family=Playfair+Display:ital,wght@0,400;0,600&amp;display=swap");'
    '.bt-sub { font-family: "Playfair Display", Georgia, serif; font-size: 26px; fill: #111827; letter-spacing: 0.5px; }'
    '.bt-title { font-family: "UnifrakturMaguntia", "Old English Text MT", "Cloister Black", serif; font-size: 78px; fill: #111827; font-weight: 700; }'
    '</style>'
    '</defs>'
    '<rect width="100%" height="100%" fill="#ffffff"/>'
    '<g transform="translate(60, 16)">'
    '<text x="0" y="26" class="bt-sub">In friendship with:</text>'
    '<text x="0" y="98" class="bt-title">The Brussels Times</text>'
    '</g>'
    '</svg>'
    '</div>'
)
source_rows.append(brussels_times_banner_html)

source_count = len(source_rows)
if source_count > 1:
    source_durations = [10] * (source_count - 1) + [30]
else:
    source_durations = [30]

source_total_seconds = max(10, sum(source_durations))
fade_sec = 0.5

keyframes_list = []
animation_rules_list = []

accum_sec = 0
for idx, dur in enumerate(source_durations):
    start_sec = accum_sec
    end_sec = accum_sec + dur
    accum_sec = end_sec

    p_start = (start_sec / source_total_seconds) * 100
    p_fadein = (min(end_sec, start_sec + fade_sec) / source_total_seconds) * 100
    p_fadeout = (max(start_sec, end_sec - fade_sec) / source_total_seconds) * 100
    p_end = (end_sec / source_total_seconds) * 100

    kf_name = f"sourceFade{idx}"

    kf_css = f"""
@keyframes {kf_name} {{
    0% {{ opacity: 0; visibility: hidden; transform: translateY(3px); }}
    {p_start:.2f}% {{ opacity: 0; visibility: visible; transform: translateY(3px); }}
    {p_fadein:.2f}% {{ opacity: 1; visibility: visible; transform: translateY(0); }}
    {p_fadeout:.2f}% {{ opacity: 1; visibility: visible; transform: translateY(0); }}
    {p_end:.2f}% {{ opacity: 0; visibility: visible; transform: translateY(-2px); }}
    100% {{ opacity: 0; visibility: hidden; transform: translateY(-2px); }}
}}
"""
    keyframes_list.append(kf_css)
    animation_rules_list.append(
        f".source-row-{idx} {{ animation: {kf_name} {source_total_seconds}s linear infinite; }}")

all_source_keyframes = "\n".join(keyframes_list)
all_source_animation_rules = "\n".join(animation_rules_list)

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=UnifrakturMaguntia&family=Playfair+Display:ital,wght@0,400;0,600&display=swap');

.source-access {{
    position: fixed !important;
    left: 0 !important;
    right: 0 !important;
    bottom: 0 !important;
    width: 100vw !important;
    height: 180px !important;
    box-sizing: border-box !important;
    overflow: hidden !important;
    z-index: 2147483000 !important;
    background: #111827;
    border-top: 2px solid rgba(255,255,255,.18);
    margin: 0;
    padding: 12px 28px;
    color: #e5e7eb;
    font-family: Arial, sans-serif;
    box-shadow: 0 -8px 28px rgba(0,0,0,.65);
}}

.source-access-head {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 13px;
    font-weight: 900;
    letter-spacing: .9px;
    text-transform: uppercase;
    margin-bottom: 8px;
}}

.source-access-body {{
    position: relative;
    min-height: 130px;
}}

.source-row {{
    position: absolute;
    left: 0;
    top: 0;
    width: 100%;
    display: block;
    padding: 4px 0;
    border-top: 1px solid rgba(255,255,255,.07);
    box-sizing: border-box;
    opacity: 0;
    visibility: hidden;
    transform: translateY(3px);
    font-size: 13px;
}}

.source-row-banner-overlay {{
    position: absolute !important;
    top: -48px !important;
    left: -28px !important;
    width: calc(100% + 56px) !important;
    height: 180px !important;
    padding: 0 !important;
    margin: 0 !important;
    border-top: none !important;
    background: #ffffff !important;
    z-index: 100 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    box-sizing: border-box !important;
    overflow: hidden !important;
}}

.source-row-banner-overlay svg {{
    width: 100% !important;
    height: 100% !important;
    max-height: 180px !important;
    object-fit: contain !important;
}}

.source-headline-wrap {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 4px;
}}

.source-name {{
    color: #ffffff;
    background: #3b70b4;
    border-radius: 5px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 900;
    letter-spacing: .6px;
    text-transform: uppercase;
    white-space: nowrap;
}}

.source-location {{
    color: #ff8b8b;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: .5px;
    text-transform: uppercase;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}

.source-headline {{
    width: 100%;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 4;
    -webkit-box-orient: vertical;
    white-space: normal;
    word-break: break-word;
    line-height: 1.35;
    max-height: 5.6em;
}}

.source-headline a,
.source-headline a:visited {{
    color: #ffffff !important;
    text-decoration: none !important;
    font-size: 16px;
    font-weight: 800;
    line-height: 1.3;
}}

.source-headline a:hover {{
    color: #75b9f5 !important;
}}

.source-row-empty .source-name {{
    background: #4a5568;
}}

.source-row-empty .source-headline {{
    color: #aab5c7;
    font-size: 12px;
}}

{all_source_keyframes}

{all_source_animation_rules}
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div class="source-access">'
    '<div class="source-access-head">'
    '<span>🛰️ LIVE DATA SOURCES</span>'
    '<span>LIVE PIN HEADLINES</span>'
    '</div>'
    '<div class="source-access-body">'
    + ''.join(source_rows)
    + '</div>'
      '</div>',
    unsafe_allow_html=True,
)

# ─── SECTION 3: MAP CANVAS LAYER RENDERING ───
live_pin_items = []
for alert_idx, item in enumerate(mapped_alerts):
    try:
        lat = float(item.get("lat"))
        lon = float(item.get("lon"))
        if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
            live_pin_items.append((alert_idx, item, lat, lon))
    except (TypeError, ValueError):
        continue

# Map building
m = folium.Map(
    location=[20.0, 0.0],
    zoom_start=2,
    min_zoom=2,
    max_bounds=True,
    zoom_control=False,
    scrollWheelZoom=True,
    touchZoom=True,
    doubleClickZoom=True
)

folium.TileLayer(
    tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    attr="&copy; OpenStreetMap &copy; CARTO",
    name="Dark Matter",
    subdomains="abcd",
    no_wrap=True
).add_to(m)

m.get_root().header.add_child(folium.Element(
    "<style>html, body, #map, .leaflet-container, .leaflet-pane, .leaflet-top, .leaflet-bottom, .leaflet-control, .leaflet-tile-pane "
    "{background-color: #262626 !important; background: #262626 !important; color-scheme: dark !important; margin: 0; padding: 0;} "
    ".leaflet-popup-content-wrapper, .leaflet-popup-tip {background-color: #1a1a1a !important; color: #ffffff !important; border: 1px solid #3d3d3d !important; box-shadow: 0 4px 16px rgba(0,0,0,0.8) !important;} "
    ".leaflet-popup-content {margin: 10px 14px !important;}</style>"
))

for alert_idx, item, lat, lon in live_pin_items:
    m_color, b_color = get_pin_colors(item)
    popup_html = (
        f'<div style="font-family:sans-serif; font-size:12px; width:240px; color:#ffffff; line-height:1.4;">'
        f'<span style="color:#a0aec0; font-weight:800; font-size:10px; text-transform:uppercase; letter-spacing:0.5px;">'
        f'📍 {html.escape(str(item["location_name"]))} — {html.escape(str(item["source"]))}</span><br>'
        f'<a href="?article={alert_idx}" target="_top" '
        f'style="text-decoration:none; font-weight:700; color:{m_color}; display:inline-block; margin-top:6px; font-size:13px;">'
        f'{html.escape(str(item["title"]))} ↗</a></div>'
    )
    marker = folium.CircleMarker(
        location=[lat, lon],
        radius=10 if item["is_un_data"] else 8,
        popup=folium.Popup(popup_html, max_width=280),
        color=b_color,
        fill=True,
        fill_color=m_color,
        fill_opacity=0.75
    )
    marker.add_to(m)

popup_zoom_js = f"""
{m.get_name()}.on('popupopen', function(e) {{
    if (e && e.popup && e.popup.getLatLng) {{
        var latlng = e.popup.getLatLng();
        var curZ = {m.get_name()}.getZoom();
        var targetZ = curZ < 5 ? 5 : Math.min(curZ + 2, 8);
        {m.get_name()}.flyTo(latlng, targetZ, {{duration: 0.8, easeLinearity: 0.25}});
    }}
}});
{m.get_name()}.on('dblclick', function(e) {{
    if (e && e.latlng) {{
        var curZ = {m.get_name()}.getZoom();
        var targetZ = curZ < 5 ? 5 : Math.min(curZ + 2, 8);
        {m.get_name()}.flyTo(e.latlng, targetZ, {{duration: 0.8, easeLinearity: 0.25}});
    }}
}});
"""
m.get_root().script.add_child(folium.Element(popup_zoom_js))

all_bounds_js = "[[-60, -180], [85, 180]]"

if live_pin_items:
    lats = [lat for _, _, lat, _ in live_pin_items]
    lons = [lon for _, _, _, lon in live_pin_items]

    if len(live_pin_items) == 1:
        m.location = [lats[0], lons[0]]
        m.options["zoom"] = 7
        all_bounds_js = f"[[{lats[0] - 1}, {lons[0] - 1}], [{lats[0] + 1}, {lons[0] + 1}]]"
    else:
        south, north = min(lats), max(lats)
        west, east = min(lons), max(lons)
        raw_span = east - west

        lat_span = north - south
        lon_span = raw_span
        lat_pad = max(2.0, lat_span * 0.12)
        lon_pad = max(3.0, lon_span * 0.12)

        south = max(-90.0, south - lat_pad)
        north = min(90.0, north + lat_pad)
        west_bound = max(-180.0, west - lon_pad)
        east_bound = min(180.0, east + lon_pad)

        m.fit_bounds(
            [[south, west_bound], [north, east_bound]],
            padding=(10, 10),
            max_zoom=8
        )
        all_bounds_js = f"[[{south}, {west_bound}], [{north}, {east_bound}]]"

reset_control_js = f"""
var ResetControl = L.Control.extend({{
    options: {{ position: 'topright' }},
    onAdd: function (map) {{
        var container = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
        var btn = L.DomUtil.create('a', '', container);
        btn.innerHTML = '🌐 Back to full map';
        btn.href = '#';
        btn.title = 'Reset map view to show all active pins';
        btn.style.backgroundColor = '#000000';
        btn.style.color = '#ffffff';
        btn.style.padding = '8px 14px';
        btn.style.textDecoration = 'none';
        btn.style.fontWeight = '700';
        btn.style.fontSize = '12px';
        btn.style.fontFamily = 'sans-serif';
        btn.style.border = '1px solid #333333';
        btn.style.borderRadius = '6px';
        btn.style.display = 'inline-block';
        btn.style.lineHeight = '1.4';
        btn.style.boxShadow = '0 4px 12px rgba(0,0,0,0.6)';

        L.DomEvent.disableClickPropagation(container);
        L.DomEvent.on(btn, 'click', function (e) {{
            L.DomEvent.preventDefault(e);
            map.flyToBounds({all_bounds_js}, {{padding: [10, 10], maxZoom: 8, duration: 1.0}});
        }});
        return container;
    }}
}});
{m.get_name()}.addControl(new ResetControl());
"""
m.get_root().script.add_child(folium.Element(reset_control_js))

st_folium(
    m,
    width="100%",
    height=1000,
    key="tactical_map",
    returned_objects=[]
)

# =============================================================================
# BOTTOM NEWS FEED (PURE CSS FIXED ANIMATION OVERLAY)
# =============================================================================

cards = []
card_index = 0

for alert_idx, item in enumerate(mapped_alerts):
    if any(code_indicator in str(item["title"]).lower() for code_indicator in
           ["style>", "keyframe", "margin", "padding", "threat-card"]): continue
    card_class = "threat-card" if item["is_un_data"] else "threat-card media"

    clean_summary_text = BeautifulSoup(str(item["summary"]), "html.parser").get_text()
    clean_title_text = BeautifulSoup(str(item["title"]), "html.parser").get_text()

    source = html.escape(str(item["source"]))
    location = html.escape(str(item["location_name"]))
    title = html.escape(clean_title_text)
    summary = html.escape(clean_summary_text)
    link = f"?article={alert_idx}"

    cards.append(f"""
        <div class="{card_class} feed-card-{card_index}">
            <div class="threat-source">{source}</div>
            <div class="threat-location">📍 {location}</div>
            <div class="threat-title"><a href="{link}" target="_top">{title} ↗</a></div>
            <div class="threat-summary">{summary}</div>
        </div>
    """)
    card_index += 1
    if card_index >= 8: break

card_count = len(cards)
seconds_per_card = 5
total_seconds = max(5, card_count * seconds_per_card)
animation_rules = []

if card_count:
    visible_percent = (seconds_per_card / total_seconds) * 100
    fade_percent = min(3.0, visible_percent * 0.15)
    for index in range(card_count):
        delay_offset = index * seconds_per_card
        animation_rules.append(
            f".feed-card-{index} {{ animation: threatFade {total_seconds}s infinite; animation-delay: {delay_offset}s; }}")
else:
    animation_rules.append(
        ".empty-feed-card { opacity: 1 !important; visibility: visible !important; transform: translateY(0) !important; }")
    cards.append("""
        <div class="threat-card" style="border-left-color: #4a5568; opacity: 1 !important; visibility: visible !important; transform: translateY(0) !important;">
            <div class="threat-location" style="color: #a0aec0;">🛰️ RADAR NOMINAL</div>
            <div class="threat-title" style="font-size: 15px; font-weight: 700;">No active threat parameters detected by this app</div>
            <div class="threat-summary">The system is actively monitoring real-time feeds. Alerts will populate automatically as relevant tracking data logs.</div>
        </div>
    """)

animation_css = "\n".join(animation_rules)
keyframe_0, keyframe_1, keyframe_2, keyframe_3 = 0, fade_percent if card_count else 0, (
        visible_percent - fade_percent) if card_count else 100, visible_percent if card_count else 100

feed_html = f"""
    <style>
        .threat-overlay {{
            position: fixed !important; left: 0px !important; right: 0px !important; bottom: 72px !important;
            width: 100vw !important; height: 220px !important; padding: 0 38px 18px 38px !important; box-sizing: border-box !important;
            background: linear-gradient(to top, rgba(10,14,20,1.0) 0%, rgba(10,14,20,0.95) 70%, rgba(10,14,20,0.0) 100%) !important;
            pointer-events: none !important; z-index: 2147483647 !important;
            -webkit-transform: translateZ(0) !important; transform: translateZ(0) !important;
            backface-visibility: hidden !important; -webkit-backface-visibility: hidden !important;
        }}
        .threat-panel {{ width: min(1120px, calc(100vw - 76px)) !important; margin: 0 auto !important; pointer-events: auto !important; position: relative !important; z-index: 2147483647 !important; }}
        .threat-overlay .threat-card {{ position: absolute !important; left: 0 !important; top: 0 !important; width: 100% !important; opacity: 0; transform: translateY(4px); visibility: hidden; transition: visibility 0s linear {total_seconds}s; z-index: 2147483647 !important; }}

        @keyframes threatFade {{
            {keyframe_0}% {{ opacity: 0; visibility: visible; transform: translateY(4px); }}
            {keyframe_1}% {{ opacity: 1; visibility: visible; transform: translateY(0); }}
            {keyframe_2}% {{ opacity: 1; visibility: visible; transform: translateY(0); }}
            {keyframe_3}% {{ opacity: 0; visibility: visible; transform: translateY(-3px); }}
            100% {{ opacity: 0; visibility: hidden; transform: translateY(-3px); }}
        }}
        {animation_css}
    </style>

    <div class="threat-overlay">
        <div class="threat-panel">
            <div class="threat-heading">🚨 REAL-TIME BREAKING LOGS ({card_count})</div>
            <div style="position: relative; width: 100%; min-height: 120px; display: block; z-index: 2147483647 !important;">
                {''.join(cards)}
            </div>
        </div>
    </div>
    """

st.markdown(feed_html, unsafe_allow_html=True)

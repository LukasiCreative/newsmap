import streamlit as st
import requests, folium, re, json, html, os, time
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from streamlit_folium import st_folium

st.set_page_config(page_title="CRISIS COMMAND", layout="wide", page_icon="🛰️", initial_sidebar_state="collapsed")

# ─── WHY THE "<div class=...>" TEXT WAS SHOWING UP RAW ───────────
# st.markdown(..., unsafe_allow_html=True) still runs the string
# through a Markdown parser before allowing HTML through. Markdown's
# rule: any line indented 4+ spaces that follows a blank line gets
# rendered as a literal CODE BLOCK (plain escaped text) instead of
# being treated as HTML. Every HTML/CSS string in this file is
# written with Python-source-matching indentation for readability
# (4/8/12 spaces), and feed_html in particular has a blank line
# right after "</style>" followed by an indented "<div ...>" — which
# is exactly the pattern that triggers this. Stripping leading
# whitespace from every line before handing a string to st.markdown
# avoids the problem everywhere, permanently. Defined here, right
def _flatten_html(markup):
    return re.sub(r"(?m)^[ \t]+", "", markup)


# ─── SECTION 1: SYSTEM STYLES (ELIMINATING ALL SPACING GAPS) ───
st.markdown(_flatten_html("""
    <style>
        html, body {background-color: #262626 !important; margin: 0 !important; padding: 0 !important;}

        /* =========================================================
           REMOVE STREAMLIT HOST / TOOLBAR / BRANDING ELEMENTS
           ========================================================= */
        #MainMenu,
        footer,
        header,
        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stToolbarActions"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"],
        [data-testid="stAppDeployButton"],
        [data-testid="stHeaderActionElements"],
        div[class*="viewerBadge"],
        div[class*="stDeployButton"],
        div[class*="StatusWidget"],
        div[class*="Toolbar"],
        div[class*="Decoration"] {
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
            width: 0 !important;
            height: 0 !important;
            min-height: 0 !important;
            pointer-events: none !important;
        }

        button[title*="Streamlit"],
        button[aria-label*="Streamlit"],
        a[title*="Streamlit"],
        a[aria-label*="Streamlit"] {
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
            pointer-events: none !important;
        }

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

        /* ─── MAP IFRAME HEIGHT FIX ───────────────────────────────
           Previously this was forced to 100vh, which made the
           Folium map container almost as tall as the whole phone
           screen. fit_bounds() then had to zoom WAY out to satisfy
           that height, pulling in a huge amount of empty ocean
           above the actual pin cluster. Because the ocean tile
           color is nearly identical to the page background, that
           empty zoomed-out space looked like a blank/broken layout
           instead of "part of the map".
           Capping the height (and reserving room for the one
           remaining fixed bottom panel: the source-access ticker,
           190px tall — sized for one headline at a time, wrapped
           across multiple lines instead of cut off, cycling via JS
           — the REAL-TIME BREAKING LOGS card overlay was removed)
           lets fit_bounds zoom in tighter so pins fill more of the
           view. */
        div[data-testid="stCustomComponentV1"], iframe {
            width: 100vw !important;
            height: calc(100vh - 190px) !important;
            margin: 0px !important; padding: 0px !important; border: none !important;
        }
    </style>
"""), unsafe_allow_html=True)

# NOTE: the old "streamlit-host-cover" black box (fixed bottom-right,
# 260x64px, solid #111827) used to be needed to hide the Streamlit Cloud
# branding badge. Now that the app is hosted on Render (not Streamlit
# Cloud), that badge doesn't exist anymore — but the cover div was still
# being rendered, sitting on top of the news feed banner as an opaque
# black square with nothing to actually hide. It has been removed.

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
    # Previously used plain substring matching ("keyword in text"),
    # which caused false positives: "war" is a substring of
    # "warming", "warmer", "warmth", etc., so any weather/temperature
    # headline mentioning "global warming" got incorrectly flagged as
    # war-relevant and leaked into the war-news ticker. Word-boundary
    # regex matching (\b...\b) requires "war" to appear as its own
    # whole word — matching "war" and "wars" but not "warming".
    text = f"{title} {summary}".lower()
    return any(re.search(rf"\b{re.escape(keyword)}\b", text) for keyword in WAR_KEYWORDS)


# ─── SECTION 2: VERIFIED DISASTER DATA FEEDS ───
# Feed URLs are the machine-readable endpoints, while the homepage URLs are kept
# as clickable source links in the app. ReliefWeb requires an approved appname;
# set RELIEFWEB_APPNAME in the deployment environment.
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

REQUEST_HEADERS = {
    "User-Agent": "CrisisCommand/2.0 (+https://gdacs.org; disaster-feed-client)",
    "Accept": "application/json, application/xml, text/xml, application/atom+xml, */*",
}


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
            link = _xml_local_text(item, "link")
            if not link:
                link = _xml_local_attr(item, "link", "href")
            if not title or not link:
                continue
            if only_relevant and not relevant(title, description):
                continue

            # GeoRSS / GDACS coordinates. Fall back to title/summary matching.
            lat = lon = None
            for node in item.iter():
                local = node.tag.rsplit("}", 1)[-1].lower()
                if local in {"point", "where"} and node.text:
                    parts = node.text.replace(",", " ").split()
                    if len(parts) >= 2:
                        lat = _safe_float(parts[0]); lon = _safe_float(parts[1])
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


@st.cache_data(ttl=60, show_spinner=False)
def fetch_usgs_geojson(limit=20):
    articles = []
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()
        for feature in data.get("features", [])[:limit]:
            props = feature.get("properties") or {}
            coords = ((feature.get("geometry") or {}).get("coordinates") or [])
            if len(coords) < 2:
                continue
            lon, lat = _safe_float(coords[0]), _safe_float(coords[1])
            if lat is None or lon is None:
                continue
            title = clean_text(props.get("title") or "USGS earthquake")
            link = props.get("url") or data.get("metadata", {}).get("url") or "https://earthquake.usgs.gov/"
            magnitude = props.get("mag")
            place = clean_text(props.get("place") or "Global")
            time_ms = props.get("time")
            time_text = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(time_ms / 1000)) if time_ms else ""
            summary = f"Magnitude {magnitude} — {place}{(' — ' + time_text) if time_text else ''}"
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


@st.cache_data(ttl=60, show_spinner=False)
def fetch_usgs_atom(limit=12):
    # fetch_rss()'s is_un_data heuristic only recognizes source names
    # starting with "GDACS" or "RELIEFWEB" — "USGS" matches neither,
    # so every result came back is_un_data=False (i.e. tagged as
    # "media"/red, war-related). That's wrong: USGS is earthquake
    # data, not war/conflict news, so it should never be red or show
    # up in the war-news ticker. Force it to True here explicitly
    # (matching fetch_usgs_geojson, which already does this
    # correctly). New dicts are built rather than mutating the
    # cached ones fetch_rss returned, since @st.cache_data may hand
    # back the same object on repeat calls.
    articles = fetch_rss(
        "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.atom",
        "USGS",
        limit=limit,
        only_relevant=False,
    )
    return [{**article, "is_un_data": True} for article in articles]


def fetch_live_media():
    all_articles = []
    # Keep the existing media monitoring, but use actual feed URLs rather than homepages.
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
            seen.add(key); unique.append(article)
    return unique


# --- Execute Ingestion Pipelines ---
feed_articles = []
feed_articles.extend(fetch_rss(FEED_CONFIG[0]["feed_url"], "GDACS", limit=8))
feed_articles.extend(fetch_rss(FEED_CONFIG[1]["feed_url"], "GDACS", limit=8))
feed_articles.extend(fetch_reliefweb(limit=15))
feed_articles.extend(fetch_usgs_geojson(limit=20))
feed_articles.extend(fetch_usgs_atom(limit=12))
feed_articles.extend(fetch_live_media())

# De-duplicate across formats without hiding a source's identity.
seen, mapped_alerts = set(), []
for article in feed_articles:
    key = (article["title"].strip().lower(), round(article["lat"], 3), round(article["lon"], 3))
    if key in seen:
        continue
    seen.add(key)
    mapped_alerts.append(article)
# ─── ARTICLE VIEW (shown when a card/pin link is opened) ───
requested_article = st.query_params.get("article")
if requested_article is not None:
    try:
        article_idx = int(requested_article)
    except (TypeError, ValueError):
        article_idx = None
    article = mapped_alerts[article_idx] if article_idx is not None and 0 <= article_idx < len(mapped_alerts) else None

    # Global styles injecting the left-docked button and container layout
    st.markdown(_flatten_html("""
    <style>
        .stApp, .stAppViewContainer, .stAppViewBlockContainer, .main, .main .block-container {
            padding: 0px !important; margin: 0px !important; max-width: 100% !important; width: 100% !important;
            background-color: #111827 !important;
        }

        /* Forces the container to float out of the Streamlit layout column onto the far left wall */
        .left-dock-anchor {
            position: fixed !important; 
            top: 40px !important; 
            left: 40px !important; 
            z-index: 2147483647 !important;
        }

        /* Custom styled HTML button mimicking your interface structure */
        .custom-back-btn {
            background-color: #181d29 !important;
            color: #ffffff !important;
            border: 2px solid rgba(255,255,255,.18) !important;
            border-radius: 8px !important;
            padding: 10px 20px !important;
            font-size: 13px !important;
            font-weight: 800 !important;
            font-family: Arial, sans-serif !important;
            box-shadow: 0 6px 20px rgba(0,0,0,.5) !important;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .custom-back-btn:hover {
            background-color: #232a3b !important;
            border-color: #75b9f5 !important;
            color: #75b9f5 !important;
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
            color: #fff; 
            border-radius: 5px; 
            padding: 5px 10px; 
            font-size: 11px; 
            font-weight: 800; 
            letter-spacing: .3px; 
            margin-bottom: 12px; 
        }
        .article-location { color: #75b9f5; font-size: 13px; font-weight: 900; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
        .article-title { color: #fff; font-size: 28px; font-weight: 800; line-height: 1.25; margin-bottom: 18px; }
        .article-summary { color: #aab5c7; font-size: 16px; line-height: 1.6; margin-bottom: 30px; }
        .article-open-btn { display: inline-block; background: #3182ce; color: #fff; text-decoration: none !important; font-weight: 800; font-size: 14px; padding: 12px 24px; border-radius: 8px; border: none; cursor: pointer; font-family: Arial, sans-serif; }
        .article-open-btn:hover { background: #2c6cb0; }
    </style>
    """), unsafe_allow_html=True)

    # Switched from a plain <a href="?"> to a <button onclick="...">
    # that explicitly sets window.location.href. Plain anchor clicks
    # weren't registering at all — most likely something on the page
    # (Streamlit's own client-side routing, which handles some link
    # clicks itself to avoid full page reloads) was intercepting the
    # click and not handling this particular href correctly.
    # Directly assigning window.location.href always forces a real,
    # full browser navigation, bypassing any such interception.
    st.markdown(_flatten_html("""
        <div class="left-dock-anchor">
            <button class="custom-back-btn" onclick="window.location.href = window.location.pathname;">← Back to Map</button>
        </div>
    """), unsafe_allow_html=True)

    # Render Article Body Content
    if article:
        # Same window.location.href approach for the external link,
        # for the same reason. json.dumps() safely produces a
        # properly quoted/escaped JS string literal from the URL
        # (handling any quotes or special characters in it), and
        # html.escape() then makes that safe to sit inside the
        # onclick="..." HTML attribute.
        open_article_js = f"window.location.href = {json.dumps(str(article['link']))};"
        st.markdown(
            '<div class="article-wrap">'
            f'<div class="article-source-pill">{html.escape(str(article["source"]))}</div>'
            f'<div class="article-location">📍 {html.escape(str(article["location_name"]))}</div>'
            f'<div class="article-title">{html.escape(str(article["title"]))}</div>'
            f'<div class="article-summary">{html.escape(str(article["summary"]))}</div>'
            f'<button class="article-open-btn" onclick="{html.escape(open_article_js, quote=True)}">Open Full Article Source ↗</button>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="article-wrap">'
            '<div class="article-title">Article not found</div>'
            '<div class="article-summary">This item may have expired from the live tracking logs. Head back to the map view to see current parameters.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    st.stop()

# ─── SOURCE ACCESS PANEL / LIVE PIN HEADLINES ───
# One headline visible at a time (a scroller, not a static list),
# but unlike the very first version, the text is allowed to wrap
# across multiple lines instead of being cut off with "...". The
# rotation itself is driven by client-side JS (setInterval swapping
# innerHTML + a CSS fade) rather than the old CSS keyframe-percentage
# trick — that was fragile because the timing had to be hand-matched
# to the row count; JS just advances through the list on a plain
# timer regardless of how many rows there are.
source_rows = []
source_alert_items = []

# Only the red pins go in the ticker — those are the war/conflict
# media items (BBC, Sky, Al Jazeera, etc., matched against
# WAR_KEYWORDS in fetch_live_media). Blue pins (GDACS/ReliefWeb/USGS
# — is_un_data=True — earthquakes, storms, general disaster alerts)
# are still plotted on the map, just left out of this headline feed.
for alert_idx, item in enumerate(mapped_alerts):
    if item.get("is_un_data"):
        continue

    title_text = BeautifulSoup(str(item.get("title", "")), "html.parser").get_text()
    title_text = clean_text(title_text)
    source_text = clean_text(str(item.get("source", "")))
    location_text = clean_text(str(item.get("location_name", "")))
    link = f"?article={alert_idx}"

    if not title_text:
        continue

    source_alert_items.append(
        f'<div class="source-row">'
        f'<div class="source-headline-wrap">'
        f'<span class="source-name">{html.escape(source_text)}</span>'
        f'<span class="source-location">📍 {html.escape(location_text)}</span>'
        f'</div>'
        f'<div class="source-headline">'
        f'<a href="{link}" target="_top">{html.escape(title_text)} ↗</a>'
        f'</div>'
        f'</div>'
    )

# No cap — cycle through every war/conflict headline available, then
# loop back to the start (the JS rotation below already wraps around
# via idx % rows.length, so this just needed more items in the array).
source_rows = source_alert_items

# If there are no live alerts, keep the banner visible and explain why.
if not source_rows:
    source_rows = [
        '<div class="source-row source-row-empty">'
        '<div class="source-headline-wrap">'
        '<span class="source-name">LIVE FEEDS</span>'
        '<span class="source-location">📡 MONITORING</span>'
        '</div>'
        '<div class="source-headline">'
        '<span>No live headlines available yet — feeds are still being monitored.</span>'
        '</div>'
        '</div>'
    ]

st.markdown(_flatten_html("""
<style>
.source-access {
    position: fixed !important;
    left: 0 !important;
    right: 0 !important;
    bottom: 0 !important;
    width: 100vw !important;
    height: 190px !important;
    box-sizing: border-box !important;
    overflow: hidden !important;
    z-index: 2147483000 !important;
    background: #111827;
    border-top: 1px solid rgba(255,255,255,.12);
    margin: 0;
    padding: 9px 22px 12px 22px;
    color: #e5e7eb;
    font-family: Arial, sans-serif;
    box-shadow: 0 -6px 20px rgba(0,0,0,.4);
    display: flex;
    flex-direction: column;
}

.source-access-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 11px;
    font-weight: 900;
    letter-spacing: .8px;
    text-transform: uppercase;
    margin-bottom: 6px;
    flex: 0 0 auto;
}

.source-access-body {
    position: relative;
    flex: 1 1 auto;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
    opacity: 1;
    transition: opacity 0.35s ease;
}

.source-access-body.source-fading {
    opacity: 0;
}

.source-row {
    display: block;
    width: 100%;
    padding: 0;
    box-sizing: border-box;
    font-size: 12px;
}

.source-headline-wrap {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 4px;
}

.source-name {
    color: #ffffff;
    background: #3b70b4;
    border-radius: 4px;
    padding: 3px 7px;
    font-size: 9px;
    font-weight: 900;
    letter-spacing: .5px;
    text-transform: uppercase;
    white-space: nowrap;
}

.source-location {
    color: #ff8b8b;
    font-size: 9px;
    font-weight: 800;
    letter-spacing: .5px;
    text-transform: uppercase;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.source-headline {
    width: 100%;
    white-space: normal;
    line-height: 1.35;
}

.source-headline a,
.source-headline a:visited {
    color: #ffffff !important;
    text-decoration: none !important;
    font-size: 15px;
    font-weight: 800;
    line-height: 1.35;
}

.source-headline a:hover {
    color: #75b9f5 !important;
}

.source-row-empty .source-name {
    background: #4a5568;
}

.source-row-empty .source-headline {
    color: #aab5c7;
    font-size: 12px;
}
</style>
"""), unsafe_allow_html=True)

# The body starts with the first headline already in place (so it's
# visible immediately, before any JS runs). The <script> below then
# takes over, fading out the current one, swapping in the next from
# the `sourceRows` array, and fading back in — repeating on a timer.
# json.dumps handles all the escaping for embedding the HTML strings
# safely inside a JS array literal.
st.markdown(_flatten_html(f"""
<div class="source-access">
    <div class="source-access-head">
        <span>🛰️ LIVE DATA SOURCES</span>
        <span>LIVE PIN HEADLINES</span>
    </div>
    <div class="source-access-body" id="source-ticker-body">{source_rows[0]}</div>
</div>
<script>
(function() {{
    var rows = {json.dumps(source_rows)};
    var idx = 0;
    var el = document.getElementById('source-ticker-body');
    if (!el || rows.length <= 1) return;
    setInterval(function() {{
        el.classList.add('source-fading');
        setTimeout(function() {{
            idx = (idx + 1) % rows.length;
            el.innerHTML = rows[idx];
            el.classList.remove('source-fading');
        }}, 350);
    }}, 5000);
}})();
</script>
"""), unsafe_allow_html=True)

# ─── SECTION 3: MAP CANVAS LAYER RENDERING ───
# The viewport is derived ONLY from real coordinates supplied by live feeds.
# No synthetic/fallback coordinates are used for map positioning.
live_pin_items = []
for alert_idx, item in enumerate(mapped_alerts):
    try:
        lat = float(item.get("lat"))
        lon = float(item.get("lon"))
        if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
            live_pin_items.append((alert_idx, item, lat, lon))
    except (TypeError, ValueError):
        continue

# Neutral view only when there are no real pins. This is a map viewport,
# not an event/pin and must never be interpreted as a location.
m = folium.Map(
    location=[20.0, 0.0],
    zoom_start=2,
    min_zoom=2,
    max_bounds=True,
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

# Leaflet's default container background is a light grey (#ddd) and shows through
# whenever the fitted zoom/bounds don't fully tile-cover the container (letterboxing).
# This lives inside the map's own iframe, so the outer page CSS can't reach it —
# it has to be injected directly into the Folium-generated HTML.
m.get_root().html.add_child(folium.Element(
    "<style>html, body {background: #262626 !important; margin: 0; padding: 0;} "
    ".leaflet-container {background: #262626 !important;}</style>"
))

# NEW: collect one click-handler snippet per pin. Each pin gets its own
# JS variable name (marker.get_name()), so each click handler is scoped
# to that specific marker only.
marker_click_scripts = []

for alert_idx, item, lat, lon in live_pin_items:
    m_color, b_color = ("#3182ce", "#63b3ed") if item["is_un_data"] else ("#ff4b4b", "#ff8080")
    popup_html = (
        f'<div style="font-family:sans-serif; font-size:12px; width:240px; color:#1a1f2c; line-height:1.4;">'
        f'<span style="color:#718096; font-weight:800; font-size:10px; text-transform:uppercase;">'
        f'📍 {html.escape(str(item["location_name"]))} — {html.escape(str(item["source"]))}</span><br>'
        f'<a href="?article={alert_idx}" target="_top" '
        f'style="text-decoration:none; font-weight:700; color:{m_color}; display:inline-block; margin-top:4px;">'
        f'{html.escape(str(item["title"]))} ↗</a></div>'
    )
    marker = folium.CircleMarker(
        location=[lat, lon],
        radius=11 if item["is_un_data"] else 9,
        popup=folium.Popup(popup_html, max_width=280),
        color=b_color,
        fill=True,
        fill_color=m_color,
        fill_opacity=0.75
    )
    marker.add_to(m)

    # first click on a pin flies the map in to a closer zoom (zoom 6,
    # was 4) centered on that pin. The bound popup (above) still
    # opens on the same click, so the flow is:
    #   click pin -> map zooms in closer + popup with title link
    #   click the title link in the popup -> opens the article view
    # Math.max(...) guards against zooming OUT if the map is already
    # tighter than zoom 6 (e.g. a second pin clicked nearby).
    marker_click_scripts.append(
        f"{marker.get_name()}.on('click', function(e) {{"
        f"{m.get_name()}.flyTo(e.latlng, Math.max({m.get_name()}.getZoom(), 6), {{duration: 0.75}});"
        f"}});"
    )

# NEW: attach all the click handlers, deferred until DOMContentLoaded.
# An earlier version of this added the handler code straight into the
# page via `.html.add_child(...)`, which (depending on exactly where
# Folium places the map/marker-creation <script> relative to the body)
# could run BEFORE `marker_xxx`/`map_xxx` existed yet as JS variables -
# a silent ReferenceError, so the handlers never attached and clicking
# a pin did nothing.
# Wrapping the attachment code in a DOMContentLoaded listener sidesteps
# that ordering question entirely: this callback only fires once every
# script tag already on the page (including the one Folium generates to
# build the map and every marker) has finished executing, so `marker_xxx`
# and `map_xxx` are guaranteed to exist by the time this runs - no matter
# where in the document our own script tag physically sits.
if marker_click_scripts:
    deferred_click_script = (
        "document.addEventListener('DOMContentLoaded', function() {"
        + "".join(marker_click_scripts)
        + "});"
    )
    m.get_root().html.add_child(folium.Element(
        "<script>" + deferred_click_script + "</script>"
    ))

# Automatically fit the map to the real pins.
# Regional clusters zoom in; globally separated events zoom out.
# The map remains a single, non-repeating world view.
#
# ─── DEFAULT VIEW: PRIORITIZE THE AFRICA/MIDDLE EAST CLUSTER ─────
# Every pin still gets plotted on the map regardless. But for the
# DEFAULT zoom/center, we only fit bounds around the war/conflict
# ("media", red) pins — GDACS/USGS ("is_un_data", blue) pins are
# scattered worldwide (earthquakes, storms, floods anywhere), while
# the war/conflict pins cluster tightly around Africa/Middle East by
# design of GEO_DATABASE (Gaza, Israel, Lebanon, Syria, Yemen, Iran,
# Iraq, Egypt, Sudan, Somalia, Libya, etc). Fitting bounds to the
# whole worldwide set was dragging the zoom out further than needed
# just to include occasional pins in the Americas/Asia/Australia.
focus_pin_items = [item_tuple for item_tuple in live_pin_items if not item_tuple[1]["is_un_data"]]
if not focus_pin_items:
    focus_pin_items = live_pin_items

if live_pin_items:
    lats = [lat for _, _, lat, _ in focus_pin_items]
    lons = [lon for _, _, _, lon in focus_pin_items]

    if len(focus_pin_items) == 1:
        m.location = [lats[0], lons[0]]
        m.options["zoom"] = 8
    else:
        south, north = min(lats), max(lats)
        west, east = min(lons), max(lons)
        raw_span = east - west

        lat_span = north - south
        lon_span = raw_span
        # Tighter padding = closer zoom on the actual pin cluster
        # (was 0.12 / min 2.0-3.0, which pulled in a lot of extra
        # surrounding area and zoomed out further than needed).
        lat_pad = max(1.0, lat_span * 0.08)
        lon_pad = max(1.5, lon_span * 0.08)

        south = max(-90.0, south - lat_pad)
        north = min(90.0, north + lat_pad)

        west_bound = max(-180.0, west - lon_pad)
        east_bound = min(180.0, east + lon_pad)

        m.fit_bounds(
            [[south, west_bound], [north, east_bound]],
            padding=(10, 10),
            max_zoom=10
        )

# ─── STALE-SIZE / TOP-GAP FIX ────────────────────────────────────
# Root cause of "big empty gap on top, map squeezed at the bottom":
# Leaflet calculates its tile layout and centers pins based on the
# container's pixel size AT THE MOMENT THE MAP INITIALIZES. Our CSS
# rule forces the surrounding iframe to a specific height, but that
# CSS is applied by the browser slightly AFTER Leaflet has already
# measured the (larger, still-resizing) container and laid out tiles
# for that outdated size. When the iframe visually settles to its
# final (correct) height, Leaflet doesn't know to recompute — so the
# map you see is really just the bottom slice of a taller map that
# was never told to resize, leaving empty space up top.
# Fix: explicitly call invalidateSize() (which makes Leaflet re-read
# the container's current size) and then re-apply the exact same
# view/bounds Python already calculated above, a few times shortly
# after load and on every window resize. This forces Leaflet to
# recenter and re-tile using the real, final container dimensions.
if live_pin_items:
    if len(focus_pin_items) == 1:
        _reapply_view_js = f"{m.get_name()}.setView([{lats[0]}, {lons[0]}], 8);"
    else:
        _reapply_view_js = (
            f"{m.get_name()}.fitBounds([[{south}, {west_bound}], [{north}, {east_bound}]], "
            f"{{padding: [10, 10], maxZoom: 10}});"
        )

    resize_fix_script = (
        "<script>"
        f"function __fixMapView(){{ try {{ "
        f"{m.get_name()}.invalidateSize(); {_reapply_view_js} "
        f"}} catch(e) {{}} }}"
        "window.addEventListener('load', function(){"
        "  __fixMapView();"
        "  setTimeout(__fixMapView, 200);"
        "  setTimeout(__fixMapView, 600);"
        "  setTimeout(__fixMapView, 1200);"
        "});"
        "window.addEventListener('resize', __fixMapView);"
        "if (window.ResizeObserver) {"
        "  new ResizeObserver(__fixMapView).observe(document.body);"
        "}"
        "</script>"
    )
    m.get_root().html.add_child(folium.Element(resize_fix_script))

# ─── MAP RENDER HEIGHT FIX ───────────────────────────────────────
# Previously fixed at height=1000 (px), which is much taller than
# most phone screens. That mismatch is what forced fit_bounds() to
# zoom out so far that pins ended up compressed into a small area
# with a large band of empty, same-colored ocean above them.
# 680px lines up with the CSS iframe height rule above
# (calc(100vh - 190px)) now that the source-access ticker is 190px
# tall (one headline at a time, wrapped instead of cut off) as the
# one remaining fixed bottom panel.
st_folium(m, width="100%", height=680, returned_objects=[], key="tactical_map_flush_v31")

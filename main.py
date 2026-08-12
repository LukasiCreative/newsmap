import streamlit as st
import requests, folium, re, json, html, os, time
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from streamlit_folium import st_folium

st.set_page_config(page_title="CRISIS COMMAND", layout="wide", page_icon="🛰️", initial_sidebar_state="collapsed")

# ─── SECTION 1: SYSTEM STYLES (ELIMINATING ALL SPACING GAPS) ───
st.markdown("""
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

        div[data-testid="stCustomComponentV1"], iframe {
            width: 100vw !important; height: 100vh !important; 
            margin: 0px !important; padding: 0px !important; border: none !important;
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

# Final app-level cover for any Streamlit branding badge that survives the
# selectors above. This only covers the small lower-right host/badge area.
st.markdown("""
<style>
    .streamlit-host-cover {
        position: fixed !important;
        right: 0 !important;
        bottom: 0 !important;
        width: 260px !important;
        height: 64px !important;
        background: #111827 !important;
        z-index: 2147483647 !important;
        pointer-events: none !important;
        display: block !important;
    }
</style>
<div class="streamlit-host-cover"></div>
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
    return fetch_rss(
        "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.atom",
        "USGS",
        limit=limit,
        only_relevant=False,
    )


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
    st.markdown("""
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
        .article-open-btn { display: inline-block; background: #3182ce; color: #fff; text-decoration: none !important; font-weight: 800; font-size: 14px; padding: 12px 24px; border-radius: 8px; }
        .article-open-btn:hover { background: #2c6cb0; }
    </style>
    """, unsafe_allow_html=True)

    # Pure HTML button placed inside the left-docked anchor.
    # The 'onclick' script rewrites the browser history state to drop '?article=X' cleanly,
    # then clicks an invisible button to trigger a smooth internal Streamlit execution update.
    st.markdown("""
        <div class="left-dock-anchor">
            <button class="custom-back-btn" onclick="
                window.top.history.pushState({}, '', window.top.location.pathname);
                const btn = window.parent.document.querySelector('button[kind=\\'secondary\\']');
                if(btn) btn.click(); else window.top.location.reload();
            ">← Back to Map</button>
        </div>
    """, unsafe_allow_html=True)

    # Render Article Body Content
    if article:
        st.markdown(
            '<div class="article-wrap">'
            f'<div class="article-source-pill">{html.escape(str(article["source"]))}</div>'
            f'<div class="article-location">📍 {html.escape(str(article["location_name"]))}</div>'
            f'<div class="article-title">{html.escape(str(article["title"]))}</div>'
            f'<div class="article-summary">{html.escape(str(article["summary"]))}</div>'
            f'<a class="article-open-btn" href="{html.escape(str(article["link"]), quote=True)}" target="_blank">Open Full Article Source ↗</a>'
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
# Rotates through the actual live alerts currently represented by map pins.
# Each banner item shows the source + the headline from the corresponding pin.
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

# Limit the rotating banner to the same first 8 live alerts used by the
# breaking-news overlay, keeping the interface compact.
source_rows = source_alert_items[:8]

# If there are no live alerts, keep the banner visible and explain why.
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

source_count = len(source_rows)
source_seconds_per_row = 5
source_total_seconds = max(5, source_count * source_seconds_per_row)
source_visible_percent = (source_seconds_per_row / source_total_seconds) * 100
source_fade_percent = min(3.0, source_visible_percent * 0.15)

source_animation_rules = "\n".join(
    f".source-row-{index} {{ animation: sourceFade {source_total_seconds}s infinite; "
    f"animation-delay: {index * source_seconds_per_row}s; }}"
    for index in range(source_count)
)

src_kf0 = 0
src_kf1 = source_fade_percent
src_kf2 = source_visible_percent - source_fade_percent
src_kf3 = source_visible_percent

st.markdown(f"""
<style>
.source-access {{
    position: fixed !important;
    left: 0 !important;
    right: 0 !important;
    bottom: 0 !important;
    width: 100vw !important;
    height: 92px !important;
    box-sizing: border-box !important;
    overflow: hidden !important;
    z-index: 2147483000 !important;
    background: #111827;
    border-top: 1px solid rgba(255,255,255,.12);
    margin: 0;
    padding: 9px 22px;
    color: #e5e7eb;
    font-family: Arial, sans-serif;
    box-shadow: 0 -6px 20px rgba(0,0,0,.4);
}}

.source-access-head {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 11px;
    font-weight: 900;
    letter-spacing: .8px;
    text-transform: uppercase;
    margin-bottom: 6px;
}}

.source-access-body {{
    position: relative;
    min-height: 58px;
}}

.source-row {{
    position: absolute;
    left: 0;
    top: 0;
    width: 100%;
    display: block;
    padding: 5px 0;
    border-top: 1px solid rgba(255,255,255,.07);
    box-sizing: border-box;
    opacity: 0;
    visibility: hidden;
    transform: translateY(3px);
    font-size: 12px;
}}

.source-headline-wrap {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 3px;
}}

.source-name {{
    color: #ffffff;
    background: #3b70b4;
    border-radius: 4px;
    padding: 3px 7px;
    font-size: 9px;
    font-weight: 900;
    letter-spacing: .5px;
    text-transform: uppercase;
    white-space: nowrap;
}}

.source-location {{
    color: #ff8b8b;
    font-size: 9px;
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
    white-space: nowrap;
    text-overflow: ellipsis;
}}

.source-headline a,
.source-headline a:visited {{
    color: #ffffff !important;
    text-decoration: none !important;
    font-size: 14px;
    font-weight: 800;
    line-height: 1.25;
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

@keyframes sourceFade {{
    {src_kf0}% {{
        opacity: 0;
        visibility: visible;
        transform: translateY(3px);
    }}
    {src_kf1}% {{
        opacity: 1;
        visibility: visible;
        transform: translateY(0);
    }}
    {src_kf2}% {{
        opacity: 1;
        visibility: visible;
        transform: translateY(0);
    }}
    {src_kf3}% {{
        opacity: 0;
        visibility: visible;
        transform: translateY(-2px);
    }}
    100% {{
        opacity: 0;
        visibility: hidden;
        transform: translateY(-2px);
    }}
}}

{source_animation_rules}
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
        radius=10 if item["is_un_data"] else 8,
        popup=folium.Popup(popup_html, max_width=280),
        color=b_color,
        fill=True,
        fill_color=m_color,
        fill_opacity=0.75
    )
    marker.add_to(m)

    # NEW: first click on a pin flies the map in to continent-level zoom
    # (zoom 4) centered on that pin. The bound popup (above) still opens
    # on the same click, so the flow is:
    #   click pin -> map zooms into that continent + popup with title link
    #   click the title link in the popup -> opens the article view
    # Math.max(...) guards against zooming OUT if the map is already
    # tighter than zoom 4 (e.g. a second pin clicked nearby).
    marker_click_scripts.append(
        f"{marker.get_name()}.on('click', function(e) {{"
        f"{m.get_name()}.flyTo(e.latlng, Math.max({m.get_name()}.getZoom(), 4), {{duration: 0.75}});"
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
if live_pin_items:
    lats = [lat for _, _, lat, _ in live_pin_items]
    lons = [lon for _, _, _, lon in live_pin_items]

    if len(live_pin_items) == 1:
        m.location = [lats[0], lons[0]]
        m.options["zoom"] = 7
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

st_folium(m, width="100%", height=1000, returned_objects=[], key="tactical_map_flush_v31")


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
            <div class="threat-title"><a href="{link}">{title} ↗</a></div>
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

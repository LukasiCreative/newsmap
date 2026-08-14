import streamlit as st
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
    """
    Removes Python indentation from HTML/CSS before passing it to
    Streamlit so indented HTML is not interpreted as a Markdown
    code block.
    """
    return re.sub(r"(?m)^[ \t]+", "", markup)


# ================================================================
# SYSTEM STYLES
# ================================================================

st.markdown(
    _flatten_html("""
    <style>
        html, body {
            background-color: #262626 !important;
            margin: 0 !important;
            padding: 0 !important;
        }

        /* =========================================================
           REMOVE STREAMLIT HOST / TOOLBAR / BRANDING
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

        .stApp,
        .stAppViewContainer,
        .stAppViewBlockContainer,
        .main,
        .main .block-container {
            padding: 0px !important;
            margin: 0px !important;
            max-width: 100% !important;
            width: 100% !important;
            background-color: #262626 !important;
        }

        div[data-testid="stAppViewContainer"] {
            padding-top: 0px !important;
            margin-top: 0px !important;
            background-color: #262626 !important;
        }

        div[data-testid="stAppViewContainer"] > .main {
            padding-top: 0px !important;
            margin-top: 0px !important;
        }

        div[data-testid="stMainBlockContainer"] {
            padding-top: 0px !important;
            margin-top: 0px !important;
            background-color: #262626 !important;
        }

        .main .block-container {
            padding-top: 0px !important;
            margin-top: 0px !important;
        }

        div[data-testid="stVerticalBlock"],
        div[data-testid="stElementContainer"],
        div[data-testid="stVerticalBlockInsideExecutionFlow"] {
            padding-left: 0rem !important;
            padding-right: 0rem !important;
            margin-left: 0rem !important;
            margin-right: 0rem !important;
            padding-top: 0px !important;
            padding-bottom: 0px !important;
            margin-top: 0px !important;
            margin-bottom: 0px !important;
            gap: 0px !important;
            width: 100% !important;
            background-color: transparent !important;
        }

        [data-testid="stElementContainer"]:first-child {
            margin-top: 0px !important;
            padding-top: 0px !important;
        }

        div[data-testid="stMainBlockContainer"] {
            padding-top: 0px !important;
        }

        /* =========================================================
           MAP IFRAME
           ========================================================= */

        div[data-testid="stCustomComponentV1"],
        iframe {
            width: 100vw !important;
            height: calc(100vh - 190px) !important;
            margin: 0px !important;
            padding: 0px !important;
            border: none !important;
        }
    </style>
    """),
    unsafe_allow_html=True
)


# ================================================================
# CONSTANTS
# ================================================================

WAR_KEYWORDS = [
    "war",
    "bomb",
    "explosion",
    "strike",
    "missile",
    "shelling",
    "attack",
    "military",
    "air strike",
    "invasion",
    "blast",
    "combat",
    "troop",
    "forces",
    "clash",
    "conflict",
    "casualty",
    "offensive",
    "army",
    "gaza",
    "ukraine",
    "israel",
    "lebanon",
    "syria",
    "drone",
    "hezbollah",
    "houthi"
]


GEO_DATABASE = {
    "Gaza": [31.50, 34.46],
    "Ukraine": [48.37, 31.16],
    "Israel": [31.04, 34.85],
    "Lebanon": [33.85, 35.86],
    "Syria": [34.80, 38.99],
    "Taiwan": [23.69, 120.96],
    "Yemen": [15.55, 48.51],
    "Russia": [61.52, 105.31],
    "Iran": [32.42, 53.68],
    "Kyiv": [50.45, 30.52],
    "Beirut": [33.89, 35.50],
    "Tehran": [35.68, 51.38],
    "Moscow": [55.75, 37.61],
    "Tel Aviv": [32.08, 34.78],
    "Sweden": [60.12, 18.64],
    "Iraq": [33.22, 43.68],
    "Egypt": [26.82, 30.80],
    "Sudan": [12.86, 30.22],
    "Somalia": [5.15, 46.20],
    "Libya": [26.34, 17.23],
    "Poland": [51.92, 19.15],
    "Germany": [51.17, 10.45],
    "France": [46.23, 2.21],
    "Turkey": [38.96, 35.24]
}


REQUEST_HEADERS = {
    "User-Agent": "CrisisCommand/2.0 (+https://gdacs.org; disaster-feed-client)",
    "Accept": "application/json, application/xml, text/xml, application/atom+xml, */*",
}


# ================================================================
# BASIC HELPERS
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
    """
    Returns True only when a war/conflict keyword appears as a
    complete word.

    This prevents words such as 'warming' from matching 'war'.
    """
    text = f"{title} {summary}".lower()

    return any(
        re.search(
            rf"\b{re.escape(keyword)}\b",
            text
        )
        for keyword in WAR_KEYWORDS
    )


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
# VERIFIED DISASTER DATA FEEDS
# ================================================================

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


# ================================================================
# RSS / ATOM FETCHER
# ================================================================

@st.cache_data(ttl=120, show_spinner=False)
def fetch_rss(url, source_name, limit=8, only_relevant=False):

    articles = []

    try:
        response = requests.get(
            url,
            headers=REQUEST_HEADERS,
            timeout=15
        )

        response.raise_for_status()

        root = ET.fromstring(response.content)

        items = list(root.findall(".//item"))

        if not items:
            items = [
                n
                for n in root.iter()
                if n.tag.rsplit("}", 1)[-1].lower() == "entry"
            ]

        for item in items:

            title = _xml_local_text(
                item,
                "title"
            )

            description = _xml_local_text(
                item,
                "description",
                "summary",
                "content"
            )

            link = _xml_local_text(
                item,
                "link"
            )

            if not link:
                link = _xml_local_attr(
                    item,
                    "link",
                    "href"
                )

            if not title or not link:
                continue

            if only_relevant and not relevant(
                title,
                description
            ):
                continue

            # ----------------------------------------------------
            # GEO LOCATION
            # ----------------------------------------------------

            lat = None
            lon = None

            for node in item.iter():

                local = node.tag.rsplit(
                    "}",
                    1
                )[-1].lower()

                if local in {"point", "where"} and node.text:

                    parts = (
                        node.text
                        .replace(",", " ")
                        .split()
                    )

                    if len(parts) >= 2:
                        lat = _safe_float(parts[0])
                        lon = _safe_float(parts[1])
                        break

                if local in {"lat", "latitude"}:
                    lat = _safe_float(node.text)

                if local in {
                    "long",
                    "lon",
                    "longitude"
                }:
                    lon = _safe_float(node.text)

            location_name, coords = find_location(
                title,
                description
            )

            if lat is None or lon is None:
                lat, lon = coords

            articles.append(
                {
                    "title": title,
                    "link": link,
                    "location_name": location_name,
                    "lat": float(lat),
                    "lon": float(lon),
                    "source": source_name,
                    "summary": (
                        description[:190]
                        if description
                        else
                        "Open original source for details."
                    ),

                    # IMPORTANT:
                    # GDACS / ReliefWeb are blue data feeds.
                    "is_un_data": (
                        source_name.upper().startswith("GDACS")
                        or source_name.upper().startswith("RELIEFWEB")
                    ),
                }
            )

            if len(articles) >= limit:
                break

    except Exception:
        pass

    return articles


# ================================================================
# RELIEFWEB
# ================================================================

@st.cache_data(ttl=120, show_spinner=False)
def fetch_reliefweb(limit=15):

    articles = []

    appname = os.getenv(
        "RELIEFWEB_APPNAME",
        "crisis-command-streamlit"
    )

    url = "https://api.reliefweb.int/v2/reports"

    payload = {
        "limit": limit,
        "sort": ["date:desc"],
        "preset": "latest",
        "query": {
            "value": (
                "war OR conflict OR attack OR explosion "
                "OR military OR missile"
            )
        },
        "fields": {
            "include": [
                "title",
                "url",
                "primary_country",
                "source",
                "date"
            ]
        },
    }

    try:

        response = requests.post(
            url,
            params={"appname": appname},
            json=payload,
            headers={
                **REQUEST_HEADERS,
                "Content-Type": "application/json"
            },
            timeout=15
        )

        response.raise_for_status()

        for item in response.json().get(
            "data",
            []
        ):

            fields = item.get(
                "fields",
                {}
            )

            title = clean_text(
                fields.get(
                    "title",
                    ""
                )
            )

            if not title:
                continue

            countries = (
                fields.get(
                    "primary_country"
                )
                or {}
            )

            country_name = (
                countries.get("name")
                if isinstance(
                    countries,
                    dict
                )
                else None
            )

            location = (
                countries.get("location")
                if isinstance(
                    countries,
                    dict
                )
                else {}
            )

            lat = (
                _safe_float(
                    location.get("lat")
                )
                if isinstance(
                    location,
                    dict
                )
                else None
            )

            lon = (
                _safe_float(
                    location.get("lon")
                )
                if isinstance(
                    location,
                    dict
                )
                else None
            )

            if lat is None or lon is None:

                if country_name in GEO_DATABASE:
                    lat, lon = GEO_DATABASE[
                        country_name
                    ]
                else:
                    lat, lon = 20.0, 0.0

            source = fields.get(
                "source"
            ) or {}

            source_name = (
                source.get(
                    "shortname",
                    "RELIEFWEB"
                )
                if isinstance(
                    source,
                    dict
                )
                else "RELIEFWEB"
            )

            date_value = fields.get(
                "date"
            ) or {}

            date_text = (
                date_value.get(
                    "created"
                )
                if isinstance(
                    date_value,
                    dict
                )
                else str(
                    date_value or ""
                )
            )

            summary = (
                "Live ReliefWeb operational intelligence update"
                + (
                    f" — {date_text[:19]}"
                    if date_text
                    else ""
                )
                + "."
            )

            articles.append(
                {
                    "title": title,
                    "link": (
                        fields.get("url")
                        or
                        "https://reliefweb.int"
                    ),
                    "location_name": (
                        country_name
                        or
                        "Global"
                    ),
                    "lat": float(lat),
                    "lon": float(lon),
                    "source": str(
                        source_name
                    ).upper(),
                    "summary": summary,

                    # Blue data feed.
                    "is_un_data": True,
                }
            )

    except Exception:
        pass

    return articles


# ================================================================
# USGS GEOJSON
# ================================================================

@st.cache_data(ttl=60, show_spinner=False)
def fetch_usgs_geojson(limit=20):

    articles = []

    url = (
        "https://earthquake.usgs.gov/"
        "earthquakes/feed/v1.0/summary/"
        "all_day.geojson"
    )

    try:

        response = requests.get(
            url,
            headers=REQUEST_HEADERS,
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        for feature in data.get(
            "features",
            []
        )[:limit]:

            props = (
                feature.get("properties")
                or {}
            )

            coords = (
                feature.get("geometry")
                or {}
            ).get(
                "coordinates"
            ) or []

            if len(coords) < 2:
                continue

            lon = _safe_float(
                coords[0]
            )

            lat = _safe_float(
                coords[1]
            )

            if lat is None or lon is None:
                continue

            title = clean_text(
                props.get("title")
                or
                "USGS earthquake"
            )

            link = (
                props.get("url")
                or
                data.get(
                    "metadata",
                    {}
                ).get(
                    "url"
                )
                or
                "https://earthquake.usgs.gov/"
            )

            magnitude = props.get(
                "mag"
            )

            place = clean_text(
                props.get("place")
                or
                "Global"
            )

            time_ms = props.get(
                "time"
            )

            time_text = (
                time.strftime(
                    "%Y-%m-%d %H:%M UTC",
                    time.gmtime(
                        time_ms / 1000
                    )
                )
                if time_ms
                else ""
            )

            summary = (
                f"Magnitude {magnitude} — {place}"
                + (
                    f" — {time_text}"
                    if time_text
                    else ""
                )
            )

            articles.append(
                {
                    "title": title,
                    "link": link,
                    "location_name": place,
                    "lat": lat,
                    "lon": lon,
                    "source": "USGS",
                    "summary": summary,

                    # Blue data feed.
                    "is_un_data": True,
                }
            )

    except Exception:
        pass

    return articles


# ================================================================
# USGS ATOM
# ================================================================

@st.cache_data(ttl=60, show_spinner=False)
def fetch_usgs_atom(limit=12):

    articles = fetch_rss(
        (
            "https://earthquake.usgs.gov/"
            "earthquakes/feed/v1.0/summary/"
            "all_day.atom"
        ),
        "USGS",
        limit=limit,
        only_relevant=False
    )

    # Force USGS to blue/data classification.
    return [
        {
            **article,
            "is_un_data": True
        }
        for article in articles
    ]


# ================================================================
# LIVE MEDIA FEEDS
# ================================================================

def fetch_live_media():

    all_articles = []

    feeds = [
        (
            "BBC (UK)",
            "https://feeds.bbci.co.uk/news/rss.xml"
        ),
        (
            "SKY NEWS",
            "https://feeds.skynews.com/feeds/rss/home.xml"
        ),
        (
            "AL JAZEERA",
            "https://www.aljazeera.com/xml/rss/all.xml"
        ),
        (
            "THE GUARDIAN",
            "https://www.theguardian.com/world/rss"
        ),
        (
            "FRANCE 24",
            "https://www.france24.com/en/rss"
        ),
    ]

    for source, url in feeds:

        all_articles.extend(
            fetch_rss(
                url,
                source,
                limit=3,
                only_relevant=True
            )
        )

    # De-duplicate headlines.
    seen = set()
    unique = []

    for article in all_articles:

        key = article[
            "title"
        ].strip().lower()

        if key in seen:
            continue

        seen.add(key)
        unique.append(article)

    return unique


# ================================================================
# EXECUTE INGESTION PIPELINES
# ================================================================

feed_articles = []

feed_articles.extend(
    fetch_rss(
        FEED_CONFIG[0]["feed_url"],
        "GDACS",
        limit=8
    )
)

feed_articles.extend(
    fetch_rss(
        FEED_CONFIG[1]["feed_url"],
        "GDACS",
        limit=8
    )
)

feed_articles.extend(
    fetch_reliefweb(
        limit=15
    )
)

feed_articles.extend(
    fetch_usgs_geojson(
        limit=20
    )
)

feed_articles.extend(
    fetch_usgs_atom(
        limit=12
    )
)

# Red/media feeds.
feed_articles.extend(
    fetch_live_media()
)


# ================================================================
# GLOBAL DE-DUPLICATION
# ================================================================

seen = set()
mapped_alerts = []

for article in feed_articles:

    key = (
        article["title"]
        .strip()
        .lower(),
        round(
            article["lat"],
            3
        ),
        round(
            article["lon"],
            3
        )
    )

    if key in seen:
        continue

    seen.add(key)

    mapped_alerts.append(
        article
    )


# ================================================================
# ARTICLE VIEW
# ================================================================

requested_article = st.query_params.get(
    "article"
)

if requested_article is not None:

    try:
        article_idx = int(
            requested_article
        )
    except (
        TypeError,
        ValueError
    ):
        article_idx = None

    article = (
        mapped_alerts[
            article_idx
        ]
        if (
            article_idx is not None
            and
            0 <= article_idx < len(
                mapped_alerts
            )
        )
        else None
    )

    # ------------------------------------------------------------
    # ARTICLE PAGE STYLES
    # ------------------------------------------------------------

    st.markdown(
        _flatten_html("""
        <style>

        .stApp,
        .stAppViewContainer,
        .stAppViewBlockContainer,
        .main,
        .main .block-container {
            padding: 0px !important;
            margin: 0px !important;
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

        div[data-testid="stButton"] button[kind="secondary"] {
            background-color: #181d29 !important;
            color: #ffffff !important;
            border: 2px solid rgba(255,255,255,.18) !important;
            border-radius: 8px !important;
            padding: 10px 20px !important;
            font-size: 13px !important;
            font-weight: 800 !important;
            font-family: Arial, sans-serif !important;
            box-shadow: 0 6px 20px rgba(0,0,0,.5) !important;
            cursor: pointer !important;
        }

        div[data-testid="stButton"] button[kind="secondary"]:hover {
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

        .article-location {
            color: #75b9f5;
            font-size: 13px;
            font-weight: 900;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }

        .article-title {
            color: #fff;
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
            color: #fff;
            text-decoration: none !important;
            font-weight: 800;
            font-size: 14px;
            padding: 12px 24px;
            border-radius: 8px;
            border: none;
            cursor: pointer;
            font-family: Arial, sans-serif;
        }

        .article-open-btn:hover {
            background: #2c6cb0;
        }

        </style>
        """),
        unsafe_allow_html=True
    )

    # ------------------------------------------------------------
    # BACK BUTTON
    # ------------------------------------------------------------

    if st.button(
        "← Back to Map",
        key="back_to_map"
    ):

        st.query_params.clear()
        st.rerun()

    # ------------------------------------------------------------
    # ARTICLE CONTENT
    # ------------------------------------------------------------

    if article:

        open_article_js = (
            "window.location.href = "
            + json.dumps(
                str(
                    article["link"]
                )
            )
            + ";"
        )

        st.markdown(
            '<div class="article-wrap">'
            f'<div class="article-source-pill">'
            f'{html.escape(str(article["source"]))}'
            f'</div>'

            f'<div class="article-location">'
            f'📍 {html.escape(str(article["location_name"]))}'
            f'</div>'

            f'<div class="article-title">'
            f'{html.escape(str(article["title"]))}'
            f'</div>'

            f'<div class="article-summary">'
            f'{html.escape(str(article["summary"]))}'
            f'</div>'

            f'<button class="article-open-btn" '
            f'onclick="{html.escape(open_article_js, quote=True)}">'
            f'Open Full Article Source ↗'
            f'</button>'

            '</div>',
            unsafe_allow_html=True
        )

    else:

        st.markdown(
            '<div class="article-wrap">'
            '<div class="article-title">'
            'Article not found'
            '</div>'

            '<div class="article-summary">'
            'This item may have expired from the live '
            'tracking logs. Head back to the map view '
            'to see current parameters.'
            '</div>'

            '</div>',
            unsafe_allow_html=True
        )

    st.stop()


# ================================================================
# RED-PIN NEWS TICKER
# ================================================================
#
# IMPORTANT:
#
# ONLY items where:
#
#     is_un_data == False
#
# are placed into the ticker.
#
# Therefore:
#
#   🔴 RED  = media / war / conflict headline
#   🔵 BLUE = GDACS / ReliefWeb / USGS data
#
# Blue data remains on the map but NEVER appears in this ticker.
# ================================================================

source_alert_items = []


for alert_idx, item in enumerate(mapped_alerts):

    # ------------------------------------------------------------
    # ONLY RED PINS
    # ------------------------------------------------------------

    if item.get("is_un_data"):
        continue

    title_text = BeautifulSoup(
        str(
            item.get(
                "title",
                ""
            )
        ),
        "html.parser"
    ).get_text()

    title_text = clean_text(
        title_text
    )

    source_text = clean_text(
        str(
            item.get(
                "source",
                ""
            )
        )
    )

    location_text = clean_text(
        str(
            item.get(
                "location_name",
                ""
            )
        )
    )

    if not title_text:
        continue

    link = f"?article={alert_idx}"

    source_alert_items.append(
        '<div class="source-row">'

        '<div class="source-headline-wrap">'

        f'<span class="source-name">'
        f'{html.escape(source_text)}'
        f'</span>'

        f'<span class="source-location">'
        f'📍 {html.escape(location_text)}'
        f'</span>'

        '</div>'

        '<div class="source-headline">'

        f'<a href="{link}" target="_top">'
        f'{html.escape(title_text)} ↗'
        f'</a>'

        '</div>'

        '</div>'
    )


# ================================================================
# EMPTY RED FEED STATE
# ================================================================

if not source_alert_items:

    source_alert_items = [

        '<div class="source-row source-row-empty">'

        '<div class="source-headline-wrap">'

        '<span class="source-name">'
        'LIVE FEEDS'
        '</span>'

        '<span class="source-location">'
        '📡 MONITORING'
        '</span>'

        '</div>'

        '<div class="source-headline">'

        '<span>'
        'No live red-pin headlines available.'
        '</span>'

        '</div>'

        '</div>'
    ]


# ================================================================
# FRIENDSHIP BANNER
# ================================================================
#
# Expected file:
#
#     assets/infriendshipwith.png
#
# The banner is shown AFTER THE LAST RED HEADLINE.
# ================================================================

BANNER_PATH = (
    Path(__file__).resolve().parent
    / "assets"
    / "infriendshipwith.png"
)


def build_banner_html():

    if not BANNER_PATH.exists():

        return (
            '<div class="source-banner '
            'source-banner-missing">'

            '<span>'
            'IN FRIENDSHIP WITH: '
            'AIR BRUSSELS TIMES'
            '</span>'

            '</div>'
        )

    try:

        banner_bytes = (
            BANNER_PATH.read_bytes()
        )

        banner_b64 = base64.b64encode(
            banner_bytes
        ).decode("ascii")

        return (
            '<div class="source-banner">'

            f'<img '
            f'src="data:image/png;base64,{banner_b64}" '
            f'alt="In friendship with Air Brussels Times">'
            
            '</div>'
        )

    except Exception:

        return (
            '<div class="source-banner '
            'source-banner-missing">'

            '<span>'
            'IN FRIENDSHIP WITH: '
            'AIR BRUSSELS TIMES'
            '</span>'

            '</div>'
        )


banner_html = build_banner_html()


# ================================================================
# FINAL TICKER SEQUENCE
# ================================================================
#
# Example:
#
#   [RED 1]
#   [RED 2]
#   [RED 3]
#   [RED 4]
#   [BANNER]
#
# Then:
#
#   [RED 1]
#   [RED 2]
#   ...
#
# This continues indefinitely.
# ================================================================

ticker_items = (
    source_alert_items
    + [banner_html]
)


# ================================================================
# TICKER CSS
# ================================================================

st.markdown(
    _flatten_html("""
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

        border-top:
            1px solid
            rgba(255,255,255,.12);

        margin: 0;

        padding:
            9px
            22px
            12px
            22px;

        color: #e5e7eb;

        font-family: Arial, sans-serif;

        box-shadow:
            0 -6px 20px
            rgba(0,0,0,.4);

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

        overflow: hidden;

        opacity: 1;

        transition:
            opacity 0.35s ease;

        display: flex;

        align-items: center;

        justify-content: center;
    }


    .source-access-body.source-fading {
        opacity: 0;
    }


    /* ============================================================
       NEWS ROW
       ============================================================ */

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

        padding:
            3px
            7px;

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


    /* ============================================================
       FRIENDSHIP BANNER
       ============================================================ */

    .source-banner {

        width: 100%;
        height: 100%;

        display: flex;

        align-items: center;

        justify-content: center;

        overflow: hidden;

        box-sizing: border-box;
    }


    .source-banner img {

        display: block;

        width: 100%;

        max-width: 100%;

        height: auto;

        max-height: 100%;

        object-fit: contain;
    }


    .source-banner-missing {

        width: 100%;
        height: 100%;

        display: flex;

        align-items: center;

        justify-content: center;

        background: #ffffff;

        color: #202938;

        font-family: Georgia, serif;

        font-size: 26px;

        font-weight: 700;

        text-align: center;
    }


    .source-row-empty .source-name {
        background: #4a5568;
    }


    .source-row-empty .source-headline {
        color: #aab5c7;

        font-size: 12px;
    }

    </style>
    """),
    unsafe_allow_html=True
)


# ================================================================
# TICKER HTML + JAVASCRIPT
# ================================================================
#
# Every item is shown for 5 seconds.
#
# After the final RED headline:
#
#       RED LAST
#          ↓
#       BANNER
#          ↓
#       RED FIRST
#
# The sequence loops forever.
# ================================================================

st.markdown(
    _flatten_html(
        f"""
        <div class="source-access">

            <div class="source-access-head">

                <span>
                    🛰️ LIVE DATA SOURCES
                </span>

                <span>
                    LIVE PIN HEADLINES
                </span>

            </div>


            <div
                class="source-access-body"
                id="source-ticker-body"
            >
                {ticker_items[0]}
            </div>

        </div>


        <script>

        (function() {{

            var items =
                {json.dumps(ticker_items)};

            var idx = 0;

            var el =
                document.getElementById(
                    'source-ticker-body'
                );


            if (!el || items.length <= 1) {{
                return;
            }}


            /*
             * Each news headline and the banner
             * stays visible for 5 seconds.
             */
            var DISPLAY_TIME = 5000;


            /*
             * Fade transition duration.
             */
            var FADE_TIME = 350;


            setInterval(function() {{

                /*
                 * Fade current item out.
                 */
                el.classList.add(
                    'source-fading'
                );


                setTimeout(function() {{

                    /*
                     * Move to the next item.
                     *
                     * The modulo operation means:
                     *
                     * LAST ITEM -> FIRST ITEM
                     */
                    idx =
                        (idx + 1)
                        % items.length;


                    /*
                     * Replace the ticker content.
                     */
                    el.innerHTML =
                        items[idx];


                    /*
                     * Fade the new item in.
                     */
                    el.classList.remove(
                        'source-fading'
                    );

                }}, FADE_TIME);

            }}, DISPLAY_TIME);

        }})();

        </script>
        """
    ),
    unsafe_allow_html=True
)


# ================================================================
# MAP CANVAS
# ================================================================

live_pin_items = []


for alert_idx, item in enumerate(
    mapped_alerts
):

    try:

        lat = float(
            item.get("lat")
        )

        lon = float(
            item.get("lon")
        )

        if (
            -90.0 <= lat <= 90.0
            and
            -180.0 <= lon <= 180.0
        ):

            live_pin_items.append(
                (
                    alert_idx,
                    item,
                    lat,
                    lon
                )
            )

    except (
        TypeError,
        ValueError
    ):
        continue


# ================================================================
# MAP
# ================================================================

m = folium.Map(
    location=[
        20.0,
        0.0
    ],
    zoom_start=2,
    min_zoom=2,
    max_bounds=True,
    zoom_control=False,
    scrollWheelZoom=True,
    touchZoom=True
)


# ================================================================
# MAP TILES
# ================================================================

folium.TileLayer(
    tiles=(
        "https://{s}.basemaps.cartocdn.com/"
        "dark_all/{z}/{x}/{y}{r}.png"
    ),

    attr=(
        "&copy; OpenStreetMap "
        "&copy; CARTO"
    ),

    name="Dark Matter",

    subdomains="abcd",

    no_wrap=True

).add_to(m)


# ================================================================
# MAP BACKGROUND
# ================================================================

m.get_root().html.add_child(
    folium.Element(
        """
        <style>
            html,
            body {
                background: #262626 !important;
                margin: 0;
                padding: 0;
            }

            .leaflet-container {
                background: #262626 !important;
            }
        </style>
        """
    )
)


# ================================================================
# MAP PIN CLICK HANDLERS
# ================================================================

marker_click_scripts = []


for (
    alert_idx,
    item,
    lat,
    lon
) in live_pin_items:

    # ------------------------------------------------------------
    # BLUE VS RED
    # ------------------------------------------------------------

    if item["is_un_data"]:

        m_color = "#3182ce"
        b_color = "#63b3ed"

    else:

        m_color = "#ff4b4b"
        b_color = "#ff8080"


    # ------------------------------------------------------------
    # POPUP
    # ------------------------------------------------------------

    popup_html = (

        '<div '
        'style="'
        'font-family:sans-serif; '
        'font-size:12px; '
        'width:240px; '
        'color:#1a1f2c; '
        'line-height:1.4;'
        '">'

        '<span '
        'style="'
        'color:#718096; '
        'font-weight:800; '
        'font-size:10px; '
        'text-transform:uppercase;'
        '">'

        f'📍 '
        f'{html.escape(str(item["location_name"]))}'
        f' — '
        f'{html.escape(str(item["source"]))}'

        '</span>'

        '<br>'

        f'<a '
        f'href="?article={alert_idx}" '
        f'target="_top" '
        f'style="'
        f'text-decoration:none; '
        f'font-weight:700; '
        f'color:{m_color}; '
        f'display:inline-block; '
        f'margin-top:4px;'
        f'">'

        f'{html.escape(str(item["title"]))} ↗'

        '</a>'

        '</div>'
    )


    # ------------------------------------------------------------
    # CIRCLE MARKER
    # ------------------------------------------------------------

    marker = folium.CircleMarker(

        location=[
            lat,
            lon
        ],

        radius=(
            11
            if item["is_un_data"]
            else 9
        ),

        popup=folium.Popup(
            popup_html,
            max_width=280
        ),

        color=b_color,

        fill=True,

        fill_color=m_color,

        fill_opacity=0.75

    )

    marker.add_to(m)


    # ------------------------------------------------------------
    # CLICK = ZOOM
    # ------------------------------------------------------------

    marker_click_scripts.append(

        f"{marker.get_name()}.on("
        f"'click', "
        f"function(e) {{"

        f"{m.get_name()}.flyTo("
        f"e.latlng, "
        f"Math.max("
        f"{m.get_name()}.getZoom(), "
        f"6"
        f"), "
        f"{{duration: 0.75}}"
        f");"

        f"}}"
        f");"
    )


# ================================================================
# DEFERRED MARKER CLICK HANDLERS
# ================================================================

if marker_click_scripts:

    deferred_click_script = (

        "document.addEventListener("
        "'DOMContentLoaded', "
        "function(){"

        +
        "".join(
            marker_click_scripts
        )

        +
        "});"
    )

    m.get_root().html.add_child(
        folium.Element(
            "<script>"
            + deferred_click_script
            + "</script>"
        )
    )


# ================================================================
# DEFAULT MAP FOCUS
# ================================================================

focus_pin_items = [

    item_tuple

    for item_tuple in live_pin_items

    if not item_tuple[1]["is_un_data"]

]


# If there are no red pins, use all live pins.
if not focus_pin_items:

    focus_pin_items = live_pin_items


# ================================================================
# FIT MAP TO PINS
# ================================================================

if live_pin_items:

    lats = [
        lat
        for _, _, lat, _
        in focus_pin_items
    ]

    lons = [
        lon
        for _, _, _, lon
        in focus_pin_items
    ]


    # ------------------------------------------------------------
    # SINGLE PIN
    # ------------------------------------------------------------

    if len(focus_pin_items) == 1:

        m.location = [
            lats[0],
            lons[0]
        ]

        m.options["zoom"] = 8


    # ------------------------------------------------------------
    # MULTIPLE PINS
    # ------------------------------------------------------------

    else:

        south = min(lats)
        north = max(lats)

        west = min(lons)
        east = max(lons)

        raw_span = east - west

        lat_span = north - south

        lon_span = raw_span


        # Tight map padding.
        lat_pad = max(
            1.0,
            lat_span * 0.08
        )

        lon_pad = max(
            1.5,
            lon_span * 0.08
        )


        south = max(
            -90.0,
            south - lat_pad
        )

        north = min(
            90.0,
            north + lat_pad
        )


        west_bound = max(
            -180.0,
            west - lon_pad
        )

        east_bound = min(
            180.0,
            east + lon_pad
        )


        m.fit_bounds(
            [
                [
                    south,
                    west_bound
                ],
                [
                    north,
                    east_bound
                ]
            ],

            padding=(
                10,
                10
            ),

            max_zoom=10
        )


# ================================================================
# MAP SIZE / RESIZE FIX
# ================================================================

if live_pin_items:

    if len(focus_pin_items) == 1:

        _reapply_view_js = (

            f"{m.get_name()}.setView("
            f"[{lats[0]}, {lons[0]}], "
            f"8"
            f");"

        )

    else:

        _reapply_view_js = (

            f"{m.get_name()}.fitBounds("
            f"[["
            f"{south}, "
            f"{west_bound}"
            f"], ["
            f"{north}, "
            f"{east_bound}"
            f"]], "
            f"{{padding: [10, 10], maxZoom: 10}}"
            f");"

        )


    resize_fix_script = (

        "<script>"

        f"function __fixMapView(){{"
        f"try {{"

        f"{m.get_name()}.invalidateSize();"

        f"{_reapply_view_js}"

        f"}} catch(e) {{}}"
        f"}}"

        "window.addEventListener("
        "'load', "
        "function(){"

        "__fixMapView();"

        "setTimeout("
        "__fixMapView, "
        "200"
        ");"

        "setTimeout("
        "__fixMapView, "
        "600"
        ");"

        "setTimeout("
        "__fixMapView, "
        "1200"
        ");"

        "});"

        "window.addEventListener("
        "'resize', "
        "__fixMapView"
        ");"


        "if (window.ResizeObserver) {"

        "new ResizeObserver("
        "__fixMapView"
        ").observe("
        "document.body"
        ");"

        "}"

        "</script>"
    )


    m.get_root().html.add_child(
        folium.Element(
            resize_fix_script
        )
    )


# ================================================================
# MAP RENDER
# ================================================================

st_folium(
    m,
    width="100%",
    height=680,
    returned_objects=[],
    key="tactical_map_flush_v31"
)

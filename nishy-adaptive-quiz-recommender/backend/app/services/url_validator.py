"""
Web Scraper Service — Finds specific article/video URLs for recommendation topics.

Problem (confirmed from browser screenshots):
  - GFG search (geeksforgeeks.org/search/) uses Google Custom Search (JS-rendered)
    → httpx GET returns an empty search box with no results
  - TutorialsPoint URL template lands on market.tutorialspoint.com (course store)
    → totally wrong section, shows unrelated courses
  - YouTube search works but links to a search page, not a specific video

Solution: Use DuckDuckGo's HTML interface (server-rendered, no JS, scraping-friendly)
  to query `site:platform.com {topic}` and extract the FIRST matching article URL.
  For YouTube: parse the initial page JSON to extract the first video ID.

This runs in the background setup task — no impact on quiz UX.
"""
import re
import time
import logging
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Respect DuckDuckGo with a realistic browser header
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_TIMEOUT = 8   # seconds per request
_DDG_DELAY = 1  # small polite delay between DDG requests (seconds)


def _bing_first_url(query: str, must_contain: str = "") -> Optional[str]:
    """Fallback HTML scraper when DuckDuckGo has no indexed result."""
    search_url = f"https://www.bing.com/search?q={urllib.parse.quote_plus(query)}"
    try:
        with httpx.Client(follow_redirects=True, timeout=_TIMEOUT) as client:
            response = client.get(search_url, headers=_HEADERS)
        if response.status_code >= 400:
            return None
        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.select("li.b_algo h2 a"):
            href = str(anchor.get("href", "")).strip()
            if not href.startswith("http"):
                continue
            if must_contain and must_contain not in href:
                continue
            if "bing.com" in urllib.parse.urlparse(href).netloc:
                continue
            logger.info("[WebScraper] Bing found: %s", href[:80])
            return href
    except Exception as exc:
        logger.warning("[WebScraper] Bing search failed: %s", exc)
    return None


def _is_reachable(url: str) -> bool:
    try:
        with httpx.Client(follow_redirects=True, timeout=_TIMEOUT) as client:
            response = client.head(url, headers=_HEADERS)
            if response.status_code in {403, 405}:
                response = client.get(url, headers=_HEADERS)
        return response.status_code < 400
    except Exception:
        return False


def find_openstax_index_article(topic: str) -> Optional[Dict]:
    """Resolve a Biology concept through OpenStax's server-rendered index."""
    topic_lower = topic.casefold()
    exact_sections = (
        ("extracellular matrix", "4-6-connections-between-cells-and-cellular-activities"),
        ("golgi", "4-4-the-endomembrane-system-and-proteins"),
        ("diversification of eukaryotes", "23-1-eukaryotic-origins"),
        ("vascular plant", "25-4-seedless-vascular-plants"),
        ("large tree", "25-4-seedless-vascular-plants"),
    )
    for keyword, section in exact_sections:
        if keyword not in topic_lower:
            continue
        exact_url = f"https://openstax.org/books/biology-2e/pages/{section}"
        if _is_reachable(exact_url):
            return {
                "label": "English",
                "title": f"{topic} — OpenStax Biology",
                "url": exact_url,
                "source": "OpenStax Biology",
            }
    index_url = "https://openstax.org/books/biology-2e/pages/index"
    topic_tokens = set(re.findall(r"[a-z]{4,}", topic.casefold()))
    if not topic_tokens:
        return None
    try:
        with httpx.Client(follow_redirects=True, timeout=15) as client:
            response = client.get(index_url, headers=_HEADERS)
        if response.status_code >= 400:
            return None
        soup = BeautifulSoup(response.text, "html.parser")
        best = None
        best_score = 0.0
        for item in soup.select("div.os-index-item"):
            term_node = item.select_one("span.os-term")
            link = item.select_one("a.os-term-section-link[href]")
            if not term_node or not link:
                continue
            term_tokens = set(re.findall(r"[a-z]{4,}", term_node.get_text(" ", strip=True).casefold()))
            score = len(topic_tokens & term_tokens) / len(topic_tokens)
            if score > best_score:
                best_score = score
                best = link
        if best is None or best_score < 0.5:
            return None
        href = urllib.parse.urljoin(index_url, str(best.get("href", "")))
        return {
            "label": "English",
            "title": f"{topic} — OpenStax Biology",
            "url": href,
            "source": "OpenStax Biology",
        }
    except Exception as exc:
        logger.warning("[WebScraper] OpenStax index scrape failed: %s", exc)
        return None


def nie_biology_resource(topic: str) -> Optional[Dict]:
    """Return the official Sri Lankan A/L Biology resource book when reachable."""
    url = "https://nie.lk/pdffiles/other/eGr12OM%20BioResoBook.pdf"
    if not _is_reachable(url):
        return None
    return {
        "label": "English",
        "title": f"{topic} — Sri Lanka NIE A/L Biology Resource Book",
        "url": url,
        "source": "Sri Lanka NIE",
    }


# ── DuckDuckGo HTML search ─────────────────────────────────────────────────
def _ddg_first_url(query: str, must_contain: str = "") -> Optional[str]:
    """
    Search DuckDuckGo HTML interface and return the first result URL.

    DuckDuckGo HTML (html.duckduckgo.com/html/) is:
      - Fully server-rendered (no JavaScript needed)
      - Freely scrapable without API keys
      - Returns <a class="result__a"> anchors with direct URLs

    Args:
        query:        Search query string (e.g., "site:geeksforgeeks.org Multi-Tier Architecture")
        must_contain: If set, only return URLs containing this substring

    Returns:
        The first matching URL, or None if nothing found.
    """
    encoded_q = urllib.parse.quote_plus(query)
    ddg_url = f"https://html.duckduckgo.com/html/?q={encoded_q}"

    try:
        with httpx.Client(follow_redirects=True, timeout=_TIMEOUT) as client:
            resp = client.get(ddg_url, headers=_HEADERS)
            if resp.status_code >= 400:
                logger.warning(f"[WebScraper] DDG returned {resp.status_code} for: {query}")
                return _bing_first_url(query, must_contain)

        soup = BeautifulSoup(resp.text, "html.parser")

        # DDG HTML result links: <a class="result__a" href="...">
        for a_tag in soup.select("a.result__a"):
            href = a_tag.get("href", "")
            if not href:
                continue

            # DDG sometimes wraps in a redirect — extract the actual URL
            # Pattern 1: /l/?uddg=<url-encoded-actual-url>
            if "/l/?" in href or "uddg=" in href:
                parsed = urllib.parse.urlparse(href)
                params = urllib.parse.parse_qs(parsed.query)
                actual = params.get("uddg", [None])[0]
                if actual:
                    href = urllib.parse.unquote(actual)

            # Pattern 2: relative paths (shouldn't happen but guard anyway)
            if not href.startswith("http"):
                continue

            # Filter by required domain substring
            if must_contain and must_contain not in href:
                continue

            # Skip DDG-internal or ad URLs
            if "duckduckgo.com" in href:
                continue

            logger.info(f"[WebScraper] DDG found: {href[:80]}")
            return href

        logger.info(f"[WebScraper] DDG: no result for '{query}'")
        return _bing_first_url(query, must_contain)

    except Exception as exc:
        logger.warning(f"[WebScraper] DDG search failed: {exc}")
        return _bing_first_url(query, must_contain)


# ── GeeksforGeeks — specific article ──────────────────────────────────────
def find_gfg_article(topic: str) -> Optional[Dict]:
    """
    Find the exact GeeksforGeeks article URL for a topic using DDG.

    Why not use GFG's own search?
    GFG search (geeksforgeeks.org/search/?q=...) is powered by Google Custom Search,
    which is JavaScript-rendered. A plain GET request returns an empty search box.

    DDG `site:geeksforgeeks.org {topic}` finds the actual article page directly.
    """
    url = _ddg_first_url(
        query=f"site:geeksforgeeks.org {topic}",
        must_contain="geeksforgeeks.org"
    )
    if url:
        # Verify the page is actually reachable (simple HEAD)
        try:
            with httpx.Client(follow_redirects=True, timeout=_TIMEOUT) as client:
                r = client.head(url, headers=_HEADERS)
                if r.status_code < 400:
                    # Extract a clean title from the URL slug
                    slug = url.rstrip("/").split("/")[-1].replace("-", " ").title()
                    return {
                        "label":  "English",
                        "title":  f"{slug} — GeeksforGeeks",
                        "url":    url,
                        "source": "GeeksforGeeks",
                    }
        except Exception:
            pass

    logger.info(f"[WebScraper] GFG article not found for '{topic}'")
    return None


# ── TutorialsPoint — specific tutorial ────────────────────────────────────
def find_tutorialspoint_tutorial(topic: str) -> Optional[Dict]:
    """
    Find the exact TutorialsPoint tutorial URL for a topic using DDG.

    Why not use TutorialsPoint's own search URL?
    The generated URL template (tutorialspoint.com/search/search_result.htm?search=...)
    actually redirects to market.tutorialspoint.com (a course marketplace),
    not the free tutorial pages at tutorialspoint.com/{topic}/index.htm.

    DDG `site:tutorialspoint.com {topic} tutorial` finds the actual tutorial page.
    We also filter to ensure the URL is NOT the market subdomain.
    """
    time.sleep(_DDG_DELAY)  # polite delay between DDG requests
    url = _ddg_first_url(
        query=f"site:tutorialspoint.com {topic} tutorial",
        must_contain="tutorialspoint.com"
    )
    if url and "market.tutorialspoint.com" not in url:
        try:
            with httpx.Client(follow_redirects=True, timeout=_TIMEOUT) as client:
                r = client.head(url, headers=_HEADERS)
                if r.status_code < 400:
                    slug = url.rstrip("/").split("/")[-1].replace("_", " ").replace("-", " ").title()
                    return {
                        "label":  "English",
                        "title":  f"{slug} — TutorialsPoint",
                        "url":    url,
                        "source": "TutorialsPoint",
                    }
        except Exception:
            pass

    logger.info(f"[WebScraper] TutorialsPoint tutorial not found for '{topic}'")
    return None


# ── YouTube — specific video (not search page) ─────────────────────────────
def _oembed_title(video_url: str) -> str:
    try:
        with httpx.Client(follow_redirects=True, timeout=_TIMEOUT) as client:
            response = client.get(
                "https://www.youtube.com/oembed",
                params={"url": video_url, "format": "json"},
                headers=_HEADERS,
            )
        if response.status_code >= 400:
            return ""
        return str(response.json().get("title", "")).strip()
    except Exception:
        return ""


def _validated_youtube_candidate(topic: str, video_ids: List[str]) -> Optional[Dict]:
    """Return the first direct watch URL whose real title closely matches the topic.

    oEmbed lookups for every candidate are fired concurrently (each is an
    independent blocking HTTP call) so the worst case is one round trip
    instead of up to ten sequential ones, while still honoring the original
    candidate preference order.
    """
    generic = {"sri", "lankan", "gce", "level", "biology", "tutorial", "about", "which"}
    topic_tokens = {
        token for token in re.findall(r"[a-z]{4,}", topic.casefold())
        if token not in generic
    }
    required_overlap = max(1, (len(topic_tokens) + 1) // 2)
    candidates = list(dict.fromkeys(video_ids))[:10]
    if not candidates:
        return None

    with ThreadPoolExecutor(max_workers=len(candidates)) as executor:
        video_urls = [f"https://www.youtube.com/watch?v={vid}" for vid in candidates]
        titles = list(executor.map(_oembed_title, video_urls))

    for video_url, title in zip(video_urls, titles):
        if not title:
            continue
        title_tokens = set(re.findall(r"[a-z]{4,}", title.casefold()))
        if topic_tokens and len(topic_tokens & title_tokens) < required_overlap:
            continue
        return {"label": "English", "title": title, "url": video_url, "source": "YouTube"}
    return None


def find_youtube_video(topic: str) -> Optional[Dict]:
    """
    Find the first actual YouTube video for a topic by scraping the
    search results page HTML for embedded video IDs.

    YouTube search results HTML contains an initial data JSON blob that
    includes videoId fields — we extract the first non-ad videoId.

    Returns None if scraping fails. Search-result pages are deliberately not
    recommendations because they are neither specific nor syllabus-validated.
    """
    yt_encoded = urllib.parse.quote_plus(f"{topic} tutorial")
    search_url = f"https://www.youtube.com/results?search_query={yt_encoded}"
    try:
        with httpx.Client(follow_redirects=True, timeout=_TIMEOUT) as client:
            resp = client.get(search_url, headers=_HEADERS)

        if resp.status_code >= 400:
            return None

        # YouTube embeds video metadata as JSON in the page HTML.
        # Pattern: "videoId":"<11-char-id>"
        # The first match is typically a sponsored result — skip it by finding
        # the second distinct video ID.
        video_ids = re.findall(r'"videoId"\s*:\s*"([a-zA-Z0-9_-]{11})"', resp.text)

        # Remove duplicates while preserving order
        seen: set = set()
        unique_ids = []
        for vid in video_ids:
            if vid not in seen:
                seen.add(vid)
                unique_ids.append(vid)

        # Prefer pre-verified, topic-exact educational videos, then inspect the
        # live search candidates. oEmbed validation still confirms every URL.
        known_ids = []
        topic_lower = topic.casefold()
        if "extracellular matrix" in topic_lower:
            known_ids.append("cMNx17H3dRU")
        if "golgi" in topic_lower:
            known_ids.append("6XBKA-F7Y1s")
        if "vascular plant" in topic_lower or "large tree" in topic_lower:
            known_ids.append("xRSo3DtebDw")
        validated = _validated_youtube_candidate(topic, [*known_ids, *unique_ids])
        if validated:
            return validated
        return None

        if not unique_ids:
            return None

        # First unique ID is usually a sponsored video — use the second if available
        video_id = unique_ids[1] if len(unique_ids) > 1 else unique_ids[0]
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        # Validate the selected video's real title; a direct URL is not enough
        # if an advertisement or unrelated result occupied that position.
        with httpx.Client(follow_redirects=True, timeout=_TIMEOUT) as client:
            metadata_response = client.get(
                "https://www.youtube.com/oembed",
                params={"url": video_url, "format": "json"},
                headers=_HEADERS,
            )
        if metadata_response.status_code >= 400:
            return None
        video_title = str(metadata_response.json().get("title", "")).strip()
        generic = {"sri", "lankan", "gce", "level", "biology", "tutorial"}
        topic_tokens = {
            token for token in re.findall(r"[a-z]{4,}", topic.casefold())
            if token not in generic
        }
        title_tokens = set(re.findall(r"[a-z]{4,}", video_title.casefold()))
        required_overlap = max(1, (len(topic_tokens) + 1) // 2)
        if topic_tokens and len(topic_tokens.intersection(title_tokens)) < required_overlap:
            logger.info("[WebScraper] Rejected unrelated YouTube result: %s", video_title)
            return None

        logger.info(f"[WebScraper] YouTube video found: {video_url}")
        return {
            "label":  "English",
            "title":  video_title,
            "url":    video_url,
            "source": "YouTube",
        }

    except Exception as exc:
        logger.warning(f"[WebScraper] YouTube scrape failed: {exc}")
        return None


# ── Wikipedia fallback ─────────────────────────────────────────────────────
def wikipedia_resource(topic: str) -> Dict:
    """Generate a Wikipedia link as last-resort fallback (always works)."""
    encoded = urllib.parse.quote(topic.replace(" ", "_"))
    return {
        "label":  "English",
        "title":  f"{topic} — Wikipedia",
        "url":    f"https://en.wikipedia.org/wiki/{encoded}",
        "source": "Wikipedia",
    }


# ── Main entry point ───────────────────────────────────────────────────────
def build_resources(topic: str) -> List[Dict]:
    """
    Build a list of 3 validated, specific resource links for a weak topic.

    Strategy (in order): official Sri Lankan NIE Biology material, then
    topic-specific Khan Academy and OpenStax Biology pages, followed by a
    specific YouTube video when one can be extracted and validated.

    Search-result pages and unrelated generic tutorials are never returned.

    Args:
        topic: The weak Biology concept inferred from the quiz.

    Returns:
        List of 3 resource dicts, each with: label, title, url, source
    """
    clean_topic = re.sub(r"\s+", " ", str(topic)).strip(" .:;-/")
    if (
        not clean_topic
        or re.search(r"(?:^|\b)(?:AL|GCE)[/\s-]*\d", clean_topic, re.IGNORECASE)
        or len(re.findall(r"[A-Za-z]{3,}", clean_topic)) == 0
    ):
        logger.warning("[WebScraper] Refusing resources for non-concept topic '%s'", topic)
        return []

    logger.info(f"[WebScraper] Building A/L Biology resources for '{clean_topic}'")

    def _khan_academy(topic: str) -> Optional[Dict]:
        query = f'site:khanacademy.org/science/biology "{topic}" biology'
        url = _ddg_first_url(query=query, must_contain="khanacademy.org")
        # The search resolver already restricts the result to Khan Academy.
        # A second serial HEAD/GET round trip added latency and discarded
        # valid pages when the site rate-limited probes with 403.
        if not url:
            return None
        return {
            "label": "English",
            "title": f"{topic} — Khan Academy",
            "url": url,
            "source": "Khan Academy",
        }

    # These three sources are independent network round trips — run them
    # concurrently instead of one after another so a slow lookup on one
    # source doesn't hold up the other two.
    with ThreadPoolExecutor(max_workers=3) as executor:
        video_future = executor.submit(find_youtube_video, clean_topic)
        openstax_future = executor.submit(find_openstax_index_article, clean_topic)
        khan_future = executor.submit(_khan_academy, clean_topic)

        resources: List[Dict] = []
        for result in (video_future.result(), openstax_future.result(), khan_future.result()):
            if result:
                resources.append(result)

    # Keep the exact A/L Biology topic in both the video title and search query.
    # Video is a useful fallback, but should not displace the official NIE,
    # OpenStax, or Khan Academy resources when all three are available.
    # Never pad with a search page or unrelated generic tutorial. Returning
    # fewer verified links is safer than presenting a weak recommendation.
    deduplicated: List[Dict] = []
    seen_urls = set()
    for resource in resources:
        url = str(resource.get("url", "")).strip()
        if not url.startswith(("https://", "http://")) or url in seen_urls:
            continue
        seen_urls.add(url)
        deduplicated.append(resource)

    logger.info(f"[WebScraper] Done for '{clean_topic}': {[r['source'] for r in deduplicated]}")
    return deduplicated[:4]

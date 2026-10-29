"""Web and YouTube search used by Milky's search tools.

Search results include titles, links, snippets and, for the top web results,
short excerpts read from the pages themselves.  The model therefore answers
from the result content instead of only opening a search page.
"""

import ipaddress
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from urllib.parse import parse_qs, unquote, urlencode, urlsplit

import requests


def _int_env(variable, default, minimum, maximum):
    try:
        value = int(os.environ.get(variable, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _bool_env(variable, default):
    value = os.environ.get(variable)
    if value is None:
        return default
    return value.strip().lower() not in {"", "0", "false", "no", "off"}


SEARCH_ENABLED = _bool_env("SEARCH_ENABLED", True)
SEARCH_MAX_RESULTS = _int_env("SEARCH_MAX_RESULTS", 5, 1, 10)
SEARCH_REGION = os.environ.get("SEARCH_REGION", "ru-ru").strip() or "ru-ru"
SEARCH_SAFESEARCH = (
    os.environ.get("SEARCH_SAFESEARCH", "moderate").strip() or "moderate"
)
SEARCH_TIMEOUT = _int_env("SEARCH_TIMEOUT", 6, 3, 60)
SEARCH_PAGE_TIMEOUT = _int_env("SEARCH_PAGE_TIMEOUT", 8, 3, 30)
SEARCH_GOOGLE = _bool_env("SEARCH_GOOGLE", True)
SEARCH_GOOGLE_TIMEOUT = _int_env("SEARCH_GOOGLE_TIMEOUT", 2, 2, 30)
SEARCH_YOUTUBE = _bool_env("SEARCH_YOUTUBE", True)
SEARCH_YOUTUBE_TIMEOUT = _int_env("SEARCH_YOUTUBE_TIMEOUT", 12, 3, 60)

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
YOUTUBE_USER_AGENT = USER_AGENT

STOPWORDS = {
    "the", "and", "for", "with", "what", "when", "where", "which", "who",
    "how", "why", "this", "that", "from", "about", "into", "today",
    "now", "please", "tell", "give", "find", "show", "search",
    "что", "как", "где", "когда", "какой", "какая", "какие", "кто",
    "чем", "это", "этот", "эта", "для", "про", "над", "под", "при",
    "или", "если", "ещё", "еще", "уже", "сейчас", "сегодня", "завтра",
    "пожалуйста", "найди", "покажи", "расскажи", "скажи", "дай",
    "мне", "меня", "тебе", "тебя", "его", "её", "ее", "их", "все",
    "всё", "был", "была", "были", "есть", "очень", "можно",
}

# Search engines occasionally return unrelated adult pages when they see a
# bot-like request.  Never pass those results to the model.
BLOCKED_HOSTS = {
    "pornhub.com",
    "xnxx.com",
    "xvideos.com",
    "xhamster.com",
    "redtube.com",
    "youporn.com",
    "onlyfans.com",
}


def configure_search(settings):
    """Apply search options from settings.json at runtime."""
    global SEARCH_ENABLED, SEARCH_MAX_RESULTS, SEARCH_REGION
    global SEARCH_SAFESEARCH, SEARCH_GOOGLE, SEARCH_YOUTUBE
    if not isinstance(settings, dict):
        return
    SEARCH_ENABLED = bool(settings.get("enabled", SEARCH_ENABLED))
    try:
        max_results = int(settings.get("max_results", SEARCH_MAX_RESULTS))
    except (TypeError, ValueError):
        max_results = SEARCH_MAX_RESULTS
    SEARCH_MAX_RESULTS = max(1, min(10, max_results))
    region = str(settings.get("region", SEARCH_REGION)).strip()
    SEARCH_REGION = region or "ru-ru"
    safesearch = str(
        settings.get("safesearch", SEARCH_SAFESEARCH)
    ).strip().lower()
    if safesearch not in {"on", "moderate", "off"}:
        safesearch = "moderate"
    SEARCH_SAFESEARCH = safesearch
    SEARCH_GOOGLE = bool(settings.get("google", SEARCH_GOOGLE))
    SEARCH_YOUTUBE = bool(settings.get("youtube", SEARCH_YOUTUBE))


def search_enabled():
    return SEARCH_ENABLED


def _request_headers(language=None):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "*/*;q=0.8"
        ),
    }
    if language:
        headers["Accept-Language"] = f"{language},en;q=0.8"
    return headers


def _safe_search_value():
    return {
        "on": "1",
        "off": "-2",
    }.get(SEARCH_SAFESEARCH, "-1")


def _valid_url(url):
    if not url or any(char.isspace() for char in url):
        return False
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if any(
        host == blocked or host.endswith("." + blocked)
        for blocked in BLOCKED_HOSTS
    ):
        return False
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            return False
    return (
        parsed.scheme.lower() in ("http", "https")
        and bool(parsed.netloc)
        and not parsed.username
        and not parsed.password
    )


def _clean_text(value, limit):
    return " ".join(str(value or "").split())[:limit]


def _clean_markdown(value, limit=500):
    text = str(value or "")
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[*_`#>]+", " ", text)
    text = unescape(text)
    return _clean_text(text, limit)


def _decode_result_url(url):
    href = str(url or "").strip()
    if href.startswith("//"):
        href = "https:" + href
    try:
        parsed = urlsplit(href)
    except ValueError:
        return ""
    host = (parsed.hostname or "").lower()
    if host.endswith("duckduckgo.com") or host.endswith("bing.com"):
        query = parse_qs(parsed.query)
        for key in ("uddg", "u", "url"):
            value = (query.get(key) or [""])[0]
            if value:
                href = unquote(value)
                break
    if href.startswith("//"):
        href = "https:" + href
    return href


def _merge_results(results, extra, limit):
    known = {item["url"] for item in results}
    for item in extra:
        if item["url"] in known:
            continue
        results.append(item)
        known.add(item["url"])
        if len(results) >= limit:
            break
    return results


def _query_stems(query):
    words = re.findall(r"[a-zа-яё0-9]{3,}", str(query or "").casefold())
    stems = []
    for word in words:
        if word in STOPWORDS:
            continue
        stem = word[:5]
        if stem not in stems:
            stems.append(stem)
    return stems


def _result_score(stems, item):
    haystack = (
        str(item.get("title") or "") + " " + str(item.get("snippet") or "")
    ).casefold()
    return sum(1 for stem in stems if stem in haystack)


def _rank_results(query, results):
    stems = _query_stems(query)
    if not stems:
        return results
    scored = []
    for index, item in enumerate(results):
        score = _result_score(stems, item)
        if score:
            scored.append((score, index, item))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [item for _score, _index, item in scored]


def _simplify_query(query):
    words = re.findall(r"[^\W_]+(?:[-'][^\W_]+)*", str(query or ""), re.UNICODE)
    kept = [word for word in words if word.casefold() not in STOPWORDS]
    if len(kept) < 2:
        kept = words
    return " ".join(kept[:8]).strip()


def _lite_search(query, limit):
    """Search DuckDuckGo Lite directly."""
    response = requests.get(
        "https://lite.duckduckgo.com/lite/",
        params={
            "q": query,
            "kl": SEARCH_REGION,
            "kp": _safe_search_value(),
        },
        headers=_request_headers(SEARCH_REGION),
        timeout=SEARCH_TIMEOUT,
    )
    if response.status_code != 200:
        return []

    blocks = re.split(
        r'(?=<a\b[^>]*class=["\'][^"\']*result-link[^"\']*["\'])',
        response.text,
        flags=re.IGNORECASE,
    )
    results = []
    for block in blocks[1:]:
        match = re.match(r"<a\b([^>]*)>(.*?)</a>", block, re.S | re.I)
        if not match:
            continue
        attrs = match.group(1)
        title = _clean_markdown(re.sub(r"<[^>]+>", " ", match.group(2)), 240)
        href_match = re.search(r'href=["\']([^"\']+)["\']', attrs, re.I)
        if not href_match:
            continue
        url = _decode_result_url(unescape(href_match.group(1)))
        if not _valid_url(url):
            continue
        snippet_match = re.search(
            r'<td[^>]*class=["\'][^"\']*result-snippet[^"\']*["\'][^>]*>'
            r"(.*?)</td>",
            block,
            re.S | re.I,
        )
        snippet = ""
        if snippet_match:
            snippet = _clean_markdown(
                re.sub(r"<[^>]+>", " ", snippet_match.group(1)), 500
            )
        results.append(
            {"title": title or url, "url": url, "snippet": snippet}
        )
        if len(results) >= limit:
            break
    return results


def _jina_search(query, limit):
    """Search DuckDuckGo through Jina Reader when direct access is blocked."""
    target = "http://lite.duckduckgo.com/lite/?" + urlencode(
        {
            "q": query,
            "kl": SEARCH_REGION,
            "kp": _safe_search_value(),
        }
    )
    response = requests.get(
        "https://r.jina.ai/" + target,
        headers=_request_headers(SEARCH_REGION),
        timeout=max(SEARCH_TIMEOUT, 12),
    )
    if response.status_code != 200:
        return []
    content = response.text
    marker = content.find("Markdown Content:")
    if marker >= 0:
        content = content[marker + len("Markdown Content:") :]

    matches = list(
        re.finditer(
            r"^\s*\d+\.\s*\[([^\]]+)\]\(([^)]+)\)\s*$",
            content,
            re.MULTILINE,
        )
    )
    results = []
    for index, match in enumerate(matches):
        title = _clean_markdown(match.group(1), 240)
        url = _decode_result_url(match.group(2))
        if not _valid_url(url):
            continue
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(content)
        )
        tail = content[match.end() : end]
        snippet_lines = []
        for line in tail.splitlines():
            line = _clean_markdown(line, 500)
            if not line:
                continue
            if re.fullmatch(r"[\w.-]+\.[a-z]{2,}(?:/\S*)?", line, re.I):
                continue
            snippet_lines.append(line)
            if len(" ".join(snippet_lines)) >= 450:
                break
        results.append(
            {
                "title": title or url,
                "url": url,
                "snippet": _clean_text(" ".join(snippet_lines), 500),
            }
        )
        if len(results) >= limit:
            break
    return results


def _google_search(query, limit):
    """Optional legacy Google source; used only when other engines fail."""
    if not SEARCH_GOOGLE:
        return []
    try:
        from googlesearch import search
    except Exception:
        return []

    results = []
    try:
        found = search(
            query,
            num_results=limit,
            lang=SEARCH_REGION.split("-")[0],
            region=SEARCH_REGION.split("-")[-1],
            advanced=True,
            timeout=SEARCH_GOOGLE_TIMEOUT,
            safe="off" if SEARCH_SAFESEARCH == "off" else "active",
        )
        for item in found:
            url = str(getattr(item, "url", "") or "").strip()
            if not _valid_url(url):
                continue
            results.append(
                {
                    "title": _clean_text(
                        getattr(item, "title", "") or url, 240
                    ),
                    "url": url,
                    "snippet": _clean_text(
                        getattr(item, "description", ""), 500
                    ),
                }
            )
            if len(results) >= limit:
                break
    except Exception:
        return results
    return results


def _search_once(query, limit):
    results = []
    for provider in (_lite_search, _jina_search):
        try:
            found = provider(query, limit)
        except Exception:
            continue
        _merge_results(results, found, limit)
        ranked = _rank_results(query, results)
        if len(ranked) >= min(3, limit):
            return ranked
    ranked = _rank_results(query, results)
    if ranked:
        return ranked
    return []


def search_web(query, limit=None):
    query = " ".join(str(query or "").split()).strip()
    if not query or not SEARCH_ENABLED:
        return []
    limit = SEARCH_MAX_RESULTS if limit is None else int(limit)
    limit = max(1, min(10, limit))

    results = _search_once(query, limit)
    if results:
        return results[:limit]

    simplified = _simplify_query(query)
    if simplified and simplified.casefold() != query.casefold():
        results = _search_once(simplified, limit)
        if results:
            return results[:limit]

    # Last resort: the legacy Google helper.  It is slow and often blocked,
    # but it costs nothing when the normal engines already answered.
    try:
        results = _rank_results(query, _google_search(query, limit))
    except Exception:
        results = []
    return results[:limit]


def _html_text(html):
    text = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    text = re.sub(
        r"<(script|style|noscript|svg|iframe|canvas)\b[^>]*>.*?</\1>",
        " ",
        text,
        flags=re.S | re.I,
    )
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.I)
    text = re.sub(r"</(?:p|div|li|tr|h[1-6])>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return _clean_text(unescape(text), 200000)


def _response_text(response):
    encoding = response.encoding
    if not encoding or encoding.lower() in ("iso-8859-1", "latin-1"):
        encoding = response.apparent_encoding or "utf-8"
    try:
        return response.content.decode(encoding, errors="replace")
    except (LookupError, UnicodeError):
        return response.text


def _query_codes(query):
    lowered = str(query or "").casefold()
    codes = set(re.findall(r"\b[a-z]{3}\b", lowered))
    for word, code in (
        ("доллар", "usd"),
        ("доллара", "usd"),
        ("dollar", "usd"),
        ("евро", "eur"),
        ("euro", "eur"),
        ("юан", "cny"),
        ("фунт", "gbp"),
        ("pound", "gbp"),
        ("биткоин", "btc"),
        ("bitcoin", "btc"),
    ):
        if word in lowered:
            codes.add(code)
    return {code.upper() for code in codes}


def _page_excerpt(text, query, limit):
    stems = _query_stems(query)
    if not stems:
        return text[:limit]
    codes = _query_codes(query)

    positions = []
    lowered = text.casefold()
    for stem in stems:
        start = 0
        found_for_stem = 0
        while found_for_stem < 8:
            position = lowered.find(stem, start)
            if position < 0:
                break
            positions.append(max(0, position - 180))
            start = position + len(stem)
            found_for_stem += 1
    if not positions:
        return text[:limit]

    windows = []
    seen = set()
    for start in positions:
        key = start // 300
        if key in seen:
            continue
        seen.add(key)
        chunk = text[start : start + 900]
        folded = chunk.casefold()
        score = sum(1 for stem in stems if stem in folded)
        if any(re.search(rf"\b{code}\b", chunk, re.I) for code in codes):
            score += 5
        if re.search(r"\d", chunk):
            score += 2
        if any(symbol in chunk for symbol in ("₽", "$", "€", "%")):
            score += 1
        windows.append((score, start, chunk))
    selected = sorted(windows, key=lambda row: (-row[0], row[1]))[:3]
    return _clean_text(" … ".join(row[2] for row in selected), limit)


def _jina_page(url, query, limit):
    try:
        response = requests.get(
            "https://r.jina.ai/" + url,
            headers=_request_headers(SEARCH_REGION),
            timeout=max(SEARCH_PAGE_TIMEOUT, 12),
        )
    except Exception:
        return ""
    if response.status_code != 200:
        return ""
    content = response.text
    marker = content.find("Markdown Content:")
    if marker >= 0:
        content = content[marker + len("Markdown Content:") :]
    content = _clean_markdown(content, 200000)
    return _page_excerpt(content, query, limit)


def read_page(url, query="", limit=1600):
    """Read a result page and return a short excerpt relevant to the query."""
    if not _valid_url(url):
        return ""
    try:
        response = requests.get(
            url,
            headers=_request_headers(SEARCH_REGION),
            timeout=SEARCH_PAGE_TIMEOUT,
        )
    except Exception:
        return _jina_page(url, query, limit)
    if response.status_code != 200:
        return _jina_page(url, query, limit)
    content_type = response.headers.get("content-type", "").lower()
    if "html" not in content_type and "text" not in content_type:
        return ""
    text = _html_text(_response_text(response))
    if len(text) < 200:
        return _jina_page(url, query, limit)
    return _page_excerpt(text, query, limit)


def enrich_results(results, query, max_pages=3):
    """Add page excerpts to the top web results in parallel."""
    if not results:
        return results
    targets = results[:max_pages]
    try:
        with ThreadPoolExecutor(max_workers=len(targets)) as pool:
            futures = {
                pool.submit(read_page, item["url"], query): item
                for item in targets
            }
            for future, item in futures.items():
                try:
                    page = future.result()
                except Exception:
                    page = ""
                if page:
                    item["page"] = page
    except Exception:
        pass
    return results


def _youtube_initial_data(html):
    marker = html.find("ytInitialData")
    if marker < 0:
        return None
    start = html.find("{", marker)
    if start < 0:
        return None
    try:
        data, _end = json.JSONDecoder().raw_decode(html[start:])
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _youtube_video_renderers(node):
    if isinstance(node, dict):
        renderer = node.get("videoRenderer")
        if isinstance(renderer, dict):
            yield renderer
        for value in node.values():
            yield from _youtube_video_renderers(value)
    elif isinstance(node, list):
        for item in node:
            yield from _youtube_video_renderers(item)


def _youtube_video(video):
    video_id = str(video.get("videoId") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,}", video_id):
        return None

    title = " ".join(
        str(run.get("text") or "")
        for run in ((video.get("title") or {}).get("runs") or [])
    ).strip()
    if not title:
        return None

    details = []
    owner = (video.get("ownerText") or {}).get("runs") or []
    if owner and owner[0].get("text"):
        details.append(str(owner[0]["text"]))
    for key in ("lengthText", "viewCountText", "publishedTimeText"):
        value = (video.get(key) or {}).get("simpleText")
        if value:
            details.append(str(value))

    return {
        "title": _clean_text(title, 240),
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "snippet": _clean_text(" · ".join(details), 300),
    }


def search_youtube(query, limit=None):
    """Return existing YouTube videos for a query from YouTube's own search."""
    query = " ".join(str(query or "").split()).strip()
    if not query or not SEARCH_ENABLED or not SEARCH_YOUTUBE:
        return []
    limit = SEARCH_MAX_RESULTS if limit is None else int(limit)
    limit = max(1, min(10, limit))
    lang = SEARCH_REGION.split("-")[0] if "-" in SEARCH_REGION else "en"

    try:
        response = requests.get(
            "https://www.youtube.com/results",
            params={"search_query": query, "hl": lang},
            headers={
                "User-Agent": YOUTUBE_USER_AGENT,
                "Accept-Language": f"{lang},en;q=0.8",
            },
            timeout=SEARCH_YOUTUBE_TIMEOUT,
        )
        response.raise_for_status()
        data = _youtube_initial_data(response.text)
        results = []
        for renderer in _youtube_video_renderers(data):
            item = _youtube_video(renderer)
            if item is None:
                continue
            results.append(item)
            if len(results) >= limit:
                return results
        if results:
            return results
    except Exception:
        pass

    # If YouTube changes its page format, fall back to a normal web search.
    try:
        return search_web(f"site:youtube.com {query}", limit)
    except Exception:
        return []

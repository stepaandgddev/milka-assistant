import os
from urllib.parse import urlsplit


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


SEARCH_MAX_RESULTS = _int_env("SEARCH_MAX_RESULTS", 5, 1, 10)
SEARCH_REGION = os.environ.get("SEARCH_REGION", "ru-ru").strip() or "ru-ru"
SEARCH_SAFESEARCH = (
    os.environ.get("SEARCH_SAFESEARCH", "moderate").strip() or "moderate"
)
SEARCH_TIMEOUT = _int_env("SEARCH_TIMEOUT", 6, 3, 60)
SEARCH_GOOGLE = _bool_env("SEARCH_GOOGLE", True)
SEARCH_GOOGLE_TIMEOUT = _int_env("SEARCH_GOOGLE_TIMEOUT", 2, 2, 30)

_DDGS_CONFIGURED = False


def _dns_servers():
    raw = os.environ.get("SEARCH_DNS_SERVERS", "1.1.1.1,8.8.8.8")
    if raw.strip().lower() in {"", "system", "default"}:
        return None
    servers = [item.strip() for item in raw.split(",") if item.strip()]
    return servers or None


def _configure_ddgs():
    global _DDGS_CONFIGURED
    if _DDGS_CONFIGURED:
        return
    _DDGS_CONFIGURED = True
    servers = _dns_servers()
    if not servers:
        return
    try:
        import ddgs.base
        import ddgs.ddgs
        import primp
        from ddgs.http_client import HttpClient
    except Exception:
        return

    class DnsHttpClient(HttpClient):
        def __init__(self, proxy=None, timeout=10, *, verify=True):
            self.client = primp.Client(
                proxy=proxy,
                timeout=timeout,
                impersonate="random",
                impersonate_os="random",
                verify=verify if isinstance(verify, bool) else True,
                ca_cert_file=verify if isinstance(verify, str) else None,
                dns_resolver=servers,
            )

    ddgs.base.HttpClient = DnsHttpClient
    ddgs.ddgs.HttpClient = DnsHttpClient


def _valid_url(url):
    if not url or any(char.isspace() for char in url):
        return False
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    return (
        parsed.scheme.lower() in ("http", "https")
        and bool(parsed.netloc)
        and not parsed.username
        and not parsed.password
    )


def _clean_text(value, limit):
    return " ".join(str(value or "").split())[:limit]


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


def _google_search(query, limit):
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
            lang="ru",
            region="ru",
            advanced=True,
            timeout=SEARCH_GOOGLE_TIMEOUT,
            safe="active",
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


def _ddgs_search(query, limit):
    _configure_ddgs()
    try:
        from ddgs import DDGS
    except Exception as error:
        raise RuntimeError("The ddgs library is unavailable") from error

    results = []
    last_error = None
    for backend in ("html", "yahoo", "lite"):
        try:
            found = DDGS(timeout=SEARCH_TIMEOUT).text(
                query,
                region=SEARCH_REGION,
                safesearch=SEARCH_SAFESEARCH,
                max_results=limit,
                backend=backend,
            )
        except Exception as error:
            last_error = error
            continue

        known = {item["url"] for item in results}
        for item in found or []:
            url = str(item.get("href") or "").strip()
            if not _valid_url(url) or url in known:
                continue
            results.append(
                {
                    "title": _clean_text(item.get("title") or url, 240),
                    "url": url,
                    "snippet": _clean_text(item.get("body"), 500),
                }
            )
            known.add(url)
            if len(results) >= limit:
                return results

        if len(results) >= min(3, limit):
            return results

    if results:
        return results
    if last_error is not None:
        raise RuntimeError(str(last_error)) from last_error
    return []


def search_web(query, limit=None):
    query = " ".join(str(query or "").split()).strip()
    if not query:
        return []
    limit = SEARCH_MAX_RESULTS if limit is None else int(limit)
    limit = max(1, min(10, limit))

    results = []
    for provider in (_google_search, _ddgs_search):
        try:
            found = provider(query, limit)
        except Exception:
            if provider is _ddgs_search and not results:
                raise
            continue
        _merge_results(results, found, limit)
        if len(results) >= limit:
            break
    return results[:limit]

"""Read-only research connectors for genuinely open creative discovery.

License metadata is a *lead*, never ownership or permission to import media.
No downloading assets, scraping websites, automatic creative decisions or paid API.
Every network invocation requires the BODY's explicit 'network' access grant.
"""
from __future__ import annotations

import html
import ipaddress
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser


class CreativeResearchError(ValueError):
    """Rejected request, untrusted response or unavailable free provider."""


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _plain(value, max_chars=240):
    if not isinstance(value, str):
        return ""
    parser = _Text()
    parser.feed(value[:max_chars * 8])
    parser.close()
    return " ".join("".join(parser.parts).split())[:max_chars]


def _public_https(value):
    """Untrusted provider links are presented only; never fetched automatically."""
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        uri = urllib.parse.urlsplit(value)
        host = uri.hostname
        if uri.scheme != "https" or not host or uri.username or uri.password:
            return None
        if host.lower() == "localhost" or host.lower().endswith((".local", ".internal")):
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            if "." not in host:
                return None
        return value
    except ValueError:
        return None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_searxng_url(value):
    """Accept a host-configured literal loopback service and canonicalize its base."""
    if value is None:
        return None
    match = re.fullmatch(r"http://(127\.0\.0\.1|\[::1\]):([0-9]{1,5})/?", value,
                         flags=re.IGNORECASE) if isinstance(value, str) else None
    if match is None or not 1 <= int(match[2]) <= 65535:
        raise CreativeResearchError("SearXNG requires a literal loopback HTTP base with an explicit port")
    return f"http://{match[1]}:{int(match[2])}"


def _public_api_json(url):
    """Validate fixed public HTTPS providers before using the JSON transport."""
    hosts = {"api.openverse.org", "api.crossref.org", "commons.wikimedia.org",
             "api.artic.edu", "sfxmint.com"}
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in hosts:
        raise CreativeResearchError("Research request is not an approved free API")
    return _bounded_json_get(url)


def _bounded_json_get(url):
    """Fetch from a caller-validated URL without ambient proxies or redirects."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)
    request = urllib.request.Request(url, headers={
        "User-Agent": "ZX7-BODY-CreativeResearch/0.1 (https://github.com/ZX7-Labs/Zx7-creative-studio-; metadata-only)",
        "Accept": "application/json"})
    try:
        with opener.open(request, timeout=10) as response:
            if response.status != 200:
                raise CreativeResearchError("Research provider returned an unsuccessful status")
            raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise CreativeResearchError("Research metadata exceeds response budget")
            payload = json.loads(raw)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError,
            ValueError, RecursionError) as exc:
        if isinstance(exc, CreativeResearchError):
            raise
        raise CreativeResearchError("Research provider unavailable or returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise CreativeResearchError("Research provider did not return a JSON object")
    return payload


def _request_params(base, params):
    return base + "?" + urllib.parse.urlencode(params)


def _check(query, limit):
    if not isinstance(query, str) or not query.strip() or len(query.encode("utf-8")) > 240:
        raise CreativeResearchError("Research query must be 1–240 UTF-8 bytes")
    if type(limit) is not int or not 1 <= limit <= 12:
        raise CreativeResearchError("Research result limit must be between 1 and 12")
    return query.strip()


class CreativeResearch:
    """Creative asset, scholarly, and optional public web reference leads.

    An injected transport supports deterministic offline protocol tests.
    Production transport alone restricts network destinations and response size.
    """

    def __init__(self, fetch_json=None, *, searxng_url=None):
        self._fetch = fetch_json or _public_api_json
        self._searxng_url = validate_searxng_url(searxng_url)
        self._fetch_web = fetch_json or _bounded_json_get

    @property
    def web_search_enabled(self):
        return self._searxng_url is not None

    def web(self, *, query, limit=8):
        if not self.web_search_enabled:
            raise CreativeResearchError("Host has not configured a local SearXNG service")
        query = _check(query, limit)
        url = _request_params(self._searxng_url + "/search", {"q": query, "format": "json"})
        raw = self._fetch_web(url).get("results")
        if not isinstance(raw, list):
            raise CreativeResearchError("SearXNG reference metadata is malformed")
        results = []
        seen = set()
        for item in raw:
            if not isinstance(item, dict):
                continue
            page = _public_https(item.get("url"))
            title = _plain(item.get("title"))
            if not page or not title or page in seen:
                continue
            seen.add(page)
            results.append({"title": title, "snippet": _plain(item.get("content"), 360),
                            "source_page": page})
            if len(results) == limit:
                break
        return {
            "kind": "research_web_references", "provider": "searxng", "results": results,
            "result_content_untrusted": True, "source_pages_reviewed": False,
            "rights_verified": False, "import_authorized": False,
        }

    def assets(self, *, query, media, limit=8):
        query = _check(query, limit)
        if media not in ("image", "audio", "video"):
            raise CreativeResearchError("Supported asset types: image, audio, video")
        failures = []
        if media == "video":
            items, provider = self._commons_media(query, media, limit), "wikimedia_commons"
        else:
            try:
                items, provider = self._openverse(query, media, limit), "openverse"
            except CreativeResearchError:
                failures.append("openverse_unavailable_or_invalid")
                # These are independent, free, GET-only candidate libraries.
                # No paid generation or third-party asset download exists.
                alternatives = (("art_institute_chicago", self._artic_images)
                                if media == "image" else
                                ("sfxmint_free_library", self._sfxmint_audio))
                name, adapter = alternatives
                try:
                    items, provider = adapter(query, limit), name
                except CreativeResearchError:
                    failures.append(name + "_unavailable_or_invalid")
                    items, provider = self._commons_media(
                        query, media, limit), "wikimedia_commons"
        return {
            "kind": "research_asset_candidates",
            "provider": provider,
            "provider_failures": failures,
            "fallback_used": bool(failures),
            "media": media,
            "query": query,
            "results": items,
            "rights_verified": False,
            "import_authorized": False,
            "required_next_step": (
                "Inspect the original file page and current license, provenance, "
                "third-party privacy/trademark/personality/music rights and media bytes "
                "before any use. Search metadata is not legal clearance."),
        }

    def studies(self, *, query, limit=8):
        query = _check(query, limit)
        url = _request_params("https://api.crossref.org/works", {
            "query.bibliographic": query, "filter": "type:journal-article",
            "rows": limit, "select": "DOI,title,container-title,published,type"})
        payload = self._fetch(url)
        message = payload.get("message")
        raw = message.get("items") if isinstance(message, dict) else None
        if not isinstance(raw, list):
            raise CreativeResearchError("Crossref scholarly metadata is malformed")
        out = []
        for item in raw[:limit]:
            if not isinstance(item, dict) or item.get("type") != "journal-article":
                continue
            doi = item.get("DOI")
            if not isinstance(doi, str) or not re.fullmatch(
                    r"10\.\d{4,9}/[a-zA-Z0-9._;()/:+-]{1,200}", doi):
                continue
            title = item.get("title")
            title = _plain(title[0]) if isinstance(title, list) and title else ""
            if not title:
                continue
            publication = item.get("container-title")
            journal = _plain(publication[0], 140) if isinstance(
                publication, list) and publication else ""
            published = item.get("published")
            dates = published.get("date-parts") if isinstance(published, dict) else None
            year = (dates[0][0] if isinstance(dates, list) and dates and
                    isinstance(dates[0], list) and dates[0] and
                    type(dates[0][0]) is int and 1000 <= dates[0][0] <= 3000
                    else None)
            out.append({
                "kind": "scholarly_metadata", "title": title,
                "journal": journal, "year": year, "doi": doi,
                "source_page": "https://doi.org/" + urllib.parse.quote(doi, safe="/.:;+()-_"),
                "study_results_verified": False,
                "peer_review_independently_verified": False,
                "abstract_or_full_text_reviewed": False})
        return {
            "kind": "creative_audience_research",
            "query": query, "provider": "crossref", "results": out,
            "claim": ("Bibliographic search leads only. A paper title is not "
                      "evidence that an editing or storytelling style improves "
                      "retention, emotional response, or audience preference."),
            "required_next_step": (
                "Read eligible papers and methods; distinguish tested audiences, "
                "causality, genre and platform. Validate selected hypotheses "
                "with permissioned audience experiments and real outcomes.")}

    def _openverse(self, query, media, limit):
        url = _request_params("https://api.openverse.org/v1/" + (
            "images" if media == "image" else "audio") + "/", {
            "q": query, "license": "cc0", "mature": "false",
            "page_size": limit, "page": 1})
        raw = self._fetch(url).get("results")
        if not isinstance(raw, list):
            raise CreativeResearchError("Openverse asset metadata is malformed")
        items = []
        for asset in raw[:limit]:
            if not isinstance(asset, dict) or str(asset.get("license", "")).lower() != "cc0":
                continue
            page = _public_https(asset.get("foreign_landing_url"))
            if not page:
                continue
            items.append({
                "title": _plain(asset.get("title")) or "Untitled",
                "creator": _plain(asset.get("creator"), 120),
                "source_page": page, "declared_license": "CC0",
                "license_evidence_source": "openverse_index_metadata",
                "rights_status": "candidate_unverified",
                "media_type": media})
        return items

    def _artic_images(self, query, limit):
        """Museum artwork leads, only works explicitly marked public-domain."""
        url = _request_params("https://api.artic.edu/api/v1/artworks/search", {
            "q": query, "query[term][is_public_domain]": "true",
            "fields": "id,title,image_id,is_public_domain", "limit": limit})
        data = self._fetch(url).get("data")
        if not isinstance(data, list):
            raise CreativeResearchError("Museum public-domain metadata is malformed")
        items = []
        for record in data[:limit]:
            if not isinstance(record, dict) or record.get("is_public_domain") is not True:
                continue
            aid, image_id = record.get("id"), record.get("image_id")
            if (type(aid) is not int or aid <= 0 or
                    not isinstance(image_id, str) or
                    not re.fullmatch(r"[0-9a-fA-F-]{36}", image_id)):
                continue
            items.append({
                "title": _plain(record.get("title")) or "Untitled",
                "source_page": "https://www.artic.edu/artworks/" + str(aid),
                "declared_license": "CC0",
                "license_evidence_source": "artic_public_domain_flag_and_open_access_policy",
                "rights_status": "candidate_unverified", "media_type": "image"})
        return items

    def _sfxmint_audio(self, query, limit):
        """Search only the no-key CC0 library; never use paid sound generation."""
        url = _request_params("https://sfxmint.com/api/v1/search", {
            "q": query, "limit": limit, "response": "structured"})
        result = self._fetch(url)
        # The API can evolve between structured response families; reject any
        # unknown shape rather than pretending source results were verified.
        raw = next((result[key] for key in ("matches", "results", "sounds", "exact")
                    if isinstance(result.get(key), list)), None)
        if raw is None:
            raise CreativeResearchError("SFX public-library schema is unavailable")
        items = []
        for sound in raw[:limit]:
            if not isinstance(sound, dict):
                continue
            license_name = str(sound.get("license", "")).lower().replace(" ", "")
            if license_name not in ("cc0", "cc01.0", "cc0-1.0"):
                continue
            page = _public_https(sound.get("page_url"))
            if not page or urllib.parse.urlsplit(page).hostname != "sfxmint.com":
                continue
            items.append({
                "title": _plain(sound.get("title")) or "Untitled SFX",
                "source_page": page, "declared_license": "CC0",
                "license_evidence_source": "sfxmint_free_library_metadata",
                "rights_status": "candidate_unverified", "media_type": "audio"})
        return items

    def _commons_media(self, query, media, limit):
        filetype = {"image": "bitmap", "audio": "audio", "video": "video"}[media]
        url = _request_params("https://commons.wikimedia.org/w/api.php", {
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": "filetype:" + filetype + " " + query,
            "gsrnamespace": 6, "gsrlimit": limit,
            "prop": "imageinfo", "iiprop": "url|mime|extmetadata",
            "iiextmetadatafilter": "LicenseShortName|LicenseUrl"})
        result = self._fetch(url)
        query_data = result.get("query", {})
        pages = query_data.get("pages", {}) if isinstance(query_data, dict) else None
        if not isinstance(pages, dict):
            raise CreativeResearchError("Commons media metadata is malformed")
        items = []
        for record in pages.values():
            if not isinstance(record, dict):
                continue
            imageinfo = record.get("imageinfo")
            if not isinstance(imageinfo, list) or not imageinfo or not isinstance(imageinfo[0], dict):
                continue
            info = imageinfo[0]
            if not isinstance(info.get("mime"), str) or not info["mime"].startswith(media + "/"):
                continue
            meta = info.get("extmetadata")
            if not isinstance(meta, dict):
                continue
            label = meta.get("LicenseShortName")
            evidence = meta.get("LicenseUrl")
            if not isinstance(label, dict) or not isinstance(evidence, dict):
                continue
            license_name = _plain(label.get("value"), 60)
            license_url = _public_https(evidence.get("value"))
            if (license_name.upper() not in ("CC0", "CC0 1.0") or
                    license_url not in (
                        "https://creativecommons.org/publicdomain/zero/1.0/",
                        "https://creativecommons.org/publicdomain/zero/1.0/deed.en")):
                continue
            page = _public_https(info.get("descriptionurl"))
            if not page or urllib.parse.urlsplit(page).hostname != "commons.wikimedia.org":
                continue
            items.append({
                "title": _plain(record.get("title")) or "Untitled",
                "source_page": page, "declared_license": "CC0",
                "license_evidence_source": "commons_file_metadata",
                "rights_status": "candidate_unverified",
                "media_type": media})
        return items[:limit]

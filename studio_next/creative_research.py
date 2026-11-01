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


def _public_api_json(url):
    """Allowlisted HTTPS GET, no ambient proxy, redirect, or unbounded JSON."""
    hosts = {"api.openverse.org", "api.crossref.org", "commons.wikimedia.org"}
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in hosts:
        raise CreativeResearchError("Research request is not an approved free API")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)
    request = urllib.request.Request(url, headers={
        "User-Agent": "ZX7-BODY-CreativeResearch/0.1 (source-respecting; no scraping)",
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
            ValueError) as exc:
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
    """Public-domain asset leads + scholarly metadata; no rights assertions.

    An injected transport supports deterministic offline protocol tests.
    Production transport alone restricts network destinations and response size.
    """

    def __init__(self, fetch_json=None):
        self._fetch = fetch_json or _public_api_json

    def assets(self, *, query, media, limit=8):
        query = _check(query, limit)
        if media not in ("image", "audio", "video"):
            raise CreativeResearchError("Supported asset types: image, audio, video")
        if media == "video":
            items, provider = self._commons_video(query, limit), "wikimedia_commons"
        else:
            items, provider = self._openverse(query, media, limit), "openverse"
        return {
            "kind": "research_asset_candidates",
            "provider": provider,
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
        raw = (payload.get("message") or {}).get("items")
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
            dates = (item.get("published") or {}).get("date-parts") or []
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

    def _commons_video(self, query, limit):
        url = _request_params("https://commons.wikimedia.org/w/api.php", {
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": "filetype:video " + query,
            "gsrnamespace": 6, "gsrlimit": limit,
            "prop": "imageinfo", "iiprop": "url|mime|extmetadata",
            "iiextmetadatafilter": "LicenseShortName|LicenseUrl"})
        pages = (self._fetch(url).get("query") or {}).get("pages", {})
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
            if not isinstance(info.get("mime"), str) or not info["mime"].startswith("video/"):
                continue
            meta = info.get("extmetadata")
            if not isinstance(meta, dict):
                continue
            license_name = _plain((meta.get("LicenseShortName") or {}).get("value"), 60)
            license_url = _public_https((meta.get("LicenseUrl") or {}).get("value"))
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
                "media_type": "video"})
        return items[:limit]

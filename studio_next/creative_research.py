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
import socket
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from http.client import HTTPException
from threading import Lock


REFERENCE_LANGUAGE_PATTERN = r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8}){0,3}"
_WIKIPEDIA_HOST = re.compile(r"([a-z]{2,8}(?:-[a-z0-9]{1,8}){0,3})\.wikipedia\.org")
_WIKIMEDIA_SITE_MATRIX = "https://meta.wikimedia.org/w/api.php"


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
        # URL parsers and browsers accept loopback spellings that
        # ipaddress.ip_address() alone does not parse: 127.1, octal/hex
        # IPv4, and a trailing DNS root dot. These are references only,
        # but must never be advertised to a creative model as public links.
        if "%" in host:
            return None
        hostname = host.rstrip(".").encode("idna").decode("ascii").lower()
        if (not hostname or hostname == "localhost" or
                hostname.endswith((".local", ".internal"))):
            return None
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            try:
                # inet_aton normalizes legacy numeric IPv4 forms without
                # resolving DNS or contacting an attacker-controlled host.
                address = ipaddress.IPv4Address(socket.inet_aton(hostname))
            except (OSError, ValueError):
                if "." not in hostname or ".." in hostname:
                    return None
                address = None
        if address is not None and not address.is_global:
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
    host = parsed.hostname
    wikimedia_api = parsed.path == "/w/api.php" and (
        host == "meta.wikimedia.org" or bool(_WIKIPEDIA_HOST.fullmatch(host or "")))
    if (parsed.scheme != "https" or parsed.netloc != host or parsed.fragment or
            (host not in hosts and not wikimedia_api)):
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
            ValueError, HTTPException, RecursionError) as exc:
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
    """Creative asset, scholarly, and public reference leads.

    An injected transport supports deterministic offline protocol tests.
    Production transport alone restricts network destinations and response size.
    """

    def __init__(self, fetch_json=None, *, searxng_url=None):
        self._fetch = fetch_json or _public_api_json
        self._searxng_url = validate_searxng_url(searxng_url)
        self._fetch_web = fetch_json or _bounded_json_get
        self._site_catalog = None
        self._site_lock = Lock()

    def web(self, *, query, limit=8, language=None):
        query = _check(query, limit)
        if language is not None:
            if not isinstance(language, str) or not re.fullmatch(REFERENCE_LANGUAGE_PATTERN, language):
                raise CreativeResearchError("Reference search requires a valid language tag")
        if self._searxng_url is None:
            provider = "wikipedia"
            language, base = self._resolve_wikipedia_site((language or "en").lower())
            results = self._wikipedia_references(query, limit, base)
        else:
            provider = "searxng"
            results = self._searxng_references(query, limit, language)
        return {
            "kind": "research_web_references", "provider": provider, "results": results,
            "language": language,
            "result_content_untrusted": True, "source_pages_reviewed": False,
            "rights_verified": False, "import_authorized": False,
        }

    def _wikipedia_sites(self):
        # Cache only the public site registry. It contains no research query.
        with self._site_lock:
            if self._site_catalog is not None:
                return self._site_catalog
            url = _request_params(_WIKIMEDIA_SITE_MATRIX, {
                "action": "sitematrix", "format": "json", "smtype": "language",
                "smlangprop": "code|site", "smsiteprop": "code|url", "smlimit": "max",
            })
            payload = self._fetch(url)
            matrix = payload.get("sitematrix")
            if not isinstance(matrix, dict) or "continue" in payload:
                raise CreativeResearchError("Wikimedia site registry is unavailable or incomplete")
            languages = {}
            aliases = {}
            for row in matrix.values():
                if not isinstance(row, dict):
                    continue
                code, sites = row.get("code"), row.get("site")
                if not isinstance(code, str) or not re.fullmatch(REFERENCE_LANGUAGE_PATTERN, code):
                    continue
                if not isinstance(sites, list):
                    continue
                for site in sites:
                    if (not isinstance(site, dict) or site.get("code") != "wiki" or
                            any(flag in site for flag in ("closed", "private", "fishbowl", "nonglobal"))):
                        continue
                    base = site.get("url")
                    if not isinstance(base, str) or not base.startswith("https://"):
                        continue
                    host = _WIKIPEDIA_HOST.fullmatch(base.removeprefix("https://"))
                    if host is None:
                        continue
                    entry = (code.lower(), base)
                    languages[entry[0]] = entry
                    aliases[host[1]] = entry
            if not languages:
                raise CreativeResearchError("Wikimedia site registry contains no searchable Wikipedia sites")
            self._site_catalog = aliases | languages
            return self._site_catalog

    def _resolve_wikipedia_site(self, language):
        if language == "all":
            raise CreativeResearchError("Choose a Wikipedia language, or use all with SearXNG")
        sites = self._wikipedia_sites()
        while language:
            if language in sites:
                return sites[language]
            language = language.rpartition("-")[0]
        raise CreativeResearchError("Wikipedia has no public search site for the requested language")

    def _wikipedia_references(self, query, limit, base):
        url = _request_params(base + "/w/api.php", {
            "action": "query", "list": "search", "format": "json", "srnamespace": 0,
            "srprop": "snippet", "srsearch": query, "srlimit": limit,
        })
        data = self._fetch(url).get("query")
        raw = data.get("search") if isinstance(data, dict) else None
        if not isinstance(raw, list):
            raise CreativeResearchError("Wikipedia reference metadata is malformed")
        results = []
        seen = set()
        for item in raw:
            if not isinstance(item, dict):
                continue
            page_id = item.get("pageid")
            title = _plain(item.get("title"))
            if type(page_id) is not int or not 0 < page_id < 2**63 or not title or page_id in seen:
                continue
            seen.add(page_id)
            results.append({"title": title, "snippet": _plain(item.get("snippet"), 360),
                            "source_page": f"{base}/?curid={page_id}"})
            if len(results) == limit:
                break
        return results

    def _searxng_references(self, query, limit, language):
        params = {"q": query, "format": "json"}
        if language is not None:
            params["language"] = language
        url = _request_params(self._searxng_url + "/search", params)
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
        return results

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

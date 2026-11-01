"""Creative-domain federated research over independently verifiable free sources.

A research source is host-installed code, not a prompt-defined URL or dynamic
plugin. A small model can ask arbitrary creative questions across media,
cinematography, sound, narrative, graphic design, animation and other art.
This returns *research evidence*; it never certifies creative quality,
licenses, or initiates a paid API/asset download.

Provider failures are isolated. The bounded API transport has a finite network
timeout (otherwise one failed website can hang a whole studio indefinitely);
parallel queries and partial results prevent one timeout from stopping research.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
from threading import Lock
import re
import time
import urllib.parse

from .creative_research import (
    CreativeResearch, CreativeResearchError, _plain, _public_https, _check,
    _request_params,
)
from .creative_research_3d import poly_haven_assets, ambientcg_assets
from .creative_research_sources import nasa_video_references, europe_pmc_abstracts


@dataclass(frozen=True)
class CreativeSource:
    """Immutable host-installed adapter descriptor, not a remote plugin manifest."""
    id: str
    domain: str
    media: frozenset[str]
    function: object
    def __post_init__(self):
        if (not re.fullmatch(r"[a-z][a-z0-9_]{1,39}", self.id)
                or self.domain not in ("assets", "knowledge", "scholarship")
                or not isinstance(self.media, frozenset)
                or not self.media.issubset({"image", "video", "audio", "3d", "all"})
                or not self.media or not callable(self.function)):
            raise CreativeResearchError("Invalid host-owned creative source contract")


class CreativeResearchHub:
    """Host-controlled flexible source registry, concurrent execution and cache.

    New creative domains are added by trusted adapters, not by changing the
    existing AI model interface or teaching it a new giant markdown catalog.
    A single request fans out in parallel; slow endpoints degrade individually.
    """

    def __init__(self, sources, *, cache_seconds=180, clock=None, max_workers=8):
        if (not isinstance(sources, (tuple, list)) or not sources or len(sources) > 48
                or any(not isinstance(item, CreativeSource) for item in sources)
                or len({item.id for item in sources}) != len(sources)):
            raise CreativeResearchError("Real installed unique creative source adapters required")
        if (type(max_workers) is not int or not 1 <= max_workers <= 16
                or type(cache_seconds) is not int or not 0 <= cache_seconds <= 86400):
            raise CreativeResearchError("Bounded free research budget required")
        self.sources = tuple(sources)
        self.cache_seconds = cache_seconds
        self.max_workers = max_workers
        self._clock = clock or time.monotonic
        self._cache = {}
        self._lock = Lock()

    @classmethod
    def installed(cls, fetch_json=None):
        base = CreativeResearch(fetch_json)
        return cls([
            CreativeSource("openverse_image", "assets", frozenset({"image"}),
                           lambda q, n: base._openverse(q, "image", n)),
            CreativeSource("openverse_audio", "assets", frozenset({"audio"}),
                           lambda q, n: base._openverse(q, "audio", n)),
            CreativeSource("art_institute", "assets", frozenset({"image"}),
                           base._artic_images),
            CreativeSource("cleveland_museum", "assets", frozenset({"image"}),
                           lambda q, n: _cleveland_images(base._fetch, q, n)),
            CreativeSource("commons_image", "assets", frozenset({"image"}),
                           lambda q, n: base._commons_media(q, "image", n)),
            CreativeSource("commons_audio", "assets", frozenset({"audio"}),
                           lambda q, n: base._commons_media(q, "audio", n)),
            CreativeSource("commons_video", "assets", frozenset({"video"}),
                           lambda q, n: base._commons_media(q, "video", n)),
            CreativeSource("sfxmint_audio", "assets", frozenset({"audio"}),
                           base._sfxmint_audio),
            CreativeSource("polyhaven_models", "assets", frozenset({"3d"}),
                           lambda q, n: poly_haven_assets(base._fetch, q, n, type_name="models")),
            CreativeSource("polyhaven_textures", "assets", frozenset({"image"}),
                           lambda q, n: poly_haven_assets(base._fetch, q, n, type_name="textures")),
            CreativeSource("polyhaven_hdris", "assets", frozenset({"image"}),
                           lambda q, n: poly_haven_assets(base._fetch, q, n, type_name="hdris")),
            CreativeSource("ambientcg_models", "assets", frozenset({"3d"}),
                           lambda q, n: ambientcg_assets(base._fetch, q, n, type_name="3d-model")),
            CreativeSource("ambientcg_materials", "assets", frozenset({"image"}),
                           lambda q, n: ambientcg_assets(base._fetch, q, n, type_name="material")),
            CreativeSource("ambientcg_hdris", "assets", frozenset({"image"}),
                           lambda q, n: ambientcg_assets(base._fetch, q, n, type_name="hdri")),
            CreativeSource("crossref_studies", "scholarship", frozenset({"all"}),
                           lambda q, n: base.studies(query=q, limit=n)["results"]),
            CreativeSource("wikipedia_reference", "knowledge", frozenset({"all"}),
                           lambda q, n: _wikipedia_reference(base._fetch, q, n)),
            CreativeSource("nasa_archival_video_reference", "knowledge",
                           frozenset({"video"}),
                           lambda q, n: nasa_video_references(base._fetch, q, n)),
            CreativeSource("europepmc_abstracts", "scholarship", frozenset({"all"}),
                           lambda q, n: europe_pmc_abstracts(base._fetch, q, n)),
        ])

    def discover(self):
        return [{"id": item.id, "domain": item.domain,
                 "media": sorted(item.media), "free_api_key_required": False,
                 "paid_inference_required": False,
                 "rights_attested_by_this_tool": False}
                for item in self.sources]

    def research(self, *, query, domain="all", media="all", limit=12):
        query = _check(query, limit)
        if domain not in ("all", "assets", "knowledge", "scholarship"):
            raise CreativeResearchError("Creative research domain is not registered")
        if media not in ("all", "image", "audio", "video", "3d"):
            raise CreativeResearchError("Unknown creative media dimension")
        sources = [item for item in self.sources
                   if (domain == "all" or item.domain == domain)
                   and (media == "all" or media in item.media or "all" in item.media)]
        if not sources:
            return {"kind": "creative_research_evidence", "query": query,
                    "domain": domain, "media": media, "results": [],
                    "source_outcomes": [], "all_sources_exhausted": True,
                    "rights_verified": False, "creative_quality_verified": False,
                    "claim": "No matching installed source; no conclusion about creative work"}
        cache_key = (query, domain, media, limit)
        with self._lock:
            found = self._cache.get(cache_key)
            if found is not None and found[0] > self._clock():
                import copy
                return copy.deepcopy(found[1])

        # Each underlying official transport is independently bounded at
        # 10 seconds. Most calls finish quickly. The whole request is bounded
        # even if a provider itself violates its transport's deadline.
        pool = ThreadPoolExecutor(max_workers=min(self.max_workers, len(sources)))
        futures = {pool.submit(item.function, query, limit): item for item in sources}
        done, unfinished = wait(futures, timeout=13)
        results, outcomes, seen = [], [], set()
        try:
            for future, item in futures.items():
                if future not in done:
                    outcomes.append({"source": item.id, "state": "timed_out",
                                     "candidate_count": 0})
                    future.cancel()
                    continue
                try:
                    records = future.result()
                    if not isinstance(records, list):
                        raise CreativeResearchError("Provider returned malformed list")
                    count = 0
                    for record in records[:limit]:
                        if not isinstance(record, dict):
                            continue
                        uri = record.get("source_page")
                        if not _public_https(uri):
                            continue
                        if item.domain == "assets":
                            if (record.get("declared_license") != "CC0" or
                                    record.get("rights_status") != "candidate_unverified"):
                                continue
                        identity = (item.domain, uri)
                        if identity in seen:
                            continue
                        seen.add(identity)
                        result = {"source": item.id, "domain": item.domain,
                                  **{k: v for k, v in record.items() if
                                     k in ("title", "source_page", "declared_license",
                                           "rights_status", "media_type", "creator",
                                           "journal", "year", "doi",
                                           "study_results_verified",
                                           "peer_review_independently_verified",
                                           "abstract_or_full_text_reviewed",
                                           "license_evidence_source", "provider_credit", "asset_kind",
                                           "reference_type", "source_reuse_not_authorized",
                                           "model_has_not_watched_video",
                                           "abstract_excerpt", "abstract_is_unreviewed_source_text",
                                           "research_not_a_media_reuse_license")}}
                        results.append(result)
                        count += 1
                    outcomes.append({"source": item.id, "state": "responded",
                                     "candidate_count": count})
                except Exception:
                    # A provider's failure is source-scoped, never silently
                    # equated with zero good content or a successful request.
                    outcomes.append({"source": item.id, "state": "failed",
                                     "candidate_count": 0})
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

        # Round-robin source interleaving prevents one large provider
        # dominating discovery; no fake ranking of human taste or artistry.
        grouped = {source.id: [] for source in sources}
        for record in results:
            grouped[record["source"]].append(record)
        mixed = []
        for i in range(limit):
            for source in sources:
                if i < len(grouped[source.id]) and len(mixed) < limit:
                    mixed.append(grouped[source.id][i])
        payload = {
            "kind": "creative_research_evidence", "query": query,
            "domain": domain, "media": media, "results": mixed,
            "source_outcomes": outcomes,
            "all_sources_exhausted": not mixed,
            "rights_verified": False, "import_authorized": False,
            "creative_quality_verified": False,
            "human_preference_inferred": False,
            "research_is_creative_domain_scoped": True,
            "claim": ("Candidate leads are not copyright clearance or audience findings. "
                      "References can inform creativity but should not be copied; "
                      "video links are not proof that a model watched the video."),
        }
        # Cache only fully successful provider runs. Transient errors and
        # incomplete responses must get a fresh chance on the next query.
        if self.cache_seconds and all(x["state"] == "responded" for x in outcomes):
            import copy
            with self._lock:
                if len(self._cache) >= 256:
                    self._cache.clear()
                self._cache[cache_key] = (self._clock() + self.cache_seconds,
                                          copy.deepcopy(payload))
        return payload


def _cleveland_images(fetch, query, limit):
    """Official no-key CMA API; explicit per-artwork CC0, never metadata-only."""
    url = _request_params("https://openaccess-api.clevelandart.org/api/artworks/", {
        "q": query, "cc0": "", "has_image": 1, "limit": limit,
        "fields": "id,title,accession_number,share_license_status,images"})
    data = fetch(url).get("data")
    if not isinstance(data, list):
        raise CreativeResearchError("CMA metadata malformed")
    output = []
    for record in data[:limit]:
        if not isinstance(record, dict) or str(
                record.get("share_license_status", "")).upper() != "CC0":
            continue
        ident = record.get("accession_number")
        pics = record.get("images")
        if (not isinstance(ident, str) or
                not re.fullmatch(r"[A-Za-z0-9.]{1,32}", ident) or
                not isinstance(pics, dict) or not isinstance(pics.get("web"), dict)
                or not _public_https(pics["web"].get("url"))):
            continue
        output.append({"title": _plain(record.get("title")) or "Untitled",
                       "source_page": "https://www.clevelandart.org/art/" + ident,
                       "declared_license": "CC0",
                       "license_evidence_source": "cleveland_museum_share_license_status",
                       "rights_status": "candidate_unverified", "media_type": "image"})
    return output


def _wikipedia_reference(fetch, query, limit):
    """Research *facts and techniques* only; never treat article text as CC0."""
    url = _request_params("https://en.wikipedia.org/w/api.php", {
        "action": "query", "format": "json",
        "list": "search", "srsearch": query, "srnamespace": 0,
        "srlimit": limit, "srprop": ""})
    message = fetch(url).get("query")
    records = message.get("search") if isinstance(message, dict) else None
    if not isinstance(records, list):
        raise CreativeResearchError("Wiki knowledge response malformed")
    result = []
    for item in records[:limit]:
        if not isinstance(item, dict):
            continue
        title = _plain(item.get("title"), 180)
        if not title:
            continue
        result.append({"title": title, "source_page": (
            "https://en.wikipedia.org/wiki/" +
            urllib.parse.quote(item["title"].replace(" ", "_"), safe="()_-")),
            "research_not_a_reuse_license": True})
    return result

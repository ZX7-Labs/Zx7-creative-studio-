"""Research contract tests with fixtures and a local HTTP transport check."""
import json
import importlib.util
import tempfile
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from studio_next.creative_research import (
    CreativeResearch, CreativeResearchError, _public_https, _public_api_json,
    validate_searxng_url)
from studio_next.body_integration import body_catalog


class FakePublicAPIs:
    def __init__(self):
        self.calls = []
        self.response = {}
        self.site_matrix = {}

    def __call__(self, url):
        self.calls.append(url)
        if urlsplit(url).hostname == "meta.wikimedia.org":
            return self.site_matrix
        return self.response


class CreativeResearchTests(unittest.TestCase):

    def test_archived_public_sources_are_reachable_without_asset_import(self):
        calls = []
        def fetch(url):
            calls.append(url)
            host = urlsplit(url).hostname
            if host == "openaccess-api.clevelandart.org":
                return {"data": [
                    {"accession_number": "1923.1", "title": "Light",
                     "share_license_status": "CC0",
                     "images": {"web": {"url": "https://images.example.org/a.jpg"}}},
                    {"accession_number": "1923.2", "title": "Restricted",
                     "share_license_status": "Copyrighted",
                     "images": {"web": {"url": "https://images.example.org/b.jpg"}}},
                    {"accession_number": "1923.3", "share_license_status": "CC0",
                     "images": {"web": {"url": "https://127.0.0.1/private"}}},
                    {"accession_number": "../bad", "share_license_status": "CC0",
                     "images": {"web": {"url": "https://images.example.org/c.jpg"}}},
                ]}
            if host == "images-api.nasa.gov":
                return {"collection": {"items": [
                    {"data": [{"nasa_id": "Apollo_16", "title": "Moon camera",
                               "media_type": "video"}]},
                    {"data": [{"nasa_id": "../private", "media_type": "video"}]},
                    {"data": [{"nasa_id": "Photo", "media_type": "image"}]},
                ]}}
            if host == "www.ebi.ac.uk":
                return {"resultList": {"result": [
                    {"id": "123456", "source": "MED", "title": "Visual attention",
                     "pubYear": "2024", "abstractText": "<b>Methods</b> " + "A"*2000},
                    {"id": "..", "source": "MED", "title": "Malformed ID"},
                    {"id": "bad/path", "source": "MED", "title": "Malformed ID"},
                    {"id": "123", "source": "UNKNOWN", "title": "Unknown source"},
                ]}}
            self.fail("Unexpected provider or follow-up fetch: " + url)
        research = CreativeResearch(fetch)
        art = research.assets(query="public light", media="image", limit=5,
                              provider="cleveland_museum")
        self.assertEqual(art["provider"], "cleveland_museum")
        self.assertEqual(len(art["results"]), 1)
        self.assertEqual(art["results"][0]["source_page"],
                         "https://www.clevelandart.org/art/1923.1")
        self.assertEqual(art["results"][0]["declared_license"], "CC0")
        self.assertEqual(art["results"][0]["rights_status"], "candidate_unverified")
        self.assertFalse(art["rights_verified"])
        self.assertFalse(art["import_authorized"])
        video = research.web(query="public moon footage", limit=5,
                             provider="nasa_archive")
        self.assertEqual(video["provider"], "nasa_archive")
        self.assertEqual(len(video["results"]), 1)
        self.assertTrue(video["results"][0]["source_reuse_not_authorized"])
        self.assertTrue(video["results"][0]["model_has_not_watched_video"])
        self.assertNotIn("declared_license", video["results"][0])
        self.assertTrue(video["result_content_untrusted"])
        self.assertFalse(video["import_authorized"])
        papers = research.studies(query="public visual attention", limit=5,
                                  provider="europe_pmc")
        self.assertEqual(papers["provider"], "europe_pmc")
        self.assertEqual(len(papers["results"]), 1)
        paper = papers["results"][0]
        self.assertTrue(paper["abstract_is_unreviewed_source_text"])
        self.assertFalse(paper["study_results_verified"])
        self.assertFalse(paper["peer_review_independently_verified"])
        self.assertLessEqual(len(paper["abstract_excerpt"]), 320)
        self.assertTrue(paper["abstract_excerpt"].startswith("Methods"))
        self.assertEqual([(urlsplit(url).hostname, urlsplit(url).path)
                          for url in calls], [
            ("openaccess-api.clevelandart.org", "/api/artworks/"),
            ("images-api.nasa.gov", "/search"),
            ("www.ebi.ac.uk", "/europepmc/webservices/rest/search"),
        ])
        self.assertEqual(parse_qs(urlsplit(calls[0]).query,
                                  keep_blank_values=True)["cc0"], [""])

    def test_nasa_live_ids_with_spaces_are_encoded_as_safe_reference_paths(self):
        provider = FakePublicAPIs()
        valid = ("NDTV000908_Apollo_Digest_Series_Spacecraft for Apollo",
                 "Official Celebration of Apollo 17 50th Anniversary",
                 "al worden_fixed")
        invalid = ("../private", "a/b", "a%2fb", "a?b", "a#b", "a\\b",
                   " a", "a ", "a\nb", "a" * 121)
        provider.response = {"collection": {"items": [
            {"data": [{"nasa_id": ident, "media_type": "video"}]}
            for ident in valid + invalid]}}
        # Provider limits apply before filtering, so test malformed IDs separately.
        research = CreativeResearch(provider)
        result = research.web(query="Apollo", limit=3, provider="nasa_archive")
        self.assertEqual([r["source_page"] for r in result["results"]], [
            "https://images.nasa.gov/details/NDTV000908_Apollo_Digest_Series_Spacecraft%20for%20Apollo",
            "https://images.nasa.gov/details/Official%20Celebration%20of%20Apollo%2017%2050th%20Anniversary",
            "https://images.nasa.gov/details/al%20worden_fixed"])
        self.assertTrue(all(r["source_reuse_not_authorized"] and
                            r["model_has_not_watched_video"] for r in result["results"]))
        self.assertFalse(result["import_authorized"])
        provider.response["collection"]["items"] = provider.response["collection"]["items"][3:]
        self.assertEqual(research.web(query="Apollo", limit=12,
                                     provider="nasa_archive")["results"], [])
        self.assertEqual(len(provider.calls), 2)

    def test_explicit_source_selection_rejects_unavailable_or_wrong_media_before_network(self):
        provider = FakePublicAPIs()
        research = CreativeResearch(provider)
        for call in (
            lambda: research.assets(query="light", media="audio", provider="cleveland_museum"),
            lambda: research.assets(query="light", media="image", provider="https://evil.test"),
            lambda: research.assets(query="light", media="image", provider=[]),
            lambda: research.studies(query="light", provider="unknown"),
            lambda: research.web(query="light", provider="searxng"),
            lambda: research.web(query="light", provider="nasa_archive", language="hi"),
            lambda: research.web(query="light", provider="https://evil.test"),
        ):
            with self.assertRaises(CreativeResearchError):
                call()
        self.assertEqual(provider.calls, [])

    def test_named_asset_provider_does_not_silently_fallback(self):
        calls = []
        def provider(url):
            calls.append(url)
            if urlsplit(url).hostname == "api.polyhaven.com":
                raise CreativeResearchError("Unavailable")
            return {"assets": [{"id": "Camera001", "title": "Camera"}]}
        research = CreativeResearch(provider)
        with self.assertRaises(CreativeResearchError):
            research.assets(query="camera", media="3d", provider="poly_haven")
        self.assertEqual([urlsplit(url).hostname for url in calls],
                         ["api.polyhaven.com"])
        result = research.assets(query="camera", media="3d", provider="ambientcg")
        self.assertEqual(result["provider"], "ambientcg")
        self.assertFalse(result["fallback_used"])
        self.assertFalse(result["import_authorized"])
        self.assertEqual([urlsplit(url).hostname for url in calls],
                         ["api.polyhaven.com", "ambientcg.com"])

    def test_europe_pmc_timeout_get_has_one_bounded_same_url_retry(self):
        from unittest.mock import MagicMock
        from urllib.error import HTTPError, URLError
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=attention"
        response = MagicMock()
        response.status = 200
        response.read.return_value = b'{"resultList":{"result":[]}}'
        response.__enter__.return_value = response
        for initial in (TimeoutError("slow public API"), URLError(TimeoutError("slow"))):
            with self.subTest(initial=type(initial).__name__):
                opener = MagicMock()
                opener.open.side_effect = [initial, response]
                with patch("studio_next.creative_research.urllib.request.build_opener",
                           return_value=opener):
                    self.assertEqual(_public_api_json(url), {"resultList": {"result": []}})
                self.assertEqual([call.args[0].full_url for call in opener.open.call_args_list],
                                 [url, url])
                self.assertEqual([call.kwargs["timeout"] for call in opener.open.call_args_list],
                                 [10, 10])
        # A persistently unavailable endpoint still fails closed after two attempts.
        opener = MagicMock()
        opener.open.side_effect = TimeoutError("still unavailable")
        with patch("studio_next.creative_research.urllib.request.build_opener", return_value=opener):
            with self.assertRaises(CreativeResearchError):
                _public_api_json(url)
        self.assertEqual(opener.open.call_count, 2)
        # HTTP denial/redirect or invalid payload are not retryable transport timeouts.
        for invalid in (HTTPError(url, 403, "denied", {}, None),
                        HTTPError(url, 302, "redirect", {}, None), ValueError("invalid JSON")):
            opener = MagicMock()
            opener.open.side_effect = invalid
            with patch("studio_next.creative_research.urllib.request.build_opener", return_value=opener):
                with self.assertRaises(CreativeResearchError):
                    _public_api_json(url)
            self.assertEqual(opener.open.call_count, 1)
        opener = MagicMock()
        opener.open.side_effect = TimeoutError("unrelated endpoint")
        with patch("studio_next.creative_research.urllib.request.build_opener", return_value=opener):
            with self.assertRaises(CreativeResearchError):
                _public_api_json("https://images-api.nasa.gov/search?q=moon")
        self.assertEqual(opener.open.call_count, 1)


    def test_public_transport_failure_classifies_stage_without_leaking_query_or_response(self):
        from unittest.mock import MagicMock
        from urllib.error import HTTPError, URLError
        import socket
        from studio_next.creative_research import _bounded_json_get
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=PRIVATE_QUERY"
        for stage, failure, expected in (
                ("open", URLError(TimeoutError("PRIVATE_BODY")), "connect_or_headers:timeout"),
                ("open", URLError(socket.gaierror(-2, "PRIVATE_BODY")), "connect_or_headers:dns"),
                ("open", HTTPError(url, 403, "PRIVATE_BODY", {}, None), "connect_or_headers:http_status"),
                ("read", TimeoutError("PRIVATE_BODY"), "body_read:timeout"),
                ("json", b'{"PRIVATE_BODY":', "json_decode:invalid_json")):
            with self.subTest(stage=stage, expected=expected):
                opener = MagicMock()
                response = MagicMock()
                response.status = 200
                response.__enter__.return_value = response
                opener.open.return_value = response
                if stage == "open":
                    opener.open.side_effect = failure
                elif stage == "read":
                    response.read.side_effect = failure
                else:
                    response.read.return_value = failure
                with patch("studio_next.creative_research.urllib.request.build_opener",
                           return_value=opener):
                    with self.assertRaisesRegex(CreativeResearchError, expected) as caught:
                        _bounded_json_get(url)
                self.assertNotIn("PRIVATE", str(caught.exception))
                self.assertIsNotNone(caught.exception.__cause__)
                self.assertEqual(opener.open.call_count, 1)


    def test_real_truncated_http_body_cannot_return_valid_json_prefix(self):
        from studio_next.creative_research import _bounded_json_get
        calls = []

        class LocalMetadata(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                calls.append(self.path)
                body = b'{"results":[]}'
                self.send_response(200)
                if self.path == "/truncated":
                    self.send_header("Content-Length", str(len(body) + 100))
                elif self.path == "/complete":
                    self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        with ThreadingHTTPServer(("127.0.0.1", 0), LocalMetadata) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                with self.assertRaisesRegex(CreativeResearchError, "body_read:http_protocol"):
                    _bounded_json_get(base + "/truncated")
                self.assertEqual(_bounded_json_get(base + "/complete"), {"results": []})
                self.assertEqual(_bounded_json_get(base + "/unknown-length"), {"results": []})
            finally:
                server.shutdown()
                thread.join()
        self.assertEqual(calls, ["/truncated", "/complete", "/unknown-length"])

    def test_restored_research_providers_allow_only_exact_metadata_paths(self):
        allowed = (
            "https://openaccess-api.clevelandart.org/api/artworks/?q=light",
            "https://images-api.nasa.gov/search?q=moon",
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=attention",
        )
        with patch("studio_next.creative_research._bounded_json_get",
                   return_value={}) as fetch:
            for url in allowed:
                self.assertEqual(_public_api_json(url), {})
                for unsafe in (url.replace("https://", "http://"),
                               url.replace("https://", "https://user@"),
                               url.replace(urlsplit(url).hostname,
                                           urlsplit(url).hostname + ".evil.test"),
                               url.replace(urlsplit(url).hostname,
                                           urlsplit(url).hostname + ":8443"),
                               url.replace(urlsplit(url).path, "/private"),
                               url + "#fragment"):
                    with self.subTest(url=unsafe), self.assertRaises(CreativeResearchError):
                        _public_api_json(unsafe)
            self.assertEqual([call.args[0] for call in fetch.call_args_list],
                             list(allowed))

    def test_body_source_selection_preserves_explicit_network_grant(self):
        provider = FakePublicAPIs()
        provider.response = {"data": []}
        with tempfile.TemporaryDirectory() as root:
            catalog = body_catalog(root, research_client=CreativeResearch(provider))
            args = {"query": "public light", "media": "image",
                    "provider": "cleveland_museum"}
            with self.assertRaises(PermissionError):
                catalog.invoke("body.research_assets", args)
            self.assertFalse(provider.calls)
            result = catalog.invoke("body.research_assets", args,
                                    allowed_access=frozenset({"network"}))
            self.assertEqual(result["provider"], "cleveland_museum")
            self.assertFalse(result["import_authorized"])
            self.assertEqual(len(provider.calls), 1)
            provider.response = {"resultList": {"result": []}}
            papers = catalog.invoke("body.research_studies",
                {"query": "public attention", "provider": "europe_pmc"},
                allowed_access=frozenset({"network"}))
            self.assertEqual(papers["provider"], "europe_pmc")
            self.assertEqual(len(provider.calls), 2)

    def test_searxng_base_url_admits_only_explicit_loopback_service(self):
        self.assertIsNone(validate_searxng_url(None))
        self.assertEqual(validate_searxng_url("http://127.0.0.1:08080/"),
                         "http://127.0.0.1:8080")
        self.assertEqual(validate_searxng_url("http://[::1]:8080"),
                         "http://[::1]:8080")
        for url in ("", "http://127.0.0.1", "http://127.0.0.1:0",
                    "http://127.0.0.1:65536", "http://127.0.0.1:8080/search",
                    "http://127.0.0.1:8080?", "http://127.0.0.1:8080#",
                    "http://127.0.0.1:8080/?query=private",
                    "http://user@127.0.0.1:8080", "http://127.0.0.2:8080",
                    "http://localhost:8080", "https://127.0.0.1:8080",
                    "http://[::ffff:127.0.0.1]:8080", "http://127.0.0.1:80\n80",
                    "http://example.org:8080"):
            with self.subTest(url=url), self.assertRaises(CreativeResearchError):
                validate_searxng_url(url)

    def test_default_web_uses_builtin_wikipedia_without_host_setup(self):
        provider = FakePublicAPIs()
        provider.site_matrix = {"sitematrix": {
            "count": 5,
            "0": {"code": "hi", "site": [{"code": "wiki", "url": "https://hi.wikipedia.org"}]},
            "1": {"code": "en", "site": [{"code": "wiki", "url": "https://en.wikipedia.org"}]},
            "2": {"code": "ja", "site": [{"code": "wiki", "url": "https://ja.wikipedia.org"}]},
            "3": {"code": "nan", "site": [{"code": "wiki", "url": "https://zh-min-nan.wikipedia.org"}]},
            "4": {"code": "zh", "site": [{"code": "wiki", "url": "https://zh.wikipedia.org"}]},
        }}
        provider.response = {"query": {"search": [
            {"pageid": True, "title": "Invalid identity"},
            {"pageid": -1, "title": "Invalid identity"},
            {"pageid": 82, "title": "  <b>चलचित्र</b>  ",
             "snippet": "<em>संदर्भ</em>", "url": "https://example.org/ignored"},
            {"pageid": 82, "title": "Duplicate"},
            {"pageid": 83, "title": "Another"},
            {"pageid": 84, "title": "Beyond limit"},
        ]}}
        research = CreativeResearch(provider)
        response = research.web(query="  चलचित्र & प्रकाश  ", limit=2, language="hi")
        self.assertEqual(response["provider"], "wikipedia")
        self.assertEqual(response["results"], [
            {"title": "चलचित्र", "snippet": "संदर्भ",
             "source_page": "https://hi.wikipedia.org/?curid=82"},
            {"title": "Another", "snippet": "",
             "source_page": "https://hi.wikipedia.org/?curid=83"},
        ])
        self.assertTrue(response["result_content_untrusted"])
        self.assertFalse(response["source_pages_reviewed"])
        self.assertFalse(response["rights_verified"])
        self.assertFalse(response["import_authorized"])
        registry, requested = map(urlsplit, provider.calls)
        self.assertEqual(registry.netloc, "meta.wikimedia.org")
        self.assertNotIn("srsearch", parse_qs(registry.query))
        self.assertEqual((requested.scheme, requested.netloc, requested.path),
                         ("https", "hi.wikipedia.org", "/w/api.php"))
        self.assertEqual(parse_qs(requested.query), {
            "action": ["query"], "list": ["search"], "format": ["json"],
            "srnamespace": ["0"], "srprop": ["snippet"],
            "srsearch": ["चलचित्र & प्रकाश"], "srlimit": ["2"],
        })
        with self.assertRaises(CreativeResearchError):
            research.web(query="light", language="example.org")
        self.assertEqual(len(provider.calls), 2)
        for locale, expected in (("JA", "ja"), ("zh-Hant-TW", "zh"), ("nan", "zh-min-nan")):
            with self.subTest(locale=locale):
                result = research.web(query="international cinema", language=locale)
                self.assertTrue(result["results"][0]["source_page"].startswith(
                    f"https://{expected}.wikipedia.org/"))
        self.assertEqual(len(provider.calls), 5)
        self.assertEqual(sum(urlsplit(url).hostname == "meta.wikimedia.org" for url in provider.calls), 1)
        provider.response = {"query": {"search": {}}}
        with self.assertRaises(CreativeResearchError):
            research.web(query="light")
        self.assertEqual(urlsplit(provider.calls[-1]).hostname, "en.wikipedia.org")

    def test_builtin_lookup_rejects_unknown_closed_and_untrusted_catalog_hosts(self):
        provider = FakePublicAPIs()
        provider.site_matrix = {"sitematrix": {
            "0": {"code": "aa", "site": [{"code": "wiki", "url": "https://aa.wikipedia.org", "closed": ""}]},
            "1": {"code": "bb", "site": [{"code": "wiki", "url": "https://bb.wikipedia.org", "private": ""}]},
            "2": {"code": "cc", "site": [{"code": "wiki", "url": "https://cc.wikipedia.org:8443"}]},
            "3": {"code": "dd", "site": [{"code": "wiki", "url": "https://dd.wikipedia.org.evil.test"}]},
            "4": {"code": "ee", "site": [{"code": "wiktionary", "url": "https://ee.wikipedia.org"}]},
            "5": {"code": "fr", "site": [{"code": "wiki", "url": "https://fr.wikipedia.org"}]},
        }}
        research = CreativeResearch(provider)
        for language in ("aa", "bb", "cc", "dd", "ee", "unknown"):
            with self.subTest(language=language), self.assertRaises(CreativeResearchError):
                research.web(query="public topic", language=language)
        request, = map(urlsplit, provider.calls)
        self.assertEqual(request.hostname, "meta.wikimedia.org")
        self.assertNotIn("public", request.query)

    def test_public_transport_accepts_only_exact_wikipedia_api_authority(self):
        with patch("studio_next.creative_research._bounded_json_get", return_value={}) as fetch:
            for unsafe in ("http://ja.wikipedia.org/w/api.php",
                           "https://ja.wikipedia.org.evil.test/w/api.php",
                           "https://user@ja.wikipedia.org/w/api.php",
                           "https://ja.wikipedia.org:8443/w/api.php",
                           "https://ja.wikipedia.org/another-path",
                           "https://meta.wikimedia.org/another-path"):
                with self.subTest(url=unsafe), self.assertRaises(CreativeResearchError):
                    _public_api_json(unsafe)
            self.assertEqual(_public_api_json("https://ja.wikipedia.org/w/api.php"), {})
            fetch.assert_called_once_with("https://ja.wikipedia.org/w/api.php")

    def test_optional_searxng_keeps_references_unverified(self):
        provider = FakePublicAPIs()
        provider.response = {"results": [
            {"url": "https://127.0.0.1/private", "title": "Local request"},
            {"url": "https://example.org/lighting", "title": "<b>Window light</b>",
             "content": "<i>Public reference</i> " + "x" * 1_000,
             "thumbnail": "https://example.org/unused.jpg", "license": "CC0"},
            {"url": "https://example.org/ignored", "title": "Over limit"},
        ]}
        research = CreativeResearch(provider, searxng_url="http://[::1]:8080/")
        result = research.web(query="  देसी lighting & design  ", limit=1)
        self.assertEqual(result["kind"], "research_web_references")
        self.assertFalse(result["rights_verified"])
        self.assertFalse(result["import_authorized"])
        self.assertTrue(result["result_content_untrusted"])
        self.assertEqual(len(result["results"]), 1)
        reference = result["results"][0]
        self.assertEqual(reference["title"], "Window light")
        self.assertTrue(reference["snippet"].startswith("Public reference"))
        self.assertLessEqual(len(reference["snippet"]), 360)
        self.assertEqual(reference["source_page"], "https://example.org/lighting")
        self.assertNotIn("thumbnail", reference)
        self.assertNotIn("license", reference)
        self.assertEqual(len(provider.calls), 1)
        requested = urlsplit(provider.calls[0])
        self.assertEqual((requested.hostname, requested.port, requested.path), ("::1", 8080, "/search"))
        self.assertEqual(parse_qs(requested.query), {"q": ["देसी lighting & design"], "format": ["json"]})
        result = research.web(query="creative", language="pt-BR")
        self.assertEqual(result["provider"], "searxng")
        result = research.web(query="creative", language="all")
        self.assertEqual(result["provider"], "searxng")
        self.assertEqual([parse_qs(urlsplit(url).query)["language"] for url in provider.calls[1:]],
                         [["pt-BR"], ["all"]])
        provider.response = {"results": {}}
        with self.assertRaises(CreativeResearchError):
            research.web(query="design")

    def test_web_search_uses_loopback_json_and_refuses_redirects(self):
        requests = []

        class LocalSearch(BaseHTTPRequestHandler):
            def do_GET(self):
                uri = urlsplit(self.path)
                requests.append((uri.path, parse_qs(uri.query)))
                if parse_qs(uri.query).get("q") == ["redirect"]:
                    self.send_response(302)
                    self.send_header("Location", "/unapproved")
                    self.end_headers()
                    return
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"results":[]}')

            def log_message(self, *_args):
                pass

        with ThreadingHTTPServer(("127.0.0.1", 0), LocalSearch) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                research = CreativeResearch(searxng_url=f"http://127.0.0.1:{server.server_port}")
                self.assertEqual(research.web(query="lighting")["results"], [])
                with self.assertRaises(CreativeResearchError):
                    research.web(query="redirect")
            finally:
                server.shutdown()
                thread.join()
        self.assertEqual(requests, [("/search", {"q": ["lighting"], "format": ["json"]}),
                                    ("/search", {"q": ["redirect"], "format": ["json"]})])

    def test_openverse_cc0_filter_refuses_non_cc0_even_if_provider_misbehaves(self):
        provider = FakePublicAPIs()
        provider.response = {"results": [
            {"title": "Free music", "license": "cc0", "creator": "Composer",
             "foreign_landing_url": "https://example.org/audio"},
            {"title": "Not zero", "license": "by-nc", "creator": "Other",
             "foreign_landing_url": "https://example.org/not-zero"},
            {"title": "Local attack", "license": "cc0", "creator": "Other",
             "foreign_landing_url": "https://127.0.0.1/secret"},
            {"title": "Fake public-domain marker", "license": "pdm",
             "foreign_landing_url": "https://example.org/unknown"},
        ]}
        r = CreativeResearch(provider).assets(query="cinematic atmosphere",media="audio",limit=8)
        self.assertEqual([x["title"] for x in r["results"]], ["Free music"])
        self.assertEqual(r["results"][0]["rights_status"], "candidate_unverified")
        self.assertFalse(r["rights_verified"])
        self.assertFalse(r["import_authorized"])
        query = parse_qs(urlsplit(provider.calls[0]).query)
        self.assertEqual(query["license"], ["cc0"])
        self.assertEqual(query["mature"], ["false"])
        self.assertEqual(urlsplit(provider.calls[0]).hostname, "api.openverse.org")

    def test_wikimedia_video_accepts_only_cc0_video_with_source_page(self):
        provider = FakePublicAPIs()
        def entry(page_id, mime, license_name, license_url, page):
            return {"title": "File:Film.webm", "pageid": page_id,
                    "imageinfo": [{"mime": mime, "descriptionurl": page,
                                   "extmetadata": {
                                       "LicenseShortName": {"value": license_name},
                                       "LicenseUrl": {"value": license_url}}}]}
        cc0 = "https://creativecommons.org/publicdomain/zero/1.0/"
        provider.response = {"query": {"pages": {
            "1": entry(1,"video/webm","CC0",cc0,
                       "https://commons.wikimedia.org/wiki/File:Film.webm"),
            "2": entry(2,"video/webm","CC-BY",cc0,
                       "https://commons.wikimedia.org/wiki/File:Other.webm"),
            "3": entry(3,"image/png","CC0",cc0,
                       "https://commons.wikimedia.org/wiki/File:Picture.png"),
            "4": entry(4,"video/webm","CC0","https://example.org/fake-license",
                       "https://commons.wikimedia.org/wiki/File:Incorrect.webm"),
            "5": entry(5,"video/webm","CC0",cc0,
                       "https://private.example.org/wiki/File:Mirror.webm"),
        }}}
        result = CreativeResearch(provider).assets(
            query="nature cinematic",media="video",limit=8)
        self.assertEqual(result["provider"], "wikimedia_commons")
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["declared_license"], "CC0")
        self.assertEqual(result["results"][0]["rights_status"], "candidate_unverified")
        params = parse_qs(urlsplit(provider.calls[0]).query)
        self.assertIn("filetype:video", params["gsrsearch"][0])
        self.assertEqual(params["gsrnamespace"], ["6"])

    def test_studies_are_metadata_not_fabricated_audience_findings(self):
        provider = FakePublicAPIs()
        provider.response = {"message":{"items":[
            {"type":"journal-article","DOI":"10.1234/story.1",
             "title":["<i>Narrative attention</i>"],"container-title":["Journal"],
             "published":{"date-parts":[[2025,5,7]]}},
            {"type":"book","DOI":"10.2345/book","title":["Marketing"]},
            {"type":"journal-article","DOI":"https://evil.example/attack",
             "title":["Bad DOI"]},
            {"type":"journal-article","DOI":"10.1234/story.2",
             "title":["Unknown publication date"],"published":"unexpected"},
        ]}}
        result = CreativeResearch(provider).studies(query="storytelling attention",limit=8)
        self.assertEqual(len(result["results"]),2)
        self.assertEqual(result["results"][0]["title"],"Narrative attention")
        self.assertEqual(result["results"][0]["year"],2025)
        self.assertIsNone(result["results"][1]["year"])
        self.assertFalse(result["results"][0]["study_results_verified"])
        self.assertFalse(result["results"][0]["peer_review_independently_verified"])
        self.assertIn("not evidence",result["claim"])
        params=parse_qs(urlsplit(provider.calls[0]).query)
        self.assertEqual(params["filter"],["type:journal-article"])
        self.assertEqual(urlsplit(provider.calls[0]).hostname,"api.crossref.org")

    def test_artic_filter_excludes_copyrighted_artworks(self):
        provider = FakePublicAPIs()
        provider.response = {"data": [
            {"id": 123, "title": "Public art", "is_public_domain": True,
             "image_id": "12345678-1234-1234-1234-123456789abc"},
            {"id": 456, "title": "Restricted", "is_public_domain": False,
             "image_id": "12345678-1234-1234-1234-123456789abc"}]}
        found = CreativeResearch(provider)._artic_images("artwork", 5)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["rights_status"], "candidate_unverified")
        self.assertEqual(urlsplit(provider.calls[0]).hostname, "api.artic.edu")

    def test_sfx_search_ignores_non_cc0_records(self):
        provider = FakePublicAPIs()
        provider.response = {"matches": [
            {"title": "Whoosh", "license": "CC0",
             "page_url": "https://sfxmint.com/sounds/whoosh"},
            {"title": "Other", "license": "custom",
             "page_url": "https://sfxmint.com/sounds/other"}]}
        found = CreativeResearch(provider)._sfxmint_audio("whoosh", 3)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["declared_license"], "CC0")
        uri = urlsplit(provider.calls[0])
        self.assertEqual(uri.hostname, "sfxmint.com")
        self.assertEqual(uri.path, "/api/v1/search")

    def test_polyhaven_and_ambientcg_only_surface_cc0_candidate_3d(self):
        from studio_next.creative_research_3d import (
            poly_haven_assets, ambientcg_assets)
        calls = []
        def provider(url):
            calls.append(url)
            if urlsplit(url).hostname == "api.polyhaven.com":
                return {"results": [
                    {"slug": "ornate_chair", "score": 0.8},
                    {"slug": "../../unsafe", "score": 0.9}]}
            return {"assets": [
                {"id": "Rock001", "title": "Cliff Rock"},
                {"id": "bad/path", "title": "Invalid"}]}
        one = poly_haven_assets(provider,"stylized chair",3,type_name="models")
        two = ambientcg_assets(provider,"stone",3,type_name="3d-model")
        self.assertEqual(len(one), 1)
        self.assertEqual(len(two), 1)
        self.assertEqual(one[0]["provider_credit"],"Powered by Poly Haven")
        self.assertEqual(one[0]["rights_status"],"candidate_unverified")
        self.assertEqual(two[0]["media_type"],"3d")
        self.assertTrue(all(x["declared_license"]=="CC0" for x in one+two))
        self.assertEqual([urlsplit(x).hostname for x in calls],
                         ["api.polyhaven.com","ambientcg.com"])
        self.assertEqual(parse_qs(urlsplit(calls[0]).query)["t"],["models"])
        self.assertEqual(parse_qs(urlsplit(calls[1]).query)["type"],["3d-model"])

    def test_existing_3d_research_adapters_are_reachable_without_new_network_grant(self):
        calls = []
        def fetch(url):
            calls.append(url)
            if urlsplit(url).hostname == "api.polyhaven.com":
                raise CreativeResearchError("Synthetic unavailable primary")
            return {"assets": [{"id": "Source001", "title": "Original source"},
                               {"id": "../invalid", "title": "Unsafe path"}]}
        research = CreativeResearch(fetch)
        expected = {"3d": ("models", "3d-model"), "texture": ("textures", "material"),
                    "hdri": ("hdris", "hdri")}
        for media, (primary, fallback) in expected.items():
            with self.subTest(media=media):
                calls.clear()
                receipt = research.assets(query="public source", media=media, limit=2)
                self.assertEqual(receipt["media"], media)
                self.assertEqual(receipt["provider"], "ambientcg")
                self.assertTrue(receipt["fallback_used"])
                self.assertFalse(receipt["rights_verified"])
                self.assertFalse(receipt["import_authorized"])
                self.assertEqual(len(receipt["results"]), 1)
                self.assertEqual(receipt["results"][0]["asset_kind"], fallback)
                self.assertEqual(receipt["results"][0]["rights_status"], "candidate_unverified")
                self.assertEqual(len(calls), 2)
                self.assertEqual(parse_qs(urlsplit(calls[0]).query)["t"], [primary])
                self.assertEqual(parse_qs(urlsplit(calls[1]).query)["type"], [fallback])
        calls.clear()
        with tempfile.TemporaryDirectory() as root:
            catalog = body_catalog(root, research_client=research)
            spec = next(s for s in catalog.discover() if s["id"] == "body.research_assets")
            self.assertEqual(set(spec["schema"]["properties"]["media"]["enum"]),
                             {"image", "audio", "video", "3d", "texture", "hdri"})
            self.assertEqual(spec["access"], "network")
            with self.assertRaises(PermissionError):
                catalog.invoke("body.research_assets", {"query": "public", "media": "3d"})
            self.assertFalse(calls)
            result = catalog.invoke("body.research_assets", {"query": "public", "media": "3d"},
                                    allowed_access=frozenset({"network"}))
            self.assertEqual(len(result["results"]), 1)
            self.assertEqual(len(calls), 2)

    def test_3d_provider_transport_admits_only_exact_metadata_paths(self):
        valid = ("https://api.polyhaven.com/search?q=chair&t=models&limit=2",
                 "https://ambientcg.com/api/v3/assets?q=rock&type=3d-model&limit=2")
        invalid = ("https://api.polyhaven.com/files/chair",
                   "https://ambientcg.com/api/v3/downloads",
                   "https://api.polyhaven.com:443/search",
                   "https://user@ambientcg.com/api/v3/assets",
                   "https://api.polyhaven.com.evil.example/search")
        with patch("studio_next.creative_research._bounded_json_get", return_value={}) as network:
            for url in valid:
                self.assertEqual(_public_api_json(url), {})
            for url in invalid:
                with self.assertRaises(CreativeResearchError):
                    _public_api_json(url)
            self.assertEqual([call.args[0] for call in network.call_args_list], list(valid))

    def test_polyhaven_live_api_source_credit_remains_in_actual_asset_result(self):
        def fetch(url):
            return {"results": [{"slug": "public_chair"}, {"slug": "../invalid"}]}
        result = CreativeResearch(fetch).assets(query="chair", media="3d", limit=2)
        self.assertEqual(result["provider"], "poly_haven")
        self.assertEqual(result["provider_credit"], "Powered by Poly Haven")
        self.assertEqual(result["results"][0]["provider_credit"], "Powered by Poly Haven")
        self.assertEqual(len(result["results"]), 1)
        self.assertFalse(result["import_authorized"])

    def test_query_budget_and_media_rejection_do_not_contact_provider(self):
        provider = FakePublicAPIs()
        research=CreativeResearch(provider)
        for args in ({"query":"","media":"image"},
                     {"query":"x"*241,"media":"image"},
                     {"query":"x","media":"script"},
                     {"query":"x","media":"video","limit":0},
                     {"query":"x","media":"image","limit":True},
                     {"query":"x","media":"image","limit":50}):
            with self.subTest(args=args),self.assertRaises(CreativeResearchError):
                research.assets(**args)
        with self.assertRaises(CreativeResearchError):
            research.studies(query="x"*241)
        self.assertFalse(provider.calls)

    def test_unavailable_openverse_is_explicitly_replaced_only_by_cc0_commons(self):
        urls = []
        def provider(url):
            urls.append(url)
            host = urlsplit(url).hostname
            if host == "api.openverse.org":
                raise CreativeResearchError("Offline public API")
            if host == "api.artic.edu":
                raise CreativeResearchError("Museum unavailable")
            if host == "commons.wikimedia.org":
                return {"query": {"pages": {"1": {
                    "title": "File:Free image.png",
                    "imageinfo": [{"mime": "image/png",
                        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Free_image.png",
                        "extmetadata": {
                            "LicenseShortName": {"value": "CC0"},
                            "LicenseUrl": {"value":
                                "https://creativecommons.org/publicdomain/zero/1.0/"}}}],
                }}}}
            raise AssertionError("Unexpected provider")
        result = CreativeResearch(provider).assets(
            query="visual cinema",media="image",limit=3)
        self.assertEqual(result["provider"],"wikimedia_commons")
        self.assertTrue(result["fallback_used"])
        self.assertEqual(result["provider_failures"],["openverse_unavailable_or_invalid",
                         "art_institute_chicago_unavailable_or_invalid"])
        self.assertEqual(len(result["results"]),1)
        self.assertFalse(result["rights_verified"])
        self.assertEqual([urlsplit(u).hostname for u in urls],
                         ["api.openverse.org","api.artic.edu","commons.wikimedia.org"])
        self.assertIn("filetype:bitmap",
                      parse_qs(urlsplit(urls[-1]).query)["gsrsearch"][0])

    def test_untrusted_provider_structures_fail_and_do_not_invent_results(self):
        for search,media,data in (
            ("assets","image",{"results":{}, "query":{"pages":[]}}),
            ("assets","video",{"query":{"pages":[]}}),
            ("studies",None,{"message":{"items":{}}}),
        ):
            provider=FakePublicAPIs()
            provider.response=data
            with self.subTest(search=search,media=media):
                with self.assertRaises(CreativeResearchError):
                    if search=="assets":
                        CreativeResearch(provider).assets(query="visual",media=media)
                    else:
                        CreativeResearch(provider).studies(query="film language")

    def test_no_internal_links_and_no_unapproved_request_host(self):
        for link in ("http://example.com", "https://localhost/private",
                     "https://192.168.1.1/private","https://user:pwd@example.org/",
                     "https://10.0.0.1/", "https://example.internal/",
                     "https://localhost./private", "https://test.local./private",
                     "https://127.0.0.1./secret", "https://127.1/secret",
                     "https://0177.0.0.1/secret", "https://0x7f.1/secret",
                     "https://0x7f000001/secret",
                     "https://127%2E0%2E0%2E1/secret",
                     "https://[::ffff:127.0.0.1]/secret"):
            with self.subTest(link=link):
                self.assertIsNone(_public_https(link))
        self.assertEqual(_public_https("https://example.org/visible"), 
                         "https://example.org/visible")
        with self.assertRaises(CreativeResearchError):
            _public_api_json("https://evil.example.org/collect?data=secret")

    def test_body_catalog_discovers_but_does_not_grant_network_implicitly(self):
        provider=FakePublicAPIs()
        provider.response={"results":[]}
        with tempfile.TemporaryDirectory() as root:
            catalog=body_catalog(root,research_client=CreativeResearch(provider))
            specs={s["id"]:s for s in catalog.discover()}
            for name in ("body.research_assets","body.research_studies"):
                self.assertEqual(specs[name]["access"],"network")
                self.assertEqual(specs[name]["status"],"installed")
                self.assertNotIn(name,catalog.executable_ids({"read"}))
                self.assertIn(name,catalog.executable_ids({"network"}))
            with self.assertRaises(PermissionError):
                catalog.invoke("body.research_assets",
                               {"query":"visual","media":"image"})
            self.assertFalse(provider.calls)
            result=catalog.invoke("body.research_assets",
                                  {"query":"visual","media":"image"},
                                  allowed_access=frozenset({"network"}))
            self.assertEqual(result["kind"],"research_asset_candidates")
            self.assertFalse(result["import_authorized"])
            self.assertEqual(len(provider.calls),1)
            with self.assertRaises(ValueError):
                catalog.invoke("body.research_assets",
                               {"query":"x","media":"image","unsafe":"injected"},
                               allowed_access=frozenset({"network"}))
            self.assertEqual(len(provider.calls),1)


@unittest.skipUnless(importlib.util.find_spec("mcp") is not None,
                     "Optional research MCP SDK is not installed")
class ResearchMCPTests(unittest.IsolatedAsyncioTestCase):

    async def test_restored_reference_source_uses_existing_mcp_budget_and_schema(self):
        from studio_next.creative_research_mcp import CreativeResearchMcpSession
        provider = FakePublicAPIs()
        provider.response = {"collection": {"items": [
            {"data": [{"nasa_id": "Apollo_16", "title": "Moon",
                       "media_type": "video"}]},
        ]}}
        session = CreativeResearchMcpSession(
            allow_public_research=True, research_client=CreativeResearch(provider),
            max_calls=1)
        tools = {tool.name: tool for tool in (await session.list_tools()).tools}
        for tool, choice in (("research_assets", "cleveland_museum"),
                             ("research_studies", "europe_pmc"),
                             ("research_web", "nasa_archive")):
            self.assertIn(choice, tools[tool].input_schema["properties"]["provider"]["enum"])
        invalid = await session.call_tool("research_web",
            {"query": "moon", "provider": "https://evil.test"})
        self.assertTrue(invalid.is_error)
        self.assertEqual(provider.calls, [])
        reply = await session.call_tool("research_web",
            {"query": "moon", "provider": "nasa_archive"})
        self.assertFalse(reply.is_error)
        receipt = json.loads(reply.content[0].text)
        self.assertEqual(receipt["provider"], "nasa_archive")
        self.assertTrue(receipt["results"][0]["model_has_not_watched_video"])
        self.assertFalse(receipt["import_authorized"])
        denied = await session.call_tool("research_studies",
            {"query": "public attention", "provider": "europe_pmc"})
        self.assertEqual(json.loads(denied.content[0].text)["status"],
                         "call_budget_exhausted")
        self.assertEqual(len(provider.calls), 1)

    def test_host_network_permission_is_mandatory(self):
        from studio_next.creative_research_mcp import (
            create_research_server, CreativeResearchMcpSession)
        with self.assertRaises(PermissionError):
            create_research_server()
        for count in (None, 0, 9, True, -1):
            with self.subTest(count=count), self.assertRaises(ValueError):
                CreativeResearchMcpSession(allow_public_research=True, max_calls=count)

    async def test_existing_research_mcp_exposes_same_3d_metadata_contract(self):
        from studio_next.creative_research_mcp import CreativeResearchMcpSession
        calls = []
        def provider(url):
            calls.append(url)
            return {"results": [{"slug": "public_chair"}]}
        session = CreativeResearchMcpSession(
            allow_public_research=True, research_client=CreativeResearch(provider), max_calls=1)
        tools = (await session.list_tools()).tools
        spec = next(t for t in tools if t.name == "research_assets")
        self.assertEqual(set(spec.input_schema["properties"]["media"]["enum"]),
                         {"image", "audio", "video", "3d", "texture", "hdri"})
        result = await session.call_tool("research_assets", {"query": "chair", "media": "3d"})
        self.assertFalse(result.is_error)
        receipt = json.loads(result.content[0].text)
        self.assertEqual(receipt["provider"], "poly_haven")
        self.assertFalse(receipt["import_authorized"])
        blocked = await session.call_tool("research_assets", {"query": "chair", "media": "hdri"})
        self.assertEqual(json.loads(blocked.content[0].text)["status"], "call_budget_exhausted")
        self.assertEqual(len(calls), 1)

    async def test_real_mcp_protocol_exposes_only_bounded_readonly_research(self):
        import anyio
        from mcp import ClientSession
        from mcp.shared.memory import create_client_server_memory_streams
        from studio_next.creative_research_mcp import create_research_server

        class PreparedResearch:
            def __init__(self):
                self.calls = []

            def assets(self, **kwargs):
                self.calls.append(("assets", kwargs))
                return {"kind": "research_asset_candidates", "results": [],
                        "import_authorized": False}

            def studies(self, **kwargs):
                self.calls.append(("studies", kwargs))
                return {"kind": "creative_audience_research", "results": []}

        research = PreparedResearch()
        server = create_research_server(
            allow_public_research=True, research_client=research)
        async with create_client_server_memory_streams() as (client_streams, server_streams):
            async with anyio.create_task_group() as group:
                group.start_soon(server.run, *server_streams,
                                 server.create_initialization_options())
                async with ClientSession(*client_streams) as session:
                    await session.initialize()
                    tools = (await session.list_tools()).tools
                    self.assertEqual({tool.name for tool in tools},
                                     {"research_assets", "research_studies"})
                    response = await session.call_tool(
                        "research_assets", {"query": "light", "media": "video"})
                    self.assertFalse(response.is_error)
                    self.assertFalse(json.loads(response.content[0].text)
                                     ["import_authorized"])
                    invalid = await session.call_tool(
                        "research_assets", {"query": "light", "media": "video",
                                            "limit": 0})
                    self.assertTrue(invalid.is_error)
                    self.assertEqual(research.calls,
                                     [("assets", {"query": "light", "media": "video"})])
                    # The standalone official MCP entry must be no less
                    # bounded than an opt-in Studio session. Invalid schema
                    # calls do not consume research budget; successful calls do.
                    for index in range(7):
                        good = await session.call_tool(
                            "research_studies", {"query": f"public-query-{index}"})
                        self.assertFalse(good.is_error)
                    denied = await session.call_tool(
                        "research_studies", {"query": "ninth-outbound-query"})
                    self.assertFalse(denied.is_error)
                    status = json.loads(denied.content[0].text)
                    self.assertEqual(status["status"], "call_budget_exhausted")
                    self.assertFalse(status["import_authorized"])
                    self.assertEqual(len(research.calls), 8)
                    self.assertFalse(any("ninth-outbound-query" in str(call)
                                         for call in research.calls))
                group.cancel_scope.cancel()

if __name__ == "__main__":
    unittest.main()

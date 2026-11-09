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
    def test_host_network_permission_is_mandatory(self):
        from studio_next.creative_research_mcp import (
            create_research_server, CreativeResearchMcpSession)
        with self.assertRaises(PermissionError):
            create_research_server()
        for count in (None, 0, 9, True, -1):
            with self.subTest(count=count), self.assertRaises(ValueError):
                CreativeResearchMcpSession(allow_public_research=True, max_calls=count)

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

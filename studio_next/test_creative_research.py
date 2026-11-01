"""Offline adversarial contract tests; no paid API and no network traffic."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from studio_next.creative_research import (
    CreativeResearch, CreativeResearchError, _public_https, _public_api_json)
from studio_next.body_integration import body_catalog


class FakePublicAPIs:
    def __init__(self):
        self.calls = []
        self.response = {}

    def __call__(self, url):
        self.calls.append(url)
        return self.response


class CreativeResearchTests(unittest.TestCase):
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
        ]}}
        result = CreativeResearch(provider).studies(query="storytelling attention",limit=8)
        self.assertEqual(len(result["results"]),1)
        self.assertEqual(result["results"][0]["title"],"Narrative attention")
        self.assertEqual(result["results"][0]["year"],2025)
        self.assertFalse(result["results"][0]["study_results_verified"])
        self.assertFalse(result["results"][0]["peer_review_independently_verified"])
        self.assertIn("not evidence",result["claim"])
        params=parse_qs(urlsplit(provider.calls[0]).query)
        self.assertEqual(params["filter"],["type:journal-article"])
        self.assertEqual(urlsplit(provider.calls[0]).hostname,"api.crossref.org")

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
        self.assertEqual(result["provider_failures"],["openverse_unavailable_or_invalid"])
        self.assertEqual(len(result["results"]),1)
        self.assertFalse(result["rights_verified"])
        self.assertEqual([urlsplit(u).hostname for u in urls],
                         ["api.openverse.org","commons.wikimedia.org"])
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
                     "https://10.0.0.1/", "https://example.internal/"):
            self.assertIsNone(_public_https(link))
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


if __name__ == "__main__":
    unittest.main()

"""Creative-research source independence, permissions and future-domain tests.

Fixture responses are NEVER evidence of live creativity or lawful asset reuse.
"""
import tempfile
import unittest
from urllib.parse import urlsplit, parse_qs

from studio_next.creative_research import CreativeResearchError
from studio_next.creative_research_hub import (
    CreativeResearchHub, CreativeSource, _cleveland_images,
    _wikipedia_reference,
)
from studio_next.body_integration import body_catalog


class FederatedCreativeResearchTests(unittest.TestCase):
    def test_all_creative_domains_accept_source_plugins_without_core_changes(self):
        calls = []
        def textile(query, count):
            calls.append(("textile", query, count))
            return [{"title": "Fabric study",
                     "source_page": "https://example.org/fabric",
                     "declared_license": "CC0",
                     "rights_status": "candidate_unverified",
                     "media_type": "3d"}]
        def title_facts(query, count):
            return [{"title": "Visual rhythm",
                     "source_page": "https://example.org/visual-rhythm"}]
        hub = CreativeResearchHub([
            CreativeSource("textile_reference", "assets", frozenset({"3d"}), textile),
            CreativeSource("visual_rhythm", "knowledge", frozenset({"all"}), title_facts)])
        output = hub.research(query="fabric shape and rhythm", domain="all")
        self.assertEqual(len(output["results"]), 2)
        self.assertEqual(len(output["source_outcomes"]), 2)
        self.assertFalse(output["rights_verified"])
        self.assertFalse(output["import_authorized"])
        self.assertFalse(output["human_preference_inferred"])
        self.assertEqual(calls,[("textile","fabric shape and rhythm",12)])
        self.assertEqual(len(hub.research(query="fabric shape and rhythm",
                                          domain="assets",media="3d")["results"]), 1)

    def test_provider_failures_do_not_erase_independent_creative_sources(self):
        def unavailable(q,n):
            raise ConnectionError("Provider outage")
        def useful(q,n):
            return [{"title": "Auditory perspective",
                     "source_page": "https://example.org/ear"}]
        hub = CreativeResearchHub([
            CreativeSource("broken_source", "knowledge", frozenset({"all"}), unavailable),
            CreativeSource("useful_source", "knowledge", frozenset({"all"}), useful)])
        result=hub.research(query="sound storytelling")
        self.assertEqual(len(result["results"]),1)
        self.assertEqual([s["state"] for s in result["source_outcomes"]],
                         ["failed","responded"])
        self.assertFalse(result["all_sources_exhausted"])

    def test_one_large_source_does_not_monopolize_all_results(self):
        def a(q,n):
            return [{"title": "A","source_page": f"https://a.example.org/{i}"} for i in range(6)]
        def b(q,n):
            return [{"title": "B","source_page": f"https://b.example.org/{i}"} for i in range(6)]
        hub = CreativeResearchHub([
            CreativeSource("first", "knowledge", frozenset({"all"}),a),
            CreativeSource("second","knowledge",frozenset({"all"}),b)])
        r = hub.research(query="story arc",limit=4)
        self.assertEqual([v["source"] for v in r["results"]],
                         ["first","second","first","second"])

    def test_cache_only_successful_records_and_isolated_copies(self):
        calls=[]
        def source(q,n):
            calls.append(q)
            return [{"title":"Edit reference","source_page":"https://example.org/edit"}]
        now=[10.0]
        hub = CreativeResearchHub([
            CreativeSource("source_1","knowledge",frozenset({"all"}),source)],
            cache_seconds=30,clock=lambda: now[0])
        first=hub.research(query="camera edit")
        first["results"].clear()
        second=hub.research(query="camera edit")
        self.assertEqual(len(second["results"]),1)
        self.assertEqual(len(calls),1)
        now[0]+=31
        hub.research(query="camera edit")
        self.assertEqual(len(calls),2)

    def test_discovery_not_paid_or_license_approval(self):
        hub = CreativeResearchHub([
            CreativeSource("custom_motion","assets",
                           frozenset({"video","3d"}),lambda q,n:[])])
        names=hub.discover()
        self.assertEqual(names[0]["id"],"custom_motion")
        self.assertFalse(names[0]["paid_inference_required"])
        self.assertFalse(names[0]["rights_attested_by_this_tool"])

    def test_unsafe_or_non_cc0_media_is_not_admitted_even_from_buggy_provider(self):
        def source(q,n):
            return [
                {"source_page":"https://good.example.org/one",
                 "declared_license":"CC-BY","rights_status":"candidate_unverified"},
                {"source_page":"https://127.0.0.1/secret","declared_license":"CC0",
                 "rights_status":"candidate_unverified"},
                {"source_page":"https://good.example.org/two","declared_license":"CC0",
                 "rights_status":"candidate_unverified"},
            ]
        hub = CreativeResearchHub([
            CreativeSource("media_source","assets",frozenset({"image"}),source)])
        output = hub.research(query="graphics",domain="assets",media="image")
        self.assertEqual(len(output["results"]),1)
        self.assertEqual(output["results"][0]["source_page"],
                         "https://good.example.org/two")

    def test_explicit_cc0_cleveland_metadata_and_public_image(self):
        urls=[]
        def fetch(url):
            urls.append(url)
            return {"data":[
                {"id":1,"accession_number":"1923.1","title":"Light",
                 "share_license_status":"CC0",
                 "images":{"web":{"url":"https://images.example.org/a.jpg"}}},
                {"id":2,"accession_number":"1923.2","title":"Not public",
                 "share_license_status":"Copyrighted",
                 "images":{"web":{"url":"https://images.example.org/b.jpg"}}},
                {"id":3,"accession_number":"1923.3","title":"No image",
                 "share_license_status":"CC0", "images":{}},
            ]}
        found=_cleveland_images(fetch,"light",5)
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]["source_page"],
                         "https://www.clevelandart.org/art/1923.1")
        self.assertEqual(found[0]["rights_status"],"candidate_unverified")
        self.assertEqual(parse_qs(urlsplit(urls[0]).query,
                                  keep_blank_values=True)["cc0"],[""])

    def test_wikipedia_technique_research_not_mistaken_for_cc0_asset(self):
        def fetch(url):
            return {"query":{"search":[
                {"title":"Film editing"},
                {"title":"Cinematography"}]}}
        records=_wikipedia_reference(fetch,"cinema",2)
        self.assertEqual(len(records),2)
        self.assertEqual(records[0]["source_page"],
                         "https://en.wikipedia.org/wiki/Film_editing")
        self.assertTrue(records[0]["research_not_a_reuse_license"])

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

    def test_registered_3d_sources_do_not_require_paid_or_model_backend(self):
        def provider(url):
            if urlsplit(url).hostname == "api.polyhaven.com":
                return {"results":[{"slug":"camera_tripod"}]}
            if urlsplit(url).hostname == "ambientcg.com":
                return {"assets":[{"id":"Camera001","title":"Camera"}]}
            raise RuntimeError("Offline")
        hub = CreativeResearchHub.installed(fetch_json=provider)
        r = hub.research(query="camera",domain="assets",media="3d",limit=6)
        self.assertEqual(len(r["results"]),2)
        self.assertFalse(r["rights_verified"])
        self.assertEqual(set(x["source"] for x in r["results"]),
                         {"polyhaven_models","ambientcg_models"})

    def test_nasa_video_is_research_reference_not_automatically_licensed(self):
        from studio_next.creative_research_sources import nasa_video_references
        def fetch(url):
            self.assertEqual(urlsplit(url).hostname, "images-api.nasa.gov")
            return {"collection":{"items":[
                {"data":[{"nasa_id":"Apollo_16","title":"Moon camera",
                          "media_type":"video"}]},
                {"data":[{"nasa_id":"Bad/Asset","title":"Bad ID",
                          "media_type":"video"}]},
            ]}}
        results=nasa_video_references(fetch,"moon footage",3)
        self.assertEqual(len(results),1)
        self.assertTrue(results[0]["source_reuse_not_authorized"])
        self.assertTrue(results[0]["model_has_not_watched_video"])

    def test_europe_pmc_abstract_is_limited_and_not_scientific_acceptance(self):
        from studio_next.creative_research_sources import europe_pmc_abstracts
        def fetch(url):
            self.assertEqual(urlsplit(url).hostname,"www.ebi.ac.uk")
            return {"resultList":{"result":[
                {"id":"123456","source":"MED","title":"Narrative attentional capture",
                 "pubYear":"2024","abstractText":"<b>Methods</b> " + "A"*2000},
                {"id":"bad/path","source":"MED","title":"Unknown"},
            ]}}
        results=europe_pmc_abstracts(fetch,"visual attention",3)
        self.assertEqual(len(results),1)
        self.assertLessEqual(len(results[0]["abstract_excerpt"]),320)
        self.assertFalse(results[0]["study_results_verified"])
        self.assertTrue(results[0]["abstract_is_unreviewed_source_text"])

    def test_body_catalog_has_no_extra_creative_research_setup(self):
        def arts(q,n):
            return [{"title":"Lighting",
                     "source_page":"https://example.org/lighting"}]
        hub=CreativeResearchHub([
            CreativeSource("creative_lighting","knowledge",frozenset({"all"}),arts)])
        with tempfile.TemporaryDirectory() as root:
            c=body_catalog(root,research_hub=hub)
            self.assertIn("body.research_creative",
                          {x["id"] for x in c.discover()})
            with self.assertRaises(PermissionError):
                c.invoke("body.research_creative",{"query":"lighting"})
            result=c.invoke("body.research_creative",
                            {"query":"lighting"},allowed_access={"network"})
            self.assertEqual(len(result["results"]),1)

    def test_malformed_creative_query_fails_without_network(self):
        calls=[]
        hub=CreativeResearchHub([
            CreativeSource("light_source","knowledge",frozenset({"all"}),
                           lambda q,n:calls.append(q) or [])])
        with self.assertRaises(CreativeResearchError):
            hub.research(query="gorgeous",domain="unknown")
        with self.assertRaises(CreativeResearchError):
            hub.research(query="gorgeous",limit=0)
        self.assertFalse(calls)


if __name__ == "__main__":
    unittest.main()

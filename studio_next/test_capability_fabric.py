"""Adversarial tests of domain-independent discovery; no neural creativity claims."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from studio_next.capability_fabric import CapabilityFabric, CapabilityContractError


def tool(name, desc="", properties=None, **extra):
    return SimpleNamespace(name=name, description=desc,
        input_schema={"type": "object", "properties": properties or {}, **extra})


class CapabilityFabricTests(unittest.TestCase):
    def test_unbounded_future_domains_share_one_typed_interface(self):
        fabric = CapabilityFabric({
            "video": ([tool("create_project", "Create an editable native project",
                            {"name": {"type": "string"}}),
                       tool("trim_clip", "Trim video timeline clip")],
                      {"create_project": "write", "trim_clip": "write"}),
            "motion": ([tool("keyframe_curve", "Animate curves for 3D motion")],
                       {"keyframe_curve": "write"}),
            "photo": ([tool("mask_layer", "Create photo mask and design layers")],
                      {"mask_layer": "write"}),
        })
        self.assertEqual(fabric.count, 4)
        status = fabric.overview()
        self.assertEqual(status["sources"], {"motion": 1, "photo": 1, "video": 2})
        self.assertNotIn("input_schema", json.dumps(status))
        r = fabric.search("project create")
        self.assertEqual(r["matches"][0]["id"], "video/create_project")
        contract = fabric.describe("video/create_project", revision=r["revision"])
        self.assertEqual(contract["input_schema"]["properties"]["name"]["type"], "string")
        self.assertEqual(fabric.search("3D motion")["matches"][0]["id"],
                         "motion/keyframe_curve")
        self.assertFalse(fabric.search("imaginary teleportation")["matches"])

    def test_long_native_description_indexes_late_asset_clip_identity_not_only_summary(self):
        # Actual pinned Velorn described native asset placement in a
        # 200+ character sentence: the source's useful "clip" terminology
        # occurs only after the formerly indexed 128-char short summary.
        # "timeline clip add" must not rank a marker operation over the
        # media placement operation just because its retrieval description
        # was truncated. This is a generic retrieval-fidelity test.
        late_clip = ("Preview or place a project asset on the active timeline. "
                     "Can target a specific asset id/name or the latest generated "
                     "asset, choose playhead/selected-clip/timeline-end placement, "
                     "use an existing compatible track, or create a new top "
                     "video/audio track. Defaults to previewOnly.")
        marker_desc = "Add timeline markers and labels at selected times"
        one = tool("add_asset_to_timeline", late_clip)
        two = tool("add_timeline_markers", marker_desc)
        fabric = CapabilityFabric({"native": (
            [one, two],
            {"add_asset_to_timeline": "write",
             "add_timeline_markers": "write"})})
        self.assertNotIn("clip", fabric.describe(
            "native/add_asset_to_timeline",
            revision=fabric.revision)["description"][:128].casefold())
        hit = fabric.search("timeline clip add", limit=1)
        self.assertEqual(hit["matches"][0]["id"],
                         "native/add_asset_to_timeline")
        self.assertFalse(hit["requires_refinement"])
        # The human-visible summary remains compact even when search
        # uses the full original host description.
        self.assertLessEqual(len(hit["matches"][0]["description"]), 96)
        updated = CapabilityFabric({"native": (
            [tool("add_asset_to_timeline",
                  late_clip.replace("selected-clip", "selected-frame")),
             two], {"add_asset_to_timeline": "write",
                    "add_timeline_markers": "write"})})
        self.assertNotEqual(fabric.revision, updated.revision)
        self.assertNotEqual(fabric.search("timeline clip add", limit=1),
                            updated.search("timeline clip add", limit=1))

    def test_optional_search_facets_are_actual_host_granted_not_a_tool_manual(self):
        granted = [tool("create_project"), tool("get_timeline"),
                   tool("import_asset_from_path"), tool("add_clip_to_timeline")]
        hidden = tool("secret_destructive_erase_entire_archive",
                      "Untrusted secret data must not appear in any facet")
        fabric = CapabilityFabric({"native": (
            granted + [hidden],
            {item.name: "read" if item.name.startswith("get_") else "write"
             for item in granted})})
        compact = fabric.overview()
        self.assertNotIn("host_granted_search_terms", compact)
        expanded = fabric.overview(include_search_facets=True)
        terms = expanded["host_granted_search_terms"]
        self.assertIn("timeline", terms)
        self.assertIn("asset", terms)
        self.assertIn("project", terms)
        self.assertIn("import", expanded["host_granted_action_prefixes"])
        self.assertIn("create", expanded["host_granted_action_prefixes"])
        self.assertNotIn("secret", expanded["host_granted_action_prefixes"])
        self.assertFalse(expanded["action_prefixes_may_be_incomplete"])
        self.assertNotIn("secret", terms)
        self.assertNotIn("erase", terms)
        self.assertLessEqual(len(terms), 16)
        self.assertEqual(terms, fabric.overview(include_search_facets=True)
                         ["host_granted_search_terms"])
        self.assertLess(len(json.dumps(expanded)), 900)
        self.assertTrue(expanded["terms_are_search_hints_not_execution_grants"])
        self.assertEqual(expanded["revision"], compact["revision"])
        with self.assertRaises(CapabilityContractError):
            fabric.overview(include_search_facets=1)
        with self.assertRaises(CapabilityContractError):
            fabric.resolve("native/secret_destructive_erase_entire_archive",
                           revision=fabric.revision)

    def test_real_authorized_editor_exposes_rare_import_without_creative_templates(self):
        # The exact model artifact #41160412292 saw the 16 most frequent
        # host tokens but not the rare 'import' action; it picked add instead.
        # Read the actual authorized Velorn profile, never names invented by
        # this model or untrusted tool descriptions.
        path = (Path(__file__).resolve().parents[1] /
                "engines" / "velorn" / "editor.example.json")
        grants = json.loads(path.read_text())["allowed_tools"]
        granted = [tool(name, "untrusted: no name-derived secrets")
                   for name in grants]
        fabric = CapabilityFabric({"native": (granted, grants)})
        expanded = fabric.overview(include_search_facets=True)
        self.assertNotIn("import", expanded["host_granted_search_terms"])
        self.assertIn("import", expanded["host_granted_action_prefixes"])
        self.assertIn("save", expanded["host_granted_action_prefixes"])
        self.assertIn("get", expanded["host_granted_action_prefixes"])
        self.assertFalse(expanded["action_prefixes_may_be_incomplete"])
        self.assertLessEqual(len(json.dumps(expanded).encode("utf-8")), 900)
        self.assertEqual(fabric.overview().get("host_granted_action_prefixes"),
                         None)
        self.assertEqual(fabric.search("import_asset_from_path")["matches"][0]["id"],
                         "native/import_asset_from_path")

    def test_host_action_facets_are_budgeted_and_cannot_reveal_ungranted_names(self):
        candidates = [tool("action"+str(i)+"_"+"x"*24)
                      for i in range(72)]
        grants = {x.name: "write" for x in candidates}
        hidden = tool("secret_ungranted_wipe_everything")
        fabric = CapabilityFabric({"native": (candidates+[hidden], grants)})
        overview = fabric.overview(include_search_facets=True)
        self.assertLessEqual(len(json.dumps(overview).encode("utf-8")), 900)
        self.assertNotIn("secret", json.dumps(overview))
        self.assertLessEqual(len(overview["host_granted_action_prefixes"]), 32)
        self.assertTrue(overview["action_prefixes_may_be_incomplete"])
        self.assertEqual(overview["host_granted_action_prefixes"],
                         fabric.overview(include_search_facets=True)
                         ["host_granted_action_prefixes"])

    def test_unicode_tool_names_do_not_expand_escaped_host_overview_budget(self):
        # Default JSON escaping can turn one Unicode letter into six bytes.
        # No amount of invented model text grants extra output or tool rights.
        items = [tool("関数" + chr(0x4e00 + i) + "_表示") for i in range(35)]
        fabric = CapabilityFabric({"native": (
            items, {item.name: "read" for item in items})})
        overview = fabric.overview(include_search_facets=True)
        self.assertLessEqual(len(json.dumps(overview).encode("utf-8")), 900)
        self.assertEqual(fabric.overview().get("host_granted_action_prefixes"),
                         None)

    def test_only_actual_installed_and_host_granted_apis_can_be_exposed(self):
        f = CapabilityFabric({
            "video": ([tool("open_project", "Open real native project"),
                       tool("delete_entire_project", "Destructive project deletion")],
                      {"open_project": "write"}),
        })
        self.assertEqual(f.count, 1)
        self.assertEqual(f.search("delete")["matches"], [])
        with self.assertRaisesRegex(CapabilityContractError, "Unknown or ungranted"):
            f.describe("video/delete_entire_project", revision=f.revision)

    def test_catalog_identity_changes_when_tools_or_permissions_change(self):
        old = CapabilityFabric({"video": ([tool("export_media", "Export final film",
                                            {"format": {"type": "string"}})],
                                         {"export_media": "write"})})
        updated = CapabilityFabric({"video": ([tool("export_media", "Export final film",
                                            {"format": {"type": "number"}}),
                                              tool("new_effect", "Color effect")],
                                             {"export_media": "read",
                                              "new_effect": "write"})})
        self.assertNotEqual(old.revision, updated.revision)
        self.assertEqual(updated.search("new effect")["matches"][0]["id"],
                         "video/new_effect")
        with self.assertRaisesRegex(CapabilityContractError, "Stale"):
            updated.describe("video/export_media", revision=old.revision)
        with self.assertRaisesRegex(CapabilityContractError, "Stale"):
            updated.resolve("video/export_media", revision=old.revision)

    def test_1000_tool_catalog_is_only_short_result_not_1000_md_pages(self):
        tools = [tool(f"operation_{i:04d}", f"Color grade and geometry control {i}",
                      {f"native_value_{i}": {"type": "number"}})
                 for i in range(1000)]
        fabric = CapabilityFabric({"future": (tools, {t.name: "write" for t in tools})})
        self.assertEqual(fabric.count, 1000)
        overview = json.dumps(fabric.overview(), separators=(",", ":"))
        self.assertLess(len(overview), 220)
        result = fabric.search("color grade", limit=6)
        self.assertEqual(result["matches"], [])
        self.assertTrue(result["requires_refinement"])
        self.assertEqual(len(result["candidate_examples"]), 6)
        self.assertTrue(result["has_more"])
        self.assertLess(len(json.dumps(result)), 1600)
        self.assertEqual(result, fabric.search("color grade", limit=6))

    def test_ambiguous_create_intent_never_licenses_arbitrary_native_write(self):
        ops = [
            tool("create_asset_folder", "Create editor asset-panel folder"),
            tool("create_project", "Create actual editable native project"),
            tool("create_timeline", "Create timeline within existing project"),
        ]
        fabric = CapabilityFabric({"video": (ops, {t.name: "write" for t in ops})})
        broad = fabric.search("create", limit=1)
        self.assertTrue(broad["requires_refinement"])
        self.assertEqual(broad["matches"], [])
        self.assertIn("video/create_project",
                      [x["id"] for x in broad["candidate_examples"]])
        precise = fabric.search("create project", limit=3)
        self.assertFalse(precise["requires_refinement"])
        self.assertEqual(precise["matches"][0]["id"], "video/create_project")

    def test_exact_identity_unblocks_real_2b_project_creation_without_unsafe_ties(self):
        # Actual 2026-10-30 Qwen3.5-2B trial searched create_project four
        # times; lexical tie refusal returned zero invokable matches despite
        # the exact granted ID being available in the earlier host frontier.
        ops = [
            tool("create_project", "Preview or create a new Velorn project"),
            tool("create_project_checkpoint", "Create in-memory project checkpoint"),
            tool("create_timeline", "Create an editable project timeline"),
            tool("open_project", "Open the project"),
            tool("get_project", "Inspect existing project state"),
        ]
        fabric = CapabilityFabric({"native": (
            ops, {entry.name: ("read" if entry.name == "get_project" else "write")
                  for entry in ops})})
        for query in ("create_project", "native/create_project", " create_project "):
            result = fabric.search(query, limit=1)
            self.assertEqual(result["candidates_examined"], 1)
            self.assertFalse(result["requires_refinement"])
            self.assertFalse(result["has_more"])
            self.assertEqual([m["id"] for m in result["matches"]],
                             ["native/create_project"])
            self.assertEqual(fabric.describe("native/create_project",
                             revision=result["revision"])["access"], "write")
        self.assertEqual(fabric.search("unknown_tool_id", limit=1)["matches"], [])
        broad = fabric.search("create", limit=1)
        self.assertTrue(broad["requires_refinement"])
        self.assertEqual(broad["matches"], [])
        self.assertGreaterEqual(len(broad["candidate_examples"]), 2)

    def test_opaque_exact_host_ids_do_not_require_lexical_tokens(self):
        fabric = CapabilityFabric({"native": (
            [tool("__", "Explicitly granted opaque native action")],
            {"__": "read"})})
        self.assertEqual([x["id"] for x in fabric.search("__")["matches"]],
                         ["native/__"])
        self.assertEqual(fabric.search("native/__", limit=1)["candidates_examined"], 1)
        with self.assertRaisesRegex(CapabilityContractError, "searchable terms"):
            fabric.search("??")

    def test_exact_name_collision_requires_namespace_or_multiple_visible_choices(self):
        f = CapabilityFabric({
            "video": ([tool("render", "Native video export")], {"render": "write"}),
            "motion": ([tool("render", "Native motion export")], {"render": "write"}),
        })
        ambiguous = f.search("render", limit=1)
        self.assertTrue(ambiguous["requires_refinement"])
        self.assertEqual(ambiguous["matches"], [])
        self.assertEqual(ambiguous["candidates_examined"], 2)
        explicit = f.search("motion/render", limit=1)
        self.assertEqual([r["id"] for r in explicit["matches"]], ["motion/render"])
        self.assertEqual(explicit["candidates_examined"], 1)
        all_matches = f.search("render", limit=2)
        self.assertEqual({r["id"] for r in all_matches["matches"]},
                         {"motion/render", "video/render"})
        self.assertFalse(all_matches["requires_refinement"])

    def test_sparse_specialist_search_examines_only_host_granted_postings(self):
        ops = [tool(f"job_{i:04d}",
               "Render original visual composition" if i != 911
               else "Rare specialist prismaster glow treatment")
               for i in range(1000)]
        fabric = CapabilityFabric({"graphics": (
            ops, {t.name: "write" for t in ops})})
        focused = fabric.search("prismaster", limit=1)
        self.assertEqual(focused["candidates_examined"], 1)
        self.assertEqual(focused["matches"][0]["id"], "graphics/job_0911")
        self.assertLess(len(json.dumps(focused)), 800)
        common = fabric.search("render", limit=6)
        self.assertEqual(common["candidates_examined"], 999)
        self.assertTrue(common["requires_refinement"])
        self.assertEqual(common["matches"], [])
        self.assertEqual(common, fabric.search("render", limit=6))

    def test_collision_and_ambiguous_source_are_rejected(self):
        with self.assertRaisesRegex(CapabilityContractError, "Duplicate"):
            CapabilityFabric({"a": ([tool("same"), tool("same")], {"same": "read"})})
        with self.assertRaisesRegex(CapabilityContractError, "Source"):
            CapabilityFabric({"../host": ([tool("read")], {"read": "read"})})

    def test_same_tool_name_in_separate_engines_is_not_ambiguous(self):
        f = CapabilityFabric({"video": ([tool("render", "Render movie")],
                                      {"render": "write"}),
                              "vector": ([tool("render", "Render vector image")],
                                         {"render": "write"})})
        self.assertEqual(f.count, 2)
        ids = [r["id"] for r in f.search("render", limit=8)["matches"]]
        self.assertEqual(set(ids), {"video/render", "vector/render"})

    def test_fail_closed_on_invented_ids_stale_revisions_and_untrusted_schema(self):
        f = CapabilityFabric({"video": ([tool("timeline", "Inspect current edit")],
                                      {"timeline": "read"})})
        for ident, rev in (("shell_exec", f.revision),
                           ("video/fake", f.revision),
                           ("video/timeline", "f" * 64)):
            with self.subTest(ident=ident):
                with self.assertRaises(CapabilityContractError):
                    f.resolve(ident, revision=rev)
        with self.assertRaisesRegex(CapabilityContractError, "schema"):
            CapabilityFabric({"video": ([
                SimpleNamespace(name="bad", description="Bad",
                                input_schema={"type": "object", "x": object()})],
                {"bad": "read"})})

    def test_bounded_query_and_exact_parameter_names(self):
        f = CapabilityFabric({"visual": ([tool("complex_design",
            "Advanced arbitrary color composition", {f"p{i}": {"type": "number"}
                                                    for i in range(50)})],
            {"complex_design": "write"})})
        params = f.search("composition")["matches"][0]["parameters_sample"]
        self.assertEqual(params, [f"p{i}" for i in range(6)])
        with self.assertRaisesRegex(CapabilityContractError, "bounded"):
            f.search("composition " * 30)
        with self.assertRaisesRegex(CapabilityContractError, "bounded"):
            f.search("visual", limit=100)

    def test_giant_schema_uses_explicit_safe_refusal_not_a_truncated_abi(self):
        f = CapabilityFabric({"video": ([tool("deep_fx", "Native transform",
            {"expression": {"type": "string", "description": "x" * 25000}})],
            {"deep_fx": "write"})})
        result = f.describe("video/deep_fx", revision=f.revision)
        self.assertTrue(result["schema_too_large"])
        self.assertNotIn("input_schema", result)

    def test_unicode_and_source_catalog_determinism(self):
        entry = tool("add_title", "हिन्दी शीर्षक बनाएं")
        f = CapabilityFabric({"video": ([entry], {"add_title": "write"})})
        g = CapabilityFabric({"video": ([entry], {"add_title": "write"})})
        self.assertEqual(f.revision, g.revision)
        self.assertEqual(f.search("शीर्षक")["matches"][0]["id"],
                         "video/add_title")


    def test_explicit_trusted_state_preconditions_not_model_guessing(self):
        sources = {"motion": ([tool("create_motion", "Create keyframe animation"),
                               tool("render_animation", "Render animation output")],
                              {"create_motion": "write", "render_animation": "write"},
                              {"render_animation": ["project_open", "assets_cleared"]})}
        f = CapabilityFabric(sources)
        entry = f.search("render animation")["matches"][0]
        self.assertEqual(entry["requires"], ["project_open", "assets_cleared"])
        status = f.check_prerequisites(entry["id"], revision=f.revision,
                                      trusted_facts={"project_open": False})
        self.assertFalse(status["admissible"])
        self.assertEqual(status["unsatisfied"], ["project_open"])
        self.assertEqual(status["unknown_state"], ["assets_cleared"])
        approved = f.check_prerequisites(entry["id"], revision=f.revision,
            trusted_facts={"project_open": True, "assets_cleared": True})
        self.assertTrue(approved["admissible"])
        changed = CapabilityFabric({"motion": (sources["motion"][0],
            sources["motion"][1], {"render_animation": ["project_open"]})})
        self.assertNotEqual(changed.revision, f.revision)

    def test_untrusted_or_invalid_precondition_metadata_fails_closed(self):
        operations = [tool("export", "Export movie")]
        grants = {"export": "write"}
        for bad in ({"export": [["fake"]]}, {"export": ["project_open", "project_open"]},
                    {"export": ["not a fact"]}, {"unknown": ["project_open"]}):
            with self.subTest(value=bad), self.assertRaises(CapabilityContractError):
                CapabilityFabric({"video": (operations, grants, bad)})
        f = CapabilityFabric({"video": (operations, grants, {"export": ["project_open"]})})
        for facts in ({"project_open": "yes"}, {"project_open": 1}, [True]):
            with self.subTest(facts=facts), self.assertRaises(CapabilityContractError):
                f.check_prerequisites("video/export", revision=f.revision, trusted_facts=facts)

    def test_tool_schema_snapshot_does_not_mutate_if_source_or_brain_changes_it(self):
        properties = {"name": {"type": "string"}}
        native = tool("create", "Make project", properties)
        fabric = CapabilityFabric({"video": ([native], {"create": "write"})})
        revision = fabric.revision
        properties["name"]["type"] = "number"
        one = fabric.describe("video/create", revision=revision)
        self.assertEqual(one["input_schema"]["properties"]["name"]["type"], "string")
        one["input_schema"]["properties"]["name"]["type"] = "integer"
        again = fabric.describe("video/create", revision=revision)
        self.assertEqual(again["input_schema"]["properties"]["name"]["type"], "string")
        self.assertEqual(fabric.revision, revision)


class LiveMachineDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_software_operation_is_seen_from_real_live_discovery_next_refresh(self):
        class Machine:
            def __init__(self):
                self.tools = [tool("create_project", "Create actual native project")]
            async def list_tools(self):
                return SimpleNamespace(tools=self.tools, nextCursor=None)
        session = Machine()
        binding = {"video": (session, {"create_project": "write"})}
        before = await CapabilityFabric.from_connections(binding)
        self.assertEqual(before.count, 1)
        session.tools.append(tool("new_vector_effect", "Vector graphic motion effect"))
        binding["video"] = (session, {"create_project": "write",
                                     "new_vector_effect": "write"})
        after = await CapabilityFabric.from_connections(binding)
        self.assertEqual(after.count, 2)
        self.assertNotEqual(after.revision, before.revision)
        self.assertEqual(after.search("graphic motion")["matches"][0]["id"],
                         "video/new_vector_effect")
        with self.assertRaisesRegex(CapabilityContractError, "Stale"):
            after.describe("video/create_project", revision=before.revision)

    async def test_complete_cursor_paged_catalog_supports_late_future_capability(self):
        class Paged:
            async def list_tools(self, *, cursor=None):
                if cursor is None:
                    return SimpleNamespace(tools=[tool("first", "Native render")],
                                           nextCursor="opaque-stage-1")
                if cursor == "opaque-stage-1":
                    return SimpleNamespace(tools=[tool("future_fx", "Native future VFX")],
                                           nextCursor=None)
                raise AssertionError("Caller invented a cursor")
        state = await CapabilityFabric.from_connections({
            "video": (Paged(), {"first": "read", "future_fx": "write"})})
        self.assertEqual(state.count, 2)
        self.assertEqual(state.search("future VFX")["matches"][0]["id"], "video/future_fx")

    async def test_versioned_mcp_json_rpc_pages_are_complete_before_discovery(self):
        """A newer MCP wrapper and an opaque cursor must coexist."""
        seen = []
        class Versioned:
            async def list_tools(self, *, cursor=None):
                seen.append(cursor)
                if cursor is None:
                    return {"jsonrpc": "2.0", "id": 1, "result": {
                        "resultType": "complete",
                        "tools": [tool("first", "Initial video tool")],
                        "nextCursor": "opaque-v2"}}
                if cursor == "opaque-v2":
                    return {"jsonrpc": "2.0", "id": 2, "result": {
                        "resultType": "complete",
                        "tools": [tool("future_glow", "Specialized native glow VFX")]}}
                raise AssertionError("MCP cursor was fabricated")
        fabric = await CapabilityFabric.from_connections({
            "vfx": (Versioned(), {
                "first": "read", "future_glow": "write"})})
        self.assertEqual(seen, [None, "opaque-v2"])
        self.assertEqual(fabric.count, 2)
        self.assertEqual(
            fabric.search("specialized glow")["matches"][0]["id"],
            "vfx/future_glow")

    async def test_versioned_partial_errors_and_malformed_results_never_admit_tools(self):
        class Response:
            def __init__(self, payload):
                self.payload = payload
            async def list_tools(self):
                return self.payload
        unsafe = [
            {"result": {"resultType": "input_required",
                        "tools": [tool("write")]}},
            {"result": {"resultType": "progress",
                        "tools": [tool("write")]}},
            {"error": {"code": -32603, "message": "not ready"},
             "result": {"resultType": "complete", "tools": [tool("write")]}},
            {"result": {"resultType": "complete", "tools": "not a list"}},
            {"result": None, "tools": [tool("write")]},
        ]
        for payload in unsafe:
            with self.subTest(payload=str(payload)[:90]):
                with self.assertRaises(CapabilityContractError):
                    await CapabilityFabric.from_connections({
                        "vfx": (Response(payload), {"write": "write"})})

    async def test_cursorless_adapter_and_repeated_cursor_fail_closed(self):
        class NonPaging:
            async def list_tools(self):
                return SimpleNamespace(tools=[tool("first")], nextCursor="next")
        class Cycling:
            async def list_tools(self, *, cursor=None):
                return SimpleNamespace(tools=[tool("first")], nextCursor="same-token")
        for session in (NonPaging(), Cycling()):
            with self.subTest(session=type(session).__name__), self.assertRaises(
                CapabilityContractError):
                await CapabilityFabric.from_connections({
                    "video": (session, {"first": "read"})})

    async def test_large_paged_catalog_rejects_unbounded_page_stream(self):
        class Giant:
            async def list_tools(self, *, cursor=None):
                return SimpleNamespace(tools=[
                    tool(f"tool_{cursor or 0}_{i}") for i in range(3000)],
                    nextCursor="next" if cursor is None else None)
        with self.assertRaisesRegex(CapabilityContractError, "budget"):
            await CapabilityFabric.from_connections({
                "video": (Giant(), {})})



    def test_trusted_machine_effect_frontier_is_cross_domain_and_not_autoplay(self):
        photo = [tool("new_canvas", "Create a layered original photo canvas"),
                 tool("paint", "Paint pixels on an editable canvas")]
        motion = [tool("new_scene", "Create a 3D animation scene"),
                  tool("keyframe", "Animate native object motion")]
        f = CapabilityFabric({
            "photo": (photo, {"new_canvas": "write", "paint": "write"},
                      {"paint": ["document_open"]},
                      {"new_canvas": ["document_open"]}),
            "motion": (motion, {"new_scene": "write", "keyframe": "write"},
                       {"keyframe": ["document_open"]},
                       {"new_scene": ["document_open"]}),
        })
        possible = f.affordance_frontier(trusted_facts={"document_open": False},
                                        namespace="motion")
        self.assertEqual([x["id"] for x in possible["matches"]],
                         ["motion/new_scene"])
        self.assertTrue(possible["effects_are_possibilities_not_verified_results"])
        self.assertTrue(possible["facts_are_host_attested"])
        self.assertFalse(any("keyframe" in x["id"] for x in possible["matches"]))
        self.assertEqual(f.affordance_frontier(
            trusted_facts={"document_open": True})["matches"], [])

    def test_future_effect_contracts_are_versioned_and_untrusted_claims_rejected(self):
        ops = [tool("make", "Make editable project")]
        grants = {"make": "write"}
        before = CapabilityFabric({"graphics": (ops, grants)})
        after = CapabilityFabric({"graphics": (
            ops, grants, {}, {"make": ["project_open"]})})
        self.assertNotEqual(before.revision, after.revision)
        for effects in ({"missing": ["project_open"]},
                        {"make": ["not a valid fact"]},
                        {"make": ["project_open", "project_open"]},
                        {"make": [["not_a_string"]]}):
            with self.subTest(effects=effects), self.assertRaises(CapabilityContractError):
                CapabilityFabric({"graphics": (ops, grants, {}, effects)})


if __name__ == "__main__":
    unittest.main()

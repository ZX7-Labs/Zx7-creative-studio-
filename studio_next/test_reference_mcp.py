"""Actual official MCP protocol test for host-granted video reference study."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

HAS_MCP = importlib.util.find_spec("mcp") is not None
if HAS_MCP:
    import anyio
    from mcp import ClientSession
    from mcp.shared.memory import create_client_server_memory_streams
    from .creative_research_mcp import create_research_server


@unittest.skipUnless(HAS_MCP, "Install the research extra for official MCP transport")
class ReferenceMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_media_graph_authority_and_offline_permissions(self):
        with tempfile.TemporaryDirectory() as location:
            root = Path(location)
            movie = root / "sample.mp4"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "testsrc2=s=128x72:r=24:d=2",
                "-f", "lavfi", "-i", "sine=frequency=220:duration=2",
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "libx264", "-c:a", "aac", str(movie)],
                check=True, timeout=35)
            server = create_research_server(
                allow_public_research=False, reference_root=root,
                memory_path=root / "case-memory.sqlite3")
            async with create_client_server_memory_streams() as (client, host):
                async with anyio.create_task_group() as group:
                    group.start_soon(server.run, *host,
                                     server.create_initialization_options())
                    async with ClientSession(*client) as session:
                        await session.initialize()
                        names = [x.name for x in (await session.list_tools()).tools]
                        self.assertEqual(names, [
                            "observe_authorized_reference",
                            "detect_authorized_reference_shots",
                            "study_authorized_reference",
                            "recall_reference_case",
                            "recent_reference_cases",
                            "compare_reference_cases"])
                        result = await session.call_tool(
                            "observe_authorized_reference",
                            {"reference": "sample.mp4", "bins": 16})
                        self.assertFalse(result.is_error)
                        graph = json.loads(result.content[0].text)
                        self.assertEqual(len(graph["graph"]), 16)
                        self.assertTrue(graph["has_audio"])
                        self.assertFalse(graph["original_video_bytes_retained"])
                        shot_info = await session.call_tool(
                            "detect_authorized_reference_shots",
                            {"reference":"sample.mp4","method":"content"})
                        self.assertFalse(shot_info.is_error)
                        real_shots = json.loads(shot_info.content[0].text)
                        self.assertEqual(real_shots["library"], "PySceneDetect")
                        self.assertGreaterEqual(len(real_shots["shot_intervals"]), 1)
                        self.assertFalse(real_shots["creative_quality_certified"])
                        for bad in ({"reference":"../private.mp4"},
                                    {"reference":"/etc/passwd"},
                                    {"reference":"sample.mp4","bins":999}):
                            denied = await session.call_tool(
                                "observe_authorized_reference",bad)
                            self.assertTrue(denied.is_error)
                        studied = await session.call_tool(
                            "study_authorized_reference",
                            {"reference":"sample.mp4","bins":16})
                        self.assertFalse(studied.is_error)
                        identity = json.loads(studied.content[0].text)["id"]
                        repeated = await session.call_tool(
                            "study_authorized_reference",
                            {"reference":"sample.mp4","bins":16})
                        self.assertTrue(json.loads(
                            repeated.content[0].text)["deduplicated"])
                        recalled = await session.call_tool(
                            "recall_reference_case", {"id":identity})
                        self.assertFalse(recalled.is_error)
                        self.assertTrue(json.loads(recalled.content[0].text)["found"])
                        recent = await session.call_tool(
                            "recent_reference_cases", {"limit":10})
                        self.assertEqual(len(json.loads(
                            recent.content[0].text)["records"]), 1)
                        measured = await session.call_tool(
                            "compare_reference_cases",
                            {"first_id":identity, "second_id":identity})
                        self.assertFalse(measured.is_error)
                        comparison = json.loads(measured.content[0].text)
                        self.assertEqual(comparison["first_observed"],
                                         comparison["second_observed"])
                        self.assertTrue(comparison[
                            "comparison_is_not_aesthetic_quality_score"])
                        denied_compare = await session.call_tool(
                            "compare_reference_cases",
                            {"first_id": identity, "second_id":"f"*64})
                        self.assertTrue(denied_compare.is_error)
                        denied_study = await session.call_tool(
                            "study_authorized_reference", {"reference":"../private.mp4"})
                        self.assertTrue(denied_study.is_error)
                        denied = await session.call_tool("research_creative", {"query":"x"})
                        self.assertTrue(denied.is_error)
                    group.cancel_scope.cancel()


if __name__ == "__main__":
    unittest.main()

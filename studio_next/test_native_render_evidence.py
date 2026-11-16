"""The A/V release gate must keep review and revision on the same renders."""
import unittest

from studio_next.native_render_evidence import (
    reviewed_render_pair, reviewed_native_snapshot_hashes, reviewed_native_media_hashes)


class ReviewedAVPairTests(unittest.TestCase):
    def events(self):
        def write(tool, **fields):
            return dict(kind="native_tool_result", tool=tool,
                        host_application_write_acknowledged=True, **fields)

        def render(path, digest, images):
            scope = {"native_export_destination_sha256": path}
            def read(tool, **fields):
                return dict(kind="native_tool_result", tool=tool, **scope, **fields)
            return [
                write("export_timeline", native_export_timeline_sha256="timeline", **scope),
                read("zx7_verify_native_export", independently_verified_export_sha256=digest,
                     native_av_review=[6]),
                read("zx7_observe_verified_export_samples", observed_export_sha256=digest,
                     image_sha256=images, native_av_review=[1, 4]),
                read("zx7_observe_verified_export_audio_timeline", observed_export_sha256=digest,
                     native_av_review=[0, 6], native_av_pcm_sha256="c" * 64),
            ]

        return (render("before", "a" * 64, ["a", "b"]) +
                [write("update_text_clip")] + render("after", "b" * 64, ["d", "b"]))

    def test_container_only_change_does_not_prove_audiovisual_revision(self):
        events = self.events()
        revisions = {"update_text_clip"}
        events[7]["image_sha256"] = events[2]["image_sha256"]
        self.assertIsNone(reviewed_render_pair(events, revisions, audiovisual=True))
        self.assertIsNotNone(reviewed_render_pair(events, revisions))

        events[7]["native_av_review"] = [0.5, 3.5]
        events[7]["image_sha256"] = ["e", "f"]
        self.assertIsNone(reviewed_render_pair(events, revisions, audiovisual=True))

        events[8]["native_av_pcm_sha256"] = "d" * 64
        self.assertIsNotNone(reviewed_render_pair(events, revisions, audiovisual=True))

    def test_both_exports_require_matching_timed_picture_and_audio(self):
        events = self.events()
        revisions = {"update_text_clip"}
        self.assertEqual(len(reviewed_render_pair(events, revisions, audiovisual=True)), 2)
        for index, overrides in (
            (3, {"native_av_review": None}),
            (3, {"native_av_review": [0, 0.25]}),
            (3, {"native_export_destination_sha256": "other"}),
            (3, {"observed_export_sha256": "b" * 64}),
            (2, {"native_av_review": [1, 1.01]}),
            (7, {"tool": "zx7_observe_verified_export_frame", "native_av_review": None}),
            (8, {"kind": "native_read_tool_reported_error"}),
        ):
            with self.subTest(index=index, overrides=overrides):
                changed = [dict(event) for event in events]
                changed[index].update(overrides)
                self.assertIsNone(reviewed_render_pair(changed, revisions, audiovisual=True))
                self.assertIsNotNone(reviewed_render_pair(changed, revisions))

    def test_a_failed_later_audio_read_revokes_a_previously_complete_pair(self):
        events = self.events()
        events.append({**events[-1], "kind": "native_read_tool_reported_error"})
        self.assertIsNone(reviewed_render_pair(events, {"update_text_clip"}, audiovisual=True))


class RenderTimeNativeSourceCustodyTests(unittest.TestCase):
    """Only host-observed render receipts may identify the paired saved sources."""

    def setUp(self):
        self.pair = [
            {"destination_sha256": "1" * 64, "export_sha256": "a" * 64,
             "timeline_sha256": "f" * 64},
            {"destination_sha256": "2" * 64, "export_sha256": "b" * 64,
             "timeline_sha256": "f" * 64},
        ]
        self.events = [
            {"kind": "native_tool_result", "tool": "export_timeline",
             "host_application_write_acknowledged": True,
             "native_export_destination_sha256": b["destination_sha256"],
             "native_export_timeline_sha256": b["timeline_sha256"],
             "native_render_saved_project_sha256": digest,
             "native_render_options_sha256": "e" * 64,
             "native_render_media_sha256": "6" * 64}
            for b, digest in zip(self.pair, ("3" * 64, "4" * 64), strict=True)
        ]

    def test_exact_original_and_revised_native_snapshot_digests_are_returned(self):
        self.assertEqual(
            reviewed_native_snapshot_hashes(self.events, self.pair),
            ["3" * 64, "4" * 64])

    def test_media_digests_for_exact_original_and_revised_native_renders(self):
        self.assertEqual(reviewed_native_media_hashes(self.events, self.pair),
                         ["6" * 64, "6" * 64])
        for candidate in (None, "not-a-sha", "x" * 64):
            with self.subTest(candidate=candidate):
                changed = [dict(event) for event in self.events]
                changed[1]["native_render_media_sha256"] = candidate
                self.assertIsNone(reviewed_native_media_hashes(changed, self.pair))
        after = dict(self.events[0])
        after.pop("native_render_media_sha256")
        self.assertIsNone(reviewed_native_media_hashes(self.events + [after], self.pair))

    def test_missing_or_forged_render_capture_fails_closed(self):
        self.assertIsNone(reviewed_native_snapshot_hashes(self.events[:-1], self.pair))
        for field, changed in (
            ("native_export_timeline_sha256", "5" * 64),
            ("native_render_saved_project_sha256", None),
            ("native_render_saved_project_sha256", "bad"),
            ("native_render_options_sha256", None),
            ("host_application_write_acknowledged", False),
        ):
            with self.subTest(field=field):
                altered = [dict(event) for event in self.events]
                altered[0][field] = changed
                self.assertIsNone(reviewed_native_snapshot_hashes(altered, self.pair))
        forged = [dict(e) for e in self.events]
        forged[1]["native_render_saved_project_sha256"] = "3" * 64
        self.assertIsNone(reviewed_native_snapshot_hashes(forged, self.pair))

    def test_later_render_without_host_source_receipt_invalidates_old_snapshot(self):
        after = dict(self.events[0])
        after.pop("native_render_saved_project_sha256")
        self.assertIsNone(
            reviewed_native_snapshot_hashes(self.events + [after], self.pair))

    def test_wrong_pair_shape_is_not_treated_as_success(self):
        for pair in (None, [], self.pair[:1],
                     [{**self.pair[0], "timeline_sha256": "9" * 64}, self.pair[1]],
                     [{**self.pair[0], "destination_sha256": "missing"}, self.pair[1]]):
            with self.subTest(pair=pair):
                self.assertIsNone(reviewed_native_snapshot_hashes(self.events, pair))

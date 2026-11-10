"""The A/V release gate must keep review and revision on the same renders."""
import unittest

from studio_next.native_render_evidence import reviewed_render_pair


class ReviewedAVPairTests(unittest.TestCase):
    def events(self):
        def write(tool, **fields):
            return dict(kind="native_tool_result", tool=tool,
                        host_application_write_acknowledged=True, **fields)

        def render(path, digest):
            scope = {"native_export_destination_sha256": path}
            def read(tool, **fields):
                return dict(kind="native_tool_result", tool=tool, **scope, **fields)
            return [
                write("export_timeline", native_export_timeline_sha256="timeline", **scope),
                read("zx7_verify_native_export", independently_verified_export_sha256=digest,
                     native_av_review=[6]),
                read("zx7_observe_verified_export_samples", observed_export_sha256=digest,
                     image_sha256=["a", "b"], native_av_review=[1, 4]),
                read("zx7_observe_verified_export_audio_timeline", observed_export_sha256=digest,
                     native_av_review=[0, 6]),
            ]

        return render("before", "a" * 64) + [write("update_text_clip")] + render("after", "b" * 64)

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

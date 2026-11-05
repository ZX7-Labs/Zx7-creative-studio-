"""Contract: seed camera pixels never masquerade as verified exported frames."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from PIL import Image
from scripts.run_native_model_trial import RecordedModel


class RecordingTransportFixture:
    """Non-neural fixture: only proves image routing, never creative competence."""
    def __init__(self):
        self.settings = SimpleNamespace(sampling={})
        self.last_call_usage = {"fixture_only": True}
        self.picture_calls = 0
        self.text_calls = 0
        self.observed = []

    def decide_with_images(self, context, images):
        self.picture_calls += 1
        self.observed.extend(images)
        return {"action": "discover", "arguments": {}, "reason": "transport fixture"}

    def decide(self, context):
        self.text_calls += 1
        return {"action": "discover", "arguments": {}, "reason": "transport fixture"}


class NativeOriginalEvidenceTests(unittest.TestCase):
    def test_initial_source_image_is_not_post_edit_observation(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source_picture = root / "camera.png"
            Image.new("RGB", (4, 4), (75, 60, 50)).save(source_picture)
            transport = RecordingTransportFixture()
            model = RecordedModel(
                transport, root, initial_source_picture=source_picture)
            context = {"actual_granted_native_tools": ["get_project"]}
            model.decide(context)
            model.decide(context)
            self.assertEqual(transport.picture_calls, 1)
            self.assertEqual(transport.text_calls, 1)
            self.assertEqual(hashlib.sha256(transport.observed[0][1]).hexdigest(),
                             hashlib.sha256(source_picture.read_bytes()).hexdigest())
            self.assertEqual(len(list((root / "source-observations").glob("*.png"))), 1)
            self.assertFalse((root / "observations").exists())
            records = [json.loads(s) for s in
                       (root / "inference-transcript.jsonl").read_text().splitlines()]
            self.assertEqual(len(records), 2)
            self.assertEqual(len(records[0]["image_sha256"]), 1)
            self.assertEqual(len(records[1]["image_sha256"]), 0)


if __name__ == "__main__":
    unittest.main()

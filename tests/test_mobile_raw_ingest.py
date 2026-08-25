import json
import tempfile
import unittest
from pathlib import Path

from scripts.pmbrs_host_sync_ingest import persist_sync_batch


class MobileRawIngestTest(unittest.TestCase):
    def test_persist_sync_batch_writes_mobile_payloads(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            batch = [
                {
                    "artifactId": "mobile-abc-123",
                    "source": "mobile",
                    "payload": {"device": "pixel-7", "app": "pmbrs"},
                    "createdAtEpochMs": 1720000000000,
                    "schemaVersion": "1.0",
                    "deviceAlias": "test-phone",
                    "provenanceMetadataJson": json.dumps({"source": "mobile"}),
                }
            ]

            written = persist_sync_batch(root, batch)

            self.assertEqual(len(written), 1)
            saved = written[0]
            self.assertEqual(saved.parent, root / "mobile")
            article = json.loads(saved.read_text(encoding="utf-8"))
            self.assertEqual(article["artifactId"], "mobile-abc-123")
            self.assertEqual(article["source"], "mobile")
            self.assertEqual(article["payload"]["device"], "pixel-7")


if __name__ == "__main__":
    unittest.main()

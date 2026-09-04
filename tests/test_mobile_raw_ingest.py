import json
import tempfile
import unittest
from pathlib import Path

from scripts.pmbrs_host_sync_ingest import _handle_phone_sync, persist_sync_batch


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

    def test_handle_phone_sync_returns_synced_ids_for_phone_ack(self):
        # Regression test — PMBRSSyncWorker artifact-path NPE (2026-09-03).
        #
        # The phone deserializes the 200 body into SyncResponse(syncedIds:
        # List<String>) and calls syncedIds.isNotEmpty() inside the sync
        # worker. If this handler omits the "syncedIds" key (as it did
        # before the fix), Gson sets the field to null and the phone NPEs:
        #   "Attempt to invoke interface method
        #    boolean java.util.Collection.isEmpty() on a null object reference"
        # — mislabelled as a NetworkFailure and retried 3x per run (logcat
        # 22:46:25.926). The wearable + boox routes both include syncedIds;
        # the artifact route must too, or the phone can't call
        # markSyncedByArtifactId and the batch retries forever.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            batch = [
                {
                    "artifactId": "mobile-ack-1",
                    "source": "mobile",
                    "payload": {"kind": "screen_state"},
                    "createdAtEpochMs": 1720000000000,
                    "deviceAlias": "test-phone",
                },
                {
                    "artifactId": "mobile-ack-2",
                    "source": "mobile",
                    "payload": {"kind": "wearable"},
                    "createdAtEpochMs": 1720000000001,
                    "deviceAlias": "test-phone",
                },
            ]
            body = {"artifacts": batch}

            resp = _handle_phone_sync(root, body)

            # All artifacts accepted and persisted.
            self.assertEqual(resp["accepted"], 2, resp)
            # The ack contract the phone relies on (markSyncedByArtifactId).
            self.assertIn("syncedIds", resp, msg=f"handler response missing syncedIds: {resp}")
            self.assertEqual(resp["syncedIds"], ["mobile-ack-1", "mobile-ack-2"])
            # Also present in the "accepted" list so the client gets both shapes.
            self.assertEqual(len(resp["storedFiles"]), 2)


if __name__ == "__main__":
    unittest.main()

"""Tests for the P0 evidence index."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from tools.evidence.p0_index import load_index, require_complete  # noqa: E402


class EvidenceIndexTests(unittest.TestCase):
    def test_registered_rows_point_to_existing_outputs(self) -> None:
        count = require_complete()
        rows = load_index()
        self.assertEqual(count, len(rows))
        self.assertIn("ATLAS-P0-0014", [row["batch_id"] for row in rows])

    def test_unknown_batch_is_rejected(self) -> None:
        rows = load_index()
        broken = {"batch_id": "ATLAS-P0-9999", "output_path": rows[0]["output_path"], "test_name": "x"}
        from tools.evidence import p0_index

        original = p0_index.load_index
        p0_index.load_index = lambda: (broken,)
        try:
            with self.assertRaises(ContractError) as blocked:
                p0_index.require_complete()
            self.assertEqual(str(blocked.exception), "evidence-batch-unregistered")
        finally:
            p0_index.load_index = original

    def test_missing_registered_test_is_rejected(self) -> None:
        rows = load_index()
        broken = {
            "batch_id": rows[0]["batch_id"],
            "output_path": rows[0]["output_path"],
            "test_name": "internal.contract.test_missing_batch",
        }
        from tools.evidence import p0_index

        original = p0_index.load_index
        p0_index.load_index = lambda: (broken,)
        try:
            with self.assertRaises(ContractError) as blocked:
                p0_index.require_complete()
            self.assertEqual(str(blocked.exception), "evidence-test-missing")
        finally:
            p0_index.load_index = original


if __name__ == "__main__":
    unittest.main()

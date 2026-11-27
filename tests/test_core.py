import unittest

from gtcore_agent.core import (
    Controller,
    PARAMETERS,
    checksum,
    message_dt1,
    message_rq1,
    parse_dt1,
)
from gtcore_agent.server import rules_suggest


class ProtocolTests(unittest.TestCase):
    def test_roland_checksum(self):
        self.assertEqual(checksum((0x10, 0, 0x13, 0x02, 62)), 29)
        self.assertEqual((sum((0x10, 0, 0x13, 0x02, 62)) + checksum((0x10, 0, 0x13, 0x02, 62))) % 128, 0)

    def test_rq1_structure(self):
        payload = message_rq1(0x10, (0x10, 0, 0x13, 0x02), 1)
        self.assertEqual(payload[:7], (0x41, 0x10, 0, 0, 0, 0x4F, 0x11))
        self.assertEqual(payload[7:11], (0x10, 0, 0x13, 0x02))
        self.assertEqual(payload[11:15], (0, 0, 0, 1))
        self.assertEqual(sum(payload[7:]) % 128, 0)

    def test_dt1_read_and_tampered_checksum(self):
        addr = (0x10, 0, 0x13, 0x02)
        payload = message_dt1(0x10, addr, (60,))
        self.assertEqual(parse_dt1(payload, 0x10, addr, 1), (60,))
        self.assertIsNone(parse_dt1(payload, 0x11, addr, 1))
        self.assertIsNone(parse_dt1(payload[:-1] + (99,), 0x10, addr, 1))
        self.assertIsNone(parse_dt1(payload, 0x10, (0x10, 0, 0x13, 0x03), 1))

    def test_eq_offset_and_bounds(self):
        p = PARAMETERS["eq_high"]
        self.assertEqual(p.encode(0), 32)
        self.assertEqual(p.decode(32), 0)
        self.assertEqual(p.encode(-20), 12)
        with self.assertRaises(ValueError):
            p.encode(21)
        with self.assertRaises(ValueError):
            p.encode(True)

    def test_all_write_addresses_only_temporary(self):
        for p in PARAMETERS.values():
            self.assertEqual(p.address[:2], (0x10, 0))


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.c = Controller()
        self.c.read()

    def test_apply_then_undo_demo(self):
        old = self.c.snapshot["amp_middle"]
        result = self.c.new_proposal({"amp_middle": old + 5}, "テスト")
        prop_id = result["proposal"]["id"]
        with self.assertRaises(ValueError):
            self.c.apply(prop_id, False)
        applied = self.c.apply(prop_id, True)
        self.assertEqual(applied["values"]["amp_middle"], old + 5)
        self.assertTrue(applied["undo_available"])
        undone = self.c.revert(True)
        self.assertEqual(undone["values"]["amp_middle"], old)
        self.assertFalse(undone["undo_available"])

    def test_reject_unlisted_or_large_changes(self):
        with self.assertRaises(ValueError):
            self.c.new_proposal({"user_patch_bank": 3}, "no")
        with self.assertRaises(ValueError):
            self.c.new_proposal({"amp_gain": 119}, "too big")

    def test_disallow_stale_hardware_state(self):
        result = self.c.new_proposal({"amp_gain": 60}, "test")
        self.c.transport.values["amp_gain"] = 61
        with self.assertRaisesRegex(ValueError, "本体側のパッチ"):
            self.c.apply(result["proposal"]["id"], True)

    def test_rules_avoid_disabled_blocks(self):
        changes, _ = rules_suggest("9mm 鋭い", self.c.status())
        self.assertNotIn("ds2_drive", changes)
        self.assertIn("amp_middle", changes)


if __name__ == "__main__":
    unittest.main()

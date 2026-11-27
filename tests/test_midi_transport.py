"""In-process MIDI simulator exercises the same SysEx path as a real device.

It validates framing and guarded reads/writes; it is not a physical-device test.
"""

import sys
import types
import unittest
from unittest.mock import patch

from gtcore_agent.core import (
    Controller, MidiTransport, PARAMETERS, SWITCHES, message_dt1,
)


class FakeInput:
    def __init__(self):
        self.pending = []

    def iter_pending(self):
        result, self.pending = self.pending, []
        return iter(result)

    def close(self):
        pass


class FakeOutput:
    def __init__(self, input_port, model_code=0x02):
        self.input = input_port
        self.model_code = model_code
        self.sent = []
        self.memory = {p.address: p.encode(p.low + (p.high-p.low)//2) for p in PARAMETERS.values()}
        self.memory.update({addr: 1 for addr in SWITCHES.values()})
        self.name = b"UNIT TEST PATCH "

    def send(self, msg):
        payload = tuple(msg.data)
        self.sent.append(payload)
        if payload == (0x7E, 0x7F, 0x06, 0x01):
            reply = (0x7E, 0x10, 0x06, 0x02, 0x41, 0x4F, 0x03, 0, 0, self.model_code, 0, 0, 0)
        elif payload[6] == 0x11:
            address = tuple(payload[7:11])
            size = payload[14]
            data = self.name if (address == (0x10, 0, 0, 0) and size == 16) else (self.memory[address],)
            reply = message_dt1(0x10, address, tuple(data))
        elif payload[6] == 0x12:
            address = tuple(payload[7:11])
            if not address[:2] == (0x10, 0):
                raise AssertionError("write was not in temporary patch area")
            self.memory[address] = payload[11]
            return
        else:
            raise AssertionError("unexpected MIDI command")
        self.input.pending.append(types.SimpleNamespace(type="sysex", data=reply))

    def close(self):
        pass


def fake_mido(model_code=0x02):
    input_port = FakeInput()
    output_port = FakeOutput(input_port, model_code=model_code)
    module = types.SimpleNamespace(
        get_input_names=lambda: ["GT-1000CORE MIDI In"],
        get_output_names=lambda: ["GT-1000CORE MIDI Out"],
        open_input=lambda name: input_port,
        open_output=lambda name: output_port,
        Message=lambda type, data: types.SimpleNamespace(type=type, data=data),
    )
    return module, output_port


class MidiTransportTests(unittest.TestCase):
    def test_read_apply_undo_over_simulated_sysex(self):
        module, output = fake_mido()
        with patch.dict(sys.modules, {"mido": module}):
            controller = Controller()
            controller.connect("GT-1000CORE MIDI In", "GT-1000CORE MIDI Out")
            state = controller.read()
            self.assertEqual(state["mode"], "midi")
            self.assertEqual(state["patch_name"], "UNIT TEST PATCH")
            key = "amp_middle"
            old = state["values"][key]
            candidate = old + 2
            state = controller.new_proposal({key: candidate}, "MIDI simulator")
            state = controller.apply(state["proposal"]["id"], True)
            self.assertEqual(state["values"][key], candidate)
            self.assertEqual(output.memory[PARAMETERS[key].address], PARAMETERS[key].encode(candidate))
            state = controller.revert(True)
            self.assertEqual(state["values"][key], old)
            self.assertEqual(output.memory[PARAMETERS[key].address], PARAMETERS[key].encode(old))
            self.assertTrue(any(x[6] == 0x11 for x in output.sent if len(x) > 6))
            self.assertTrue(any(x[6] == 0x12 for x in output.sent if len(x) > 6))

    def test_reject_non_core_identity(self):
        module, _ = fake_mido(model_code=0x00)
        with patch.dict(sys.modules, {"mido": module}):
            with self.assertRaisesRegex(ValueError, "以外の機器"):
                MidiTransport("GT-1000CORE MIDI In", "GT-1000CORE MIDI Out")


if __name__ == "__main__":
    unittest.main()

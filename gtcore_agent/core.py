"""Roland MIDI SysEx protocol, allowlisted parameter map, and guarded edits.

All write addresses are under 10 00 00 00 (temporary patch).  The address
table is based on the GT-1000/GT-1000CORE MIDI Implementation, 2026-03-01.
This has NOT been tested against a physical GT-1000CORE.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
import time
import uuid


MODEL = (0x00, 0x00, 0x00, 0x4F)
TEMP_PATCH_PREFIX = (0x10, 0x00)


@dataclass(frozen=True)
class Parameter:
    key: str
    name: str
    address: tuple[int, int, int, int]
    low: int
    high: int
    max_step: int
    offset: int = 0  # device byte = user-facing integer + offset

    def encode(self, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not self.low <= value <= self.high:
            raise ValueError(f"{self.key}: 範囲外の値 {value!r} ({self.low}〜{self.high})")
        raw = value + self.offset
        if not 0 <= raw <= 127:
            raise ValueError("MIDI 7-bitの範囲外")
        return raw

    def decode(self, raw: int) -> int:
        value = raw - self.offset
        if not self.low <= value <= self.high:
            raise ValueError(f"{self.key}: 本体から想定外の値 {raw}")
        return value


# Single-byte, unambiguous, explicitly documented parameters only.
PARAMETERS = {
    p.key: p for p in (
        Parameter("ds1_drive", "DIST1 Drive", (0x10, 0, 0x13, 0x02), 0, 120, 15),
        Parameter("ds1_tone", "DIST1 Tone", (0x10, 0, 0x13, 0x03), -50, 50, 12, 64),
        Parameter("ds2_drive", "DIST2 Drive", (0x10, 0, 0x14, 0x02), 0, 120, 15),
        Parameter("amp_gain", "AMP A Gain", (0x10, 0, 0x15, 0x02), 0, 120, 15),
        Parameter("amp_bass", "AMP A Bass", (0x10, 0, 0x15, 0x06), 0, 100, 12),
        Parameter("amp_middle", "AMP A Middle", (0x10, 0, 0x15, 0x07), 0, 100, 12),
        Parameter("amp_treble", "AMP A Treble", (0x10, 0, 0x15, 0x08), 0, 100, 12),
        Parameter("amp_presence", "AMP A Presence", (0x10, 0, 0x15, 0x09), 0, 100, 12),
        Parameter("eq_low", "EQ1 Low Gain (dB)", (0x10, 0, 0x19, 0x02), -20, 20, 5, 32),
        Parameter("eq_high", "EQ1 High Gain (dB)", (0x10, 0, 0x19, 0x03), -20, 20, 5, 32),
        Parameter("delay_feedback", "Delay1 Feedback", (0x10, 0, 0x1D, 0x05), 0, 100, 12),
        Parameter("delay_level", "Delay1 Effect Level", (0x10, 0, 0x1D, 0x07), 0, 120, 15),
    )
}

# Useful status indicators; no switches are writable by the agent in this MVP.
SWITCHES = {
    "dist1": (0x10, 0, 0x13, 0x00),
    "dist2": (0x10, 0, 0x14, 0x00),
    "amp_a": (0x10, 0, 0x15, 0x00),
    "eq1": (0x10, 0, 0x19, 0x00),
    "delay1": (0x10, 0, 0x1D, 0x00),
}


def checksum(values: tuple[int, ...] | list[int]) -> int:
    return (-sum(values)) % 128


def message_rq1(device_id: int, address: tuple[int, ...], size: int) -> tuple[int, ...]:
    if not 0 <= device_id <= 31 or len(address) != 4 or any(not 0 <= x <= 127 for x in address):
        raise ValueError("不正なMIDIアドレスまたはデバイスID")
    if not 1 <= size <= 127:
        raise ValueError("RQ1のサイズは1〜127バイト")
    body = (*address, 0, 0, 0, size)
    return (0x41, device_id, *MODEL, 0x11, *body, checksum(body))


def message_dt1(device_id: int, address: tuple[int, ...], data: tuple[int, ...]) -> tuple[int, ...]:
    if not 0 <= device_id <= 31 or len(address) != 4 or not data or any(not 0 <= x <= 127 for x in (*address, *data)):
        raise ValueError("不正なSysExデータ")
    body = (*address, *data)
    return (0x41, device_id, *MODEL, 0x12, *body, checksum(body))


def parse_dt1(payload: tuple[int, ...], device_id: int, address: tuple[int, ...], length: int) -> tuple[int, ...] | None:
    if len(payload) < 13 or tuple(payload[:7]) != (0x41, device_id, *MODEL, 0x12):
        return None
    if tuple(payload[7:11]) != address:
        return None
    data = tuple(payload[11:-1])
    if len(data) != length or checksum((*address, *data)) != payload[-1]:
        return None
    return data


class DemoTransport:
    mode = "demo"

    def __init__(self):
        self.name = "DEMO PATCH"
        self.values = {
            "ds1_drive": 62, "ds1_tone": 5, "ds2_drive": 40,
            "amp_gain": 57, "amp_bass": 55, "amp_middle": 49,
            "amp_treble": 57, "amp_presence": 50, "eq_low": 0,
            "eq_high": 0, "delay_feedback": 32, "delay_level": 30,
        }
        self.switches = {"dist1": 1, "dist2": 0, "amp_a": 1, "eq1": 1, "delay1": 1}

    def read(self):
        return self.name, dict(self.values), dict(self.switches)

    def reread_values(self, keys):
        return {k: self.values[k] for k in keys}

    def write(self, key: str, value: int):
        PARAMETERS[key].encode(value)
        self.values[key] = value

    def close(self):
        pass


class MidiTransport:
    mode = "midi"

    def __init__(self, input_name: str, output_name: str):
        import mido

        # Exact names required. Never auto-select an arbitrary MIDI output.
        if input_name not in mido.get_input_names() or output_name not in mido.get_output_names():
            raise ValueError("選択されたMIDIポートが見つかりません")
        self.mido = mido
        self.input = mido.open_input(input_name)
        try:
            self.output = mido.open_output(output_name)
        except Exception:
            self.input.close()
            raise
        try:
            self.device_id = self._identify()
        except Exception:
            self.close()
            raise

    def _poll(self, timeout: float):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for msg in self.input.iter_pending():
                if msg.type == "sysex":
                    yield tuple(msg.data)
            time.sleep(0.01)

    def _clear(self):
        list(self.input.iter_pending())

    def _send(self, payload: tuple[int, ...]):
        self.output.send(self.mido.Message("sysex", data=payload))

    def _identify(self):
        self._clear()
        self._send((0x7E, 0x7F, 0x06, 0x01))  # universal identity request
        for data in self._poll(2.0):
            if (len(data) >= 13 and data[0] == 0x7E and data[2:5] == (0x06, 0x02, 0x41)
                    and data[5:7] == (0x4F, 0x03) and 0 <= data[1] <= 31):
                if data[9] != 0x02:  # the published GT-1000CORE identity distinction
                    raise ValueError("GT-1000CORE以外の機器です。安全のため接続しません")
                return data[1]
        raise TimeoutError("GT-1000/COREのIdentity Replyを確認できません。接続・MIDIポートを確認してください")

    def _request(self, address: tuple[int, ...], size: int):
        self._clear()
        self._send(message_rq1(self.device_id, address, size))
        for data in self._poll(1.5):
            parsed = parse_dt1(data, self.device_id, address, size)
            if parsed is not None:
                return parsed
        raise TimeoutError(f"本体からの応答がありません: {' '.join(f'{x:02X}' for x in address)}")

    def read(self):
        name_bytes = self._request((0x10, 0, 0, 0), 16)
        name = bytes(name_bytes).decode("ascii", "replace").strip() or "(無名パッチ)"
        values = {k: p.decode(self._request(p.address, 1)[0]) for k, p in PARAMETERS.items()}
        switches = {k: self._request(addr, 1)[0] for k, addr in SWITCHES.items()}
        return name, values, switches

    def reread_values(self, keys):
        return {k: PARAMETERS[k].decode(self._request(PARAMETERS[k].address, 1)[0]) for k in keys}

    def write(self, key: str, value: int):
        p = PARAMETERS[key]
        # Cannot address user-memory banks here. Temporary patch only.
        assert p.address[:2] == TEMP_PATCH_PREFIX
        self._send(message_dt1(self.device_id, p.address, (p.encode(value),)))
        time.sleep(0.07)

    def close(self):
        self.input.close()
        self.output.close()


class Controller:
    def __init__(self):
        self.lock = RLock()
        self.transport = DemoTransport()
        self.snapshot: dict[str, int] | None = None
        self.name: str | None = None
        self.switches: dict[str, int] = {}
        self.proposal = None
        self.undo = None
        self.generation = 0

    def _invalidate(self):
        self.generation += 1
        self.snapshot = None
        self.proposal = None
        self.undo = None

    def status(self):
        return {
            "mode": self.transport.mode,
            "device_id": getattr(self.transport, "device_id", None),
            "patch_name": self.name,
            "values": self.snapshot,
            "switches": self.switches,
            "proposal": self.proposal,
            "undo_available": self.undo is not None,
            "parameters": [{"key": p.key, "name": p.name, "min": p.low, "max": p.high, "max_step": p.max_step}
                           for p in PARAMETERS.values()],
        }

    def connect(self, input_name: str | None, output_name: str | None):
        with self.lock:
            new = MidiTransport(input_name, output_name) if input_name and output_name else DemoTransport()
            self.transport.close()
            self.transport = new
            self.name = None
            self.switches = {}
            self._invalidate()
            return self.status()

    def read(self):
        with self.lock:
            name, values, switches = self.transport.read()
            self._invalidate()
            self.name, self.snapshot, self.switches = name, values, switches
            return self.status()

    def new_proposal(self, changes: dict[str, int], reason: str):
        with self.lock:
            if self.snapshot is None:
                raise ValueError("先にパッチを読み込んでください")
            if not isinstance(changes, dict) or not 1 <= len(changes) <= 8:
                raise ValueError("提案は1〜8項目に制限しています")
            proposed = []
            for key, value in changes.items():
                if key not in PARAMETERS:
                    raise ValueError(f"未許可のパラメーター: {key}")
                param = PARAMETERS[key]
                param.encode(value)
                previous = self.snapshot[key]
                if abs(previous - value) > param.max_step:
                    raise ValueError(f"{key}: 1回の変更幅を超えています (±{param.max_step})")
                if previous != value:
                    proposed.append({"key": key, "name": param.name, "before": previous, "after": value})
            if not proposed:
                raise ValueError("現在の値から変更がありません")
            self.proposal = {"id": uuid.uuid4().hex, "generation": self.generation,
                             "reason": reason[:700], "changes": proposed}
            return self.status()

    def _restore(self, values: dict[str, int]):
        failures = []
        for key, value in values.items():
            try:
                self.transport.write(key, value)
            except Exception as ex:
                failures.append(f"{key}: {ex}")
        return failures

    def apply(self, proposal_id: str, confirmed: bool):
        with self.lock:
            if not confirmed or not self.proposal or self.proposal["id"] != proposal_id:
                raise ValueError("確認済みの最新提案IDが必要です")
            if self.snapshot is None or self.proposal["generation"] != self.generation:
                raise ValueError("パッチを再読み込みしてください")
            changes = self.proposal["changes"]
            keys = [c["key"] for c in changes]
            before = {c["key"]: c["before"] for c in changes}
            current_name, current_values, current_switches = self.transport.read()
            if (current_name != self.name or current_values != self.snapshot
                    or current_switches != self.switches):
                self._invalidate()
                raise ValueError("本体側のパッチまたは値が変更されています。再読み込みして提案を作り直してください")
            sent = {}
            try:
                for c in changes:
                    sent[c["key"]] = c["before"]
                    self.transport.write(c["key"], c["after"])
                verified = self.transport.reread_values(keys)
                if verified != {c["key"]: c["after"] for c in changes}:
                    raise RuntimeError("書き込み後の読み戻しが一致しません")
            except Exception as ex:
                failures = self._restore(sent)
                if not failures and sent:
                    try:
                        if self.transport.reread_values(sent) != sent:
                            failures.append("復元後の値が一致しません")
                    except Exception as read_error:
                        failures.append(f"復元後の読み戻し失敗: {read_error}")
                self._invalidate()
                suffix = " / 自動復元に失敗: " + ", ".join(failures) if failures else " / 復元処理を実行しました"
                raise RuntimeError(f"反映に失敗: {ex}{suffix}. 本体を確認してください") from ex
            for c in changes:
                self.snapshot[c["key"]] = c["after"]
            self.undo = {"before": before, "after": {c["key"]: c["after"] for c in changes}}
            self.proposal = None
            return self.status()

    def revert(self, confirmed: bool):
        with self.lock:
            if not confirmed or not self.undo:
                raise ValueError("取り消し可能な変更がありません")
            current_name, current_values, current_switches = self.transport.read()
            if (current_name != self.name or current_values != self.snapshot
                    or current_switches != self.switches):
                self._invalidate()
                raise ValueError("本体のパッチまたは状態が変わったため、取り消しを停止しました")
            failures = self._restore(self.undo["before"])
            if failures:
                self._invalidate()
                raise RuntimeError("復元失敗: " + ", ".join(failures))
            verified = self.transport.reread_values(self.undo["before"])
            if verified != self.undo["before"]:
                self._invalidate()
                raise RuntimeError("復元後の読み戻しが一致しません")
            self.snapshot.update(self.undo["before"])
            self.undo = None
            return self.status()

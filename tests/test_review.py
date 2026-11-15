"""Nemotron review step, with the HTTP call mocked (no key, no network)."""

import json

import numpy as np
import pytest

from rokoko_teleop.nemotron import NemotronClient, NemotronError
from rokoko_teleop.recorder import DatasetWriter, EpisodeBuffer, label_episode, pick_keyframes
from rokoko_teleop.review import parse_answer, review_dataset


def _reply(obj) -> bytes:
    text = obj if isinstance(obj, str) else json.dumps(obj)
    return json.dumps({"choices": [{"message": {"content": text}}]}).encode()


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.bodies = []

    def __call__(self, url, body, headers, timeout):
        assert url.endswith("/chat/completions")
        assert headers["Authorization"] == "Bearer test-key"
        self.bodies.append(json.loads(body))
        return self.responses.pop(0)


def _client(transport, tmp_path=None):
    return NemotronClient(api_key="test-key", transport=transport, sleep=lambda s: None,
                          cache_dir=tmp_path / "cache" if tmp_path else None)


def _dataset(tmp_path, lift_profile, peak_force=3.8, cracked=False):
    """A fake episode: egg lifted along `lift_profile` (m), force peaking at peak_force."""
    n = len(lift_profile)
    t = np.linspace(0, 10, n)
    force = np.where(np.asarray(lift_profile) > 0.005, peak_force, 0.0)
    buf = EpisodeBuffer()
    buf.rows = {k: [] for k in buf.rows}
    for i in range(n):
        buf.rows["t"].append(t[i])
        buf.rows["egg_force"].append(force[i])
        buf.rows["egg_pose"].append(np.array([0, 0, 0.03 + lift_profile[i], 0, 0, 0, 1.0]))
        for k in ("glove", "human_angles", "action", "wrist_target", "inspire", "qpos", "root_pose"):
            buf.rows[k].append(np.zeros(3))
    buf.max_lift = max(lift_profile)
    lift = np.asarray(lift_profile)
    frames = [(float(ti), np.full((8, 8, 3), 200, np.uint8)) for ti in t[::5]]
    kfs = pick_keyframes(frames, t, force, lift)
    label = label_episode(buf.max_lift, lift_profile[-1], cracked, float(force.max()), 8.0)
    DatasetWriter(tmp_path).save(buf, label, {"crack_force_n": 8.0}, kfs)
    return tmp_path


GOOD = {"outcome": "lifted", "confidence": 0.9, "reason": "Raised 11 cm, stayed white.",
        "egg_red_in_frames": False, "claimed_peak_force_n": 3.8, "claimed_max_lift_cm": 11.0,
        "evidence": [{"source": "frame:contact", "t": 2.6, "observation": "fingers touch the egg"},
                     {"source": "log", "t": 5.0, "observation": "lift 11 cm"}]}

LIFT = [0.0] * 10 + [0.11] * 20 + [0.0] * 10


def test_agreeing_review_sends_frames_and_log(tmp_path):
    ds = _dataset(tmp_path, LIFT)
    tr = FakeTransport([(200, _reply(GOOD))])
    [r] = review_dataset(ds, _client(tr))
    assert r["status"] == "agree" and not r["flag"] and r["model"] == "Nemotron 3.5 Super VL"
    content = tr.bodies[0]["messages"][1]["content"]
    assert any(p["type"] == "image_url" and p["image_url"]["url"].startswith("data:image/png;base64,")
               for p in content)
    assert "force_n" in content[0]["text"]
    assert "Nemotron 3.5 Super VL" in (ds / "review.md").read_text()


def test_dropped_disagreement_is_flagged(tmp_path):
    ds = _dataset(tmp_path, LIFT)
    tr = FakeTransport([(200, _reply({**GOOD, "outcome": "dropped", "reason": "fell fast"}))])
    [r] = review_dataset(ds, _client(tr))
    assert r["sim_outcome"] == "lifted" and r["outcome"] == "dropped"
    assert r["status"] == "disagree" and r["flag"]


def test_retry_on_429_then_success(tmp_path):
    ds = _dataset(tmp_path, LIFT)
    tr = FakeTransport([(429, b"slow down"), (503, b"busy"), (200, _reply(GOOD))])
    [r] = review_dataset(ds, _client(tr))
    assert r["status"] == "agree" and len(tr.bodies) == 3


def test_invalid_json_gets_one_repair(tmp_path):
    ds = _dataset(tmp_path, LIFT)
    tr = FakeTransport([(200, _reply("I think it was lifted.")), (200, _reply(GOOD))])
    [r] = review_dataset(ds, _client(tr))
    assert r["status"] == "agree" and r["calls"] == 2 and r["steps"][0].startswith("repair")
    assert "rejected" in tr.bodies[1]["messages"][-1]["content"]


def test_wrong_numbers_trigger_self_check(tmp_path):
    ds = _dataset(tmp_path, LIFT)
    tr = FakeTransport([(200, _reply({**GOOD, "claimed_peak_force_n": 12.0})), (200, _reply(GOOD))])
    [r] = review_dataset(ds, _client(tr))
    assert r["steps"][0].startswith("self-check") and r["status"] == "agree"
    assert "the log says 3.8 N" in tr.bodies[1]["messages"][-1]["content"]


def test_still_ungrounded_after_self_check_is_flagged(tmp_path):
    ds = _dataset(tmp_path, LIFT)
    bad = _reply({**GOOD, "claimed_max_lift_cm": 40})
    tr = FakeTransport([(200, bad), (200, bad)])
    [r] = review_dataset(ds, _client(tr))
    assert r["status"] == "ungrounded" and r["flag"] and r["calls"] == 2


def test_no_key_degrades_gracefully(tmp_path):
    ds = _dataset(tmp_path, LIFT)
    [r] = review_dataset(ds, NemotronClient(api_key=None))
    assert r["status"] == "not_configured" and "NVIDIA_API_KEY" in r["note"]
    assert json.loads((ds / "episodes.jsonl").read_text())["outcome"] == "lifted"  # label untouched


def test_api_down_degrades_gracefully(tmp_path):
    ds = _dataset(tmp_path, LIFT)
    tr = FakeTransport([(500, b"x")] * 5)
    [r] = review_dataset(ds, _client(tr))
    assert r["status"] == "unavailable" and "simulator label stands" in r["note"]


def test_cache_avoids_second_request(tmp_path):
    tr = FakeTransport([(200, _reply("hi"))])
    c = _client(tr, tmp_path)
    assert c.chat([{"role": "user", "content": "x"}]) == "hi"
    assert c.chat([{"role": "user", "content": "x"}]) == "hi"
    assert len(tr.bodies) == 1 and c.cache_hits == 1


def test_non_retryable_error_stops():
    tr = FakeTransport([(401, b"bad key")])
    with pytest.raises(NemotronError, match="401"):
        _client(tr).chat([{"role": "user", "content": "x"}])
    assert len(tr.bodies) == 1


def test_parse_rejects_unknown_frame():
    bad = {**GOOD, "evidence": [{"source": "frame:nope", "t": 1, "observation": "x"}]}
    a, err = parse_answer(json.dumps(bad), {"contact"})
    assert a is None and "frame:nope" in err
    a, err = parse_answer("<think>hmm</think>```json\n" + json.dumps(GOOD) + "\n```", {"contact"})
    assert err is None and a["outcome"] == "lifted"


def test_empty_reply_is_not_cached_and_gets_repaired(tmp_path):
    """A reasoning model can use the whole budget on thinking and return no
    content (finish_reason=length). That reply must not be cached, and the
    review must ask again."""
    empty = json.dumps({"choices": [{"message": {"content": ""}, "finish_reason": "length"}]}).encode()
    ds = _dataset(tmp_path / "ds", LIFT)
    tr = FakeTransport([(200, empty), (200, _reply(GOOD))])
    c = _client(tr, tmp_path)
    [r] = review_dataset(ds, c)
    assert r["status"] == "agree" and r["calls"] == 2
    assert "token budget" in r["steps"][0]
    assert tr.bodies[0]["max_tokens"] >= 4096
    assert len(list((tmp_path / "cache").glob("*.json"))) == 1  # only the good reply

"""Local faster-whisper backend: backend choice, segment shape, no-speech detection.

faster-whisper itself is replaced by a tiny fake so these tests run offline,
fast, and without the package installed.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

import whisper


class _Word:
    def __init__(self, start, end, word, probability=0.9):
        self.start, self.end, self.word, self.probability = start, end, word, probability


class _Seg:
    def __init__(self, start, end, text, no_speech_prob=0.01, avg_logprob=-0.2, words=None):
        self.start, self.end, self.text = start, end, text
        self.no_speech_prob, self.avg_logprob = no_speech_prob, avg_logprob
        self.words = words


def _install_fake(monkeypatch, segments, language_probability=0.99):
    calls = {}

    class WhisperModel:
        def __init__(self, name, device, compute_type):
            calls["init"] = (name, device, compute_type)

        def transcribe(self, path, **kwargs):
            calls["transcribe"] = (path, kwargs)
            info = types.SimpleNamespace(
                language="en", language_probability=language_probability, duration=10.0
            )
            return iter(segments), info

    fake = types.ModuleType("faster_whisper")
    fake.WhisperModel = WhisperModel
    monkeypatch.setitem(sys.modules, "faster_whisper", fake)
    return calls


def test_transcribe_local_uses_cpu_int8_and_vad(monkeypatch, tmp_path):
    calls = _install_fake(monkeypatch, [_Seg(0.0, 1.5, " Hello there. ")])
    segs, info = whisper.transcribe_local(tmp_path / "a.mp3", "small")
    assert calls["init"] == ("small", "cpu", "int8")
    assert calls["transcribe"][1]["vad_filter"] is True
    assert segs == [{"start": 0.0, "end": 1.5, "text": "Hello there."}]
    assert info["language"] == "en" and info["model"] == "small"


def test_word_timestamps_are_included_when_asked(monkeypatch, tmp_path):
    words = [_Word(0.0, 0.4, " Hello"), _Word(0.4, 0.9, " there.")]
    _install_fake(monkeypatch, [_Seg(0.0, 0.9, "Hello there.", words=words)])
    segs, _ = whisper.transcribe_local(tmp_path / "a.mp3", "small", word_timestamps=True)
    assert [w["word"] for w in segs[0]["words"]] == ["Hello", "there."]
    assert segs[0]["words"][1]["start"] == 0.4


def test_silent_segments_are_dropped(monkeypatch, tmp_path):
    _install_fake(monkeypatch, [
        _Seg(0.0, 2.0, "Thanks for watching!", no_speech_prob=0.9, avg_logprob=-1.4),
        _Seg(2.0, 3.0, "Real words.", no_speech_prob=0.1, avg_logprob=-0.3),
    ])
    segs, _ = whisper.transcribe_local(tmp_path / "a.mp3", "small")
    assert [s["text"] for s in segs] == ["Real words."]


def test_check_speech_empty_is_no_speech():
    with pytest.raises(whisper.NoSpeechDetected):
        whisper.check_speech([], {"language_probability": 0.99})


def test_check_speech_low_language_confidence_is_no_speech():
    segs = [{"start": 0.0, "end": 1.0, "text": "la la la"}]
    with pytest.raises(whisper.NoSpeechDetected, match="language confidence"):
        whisper.check_speech(segs, {"language_probability": 0.2})


def test_check_speech_passes_real_speech():
    whisper.check_speech([{"start": 0.0, "end": 1.0, "text": "hi"}], {"language_probability": 0.97})


def test_no_speech_is_not_a_systemexit():
    # watch.py treats SystemExit as failure; no-speech must stay distinguishable.
    assert not issubclass(whisper.NoSpeechDetected, SystemExit)


def _no_keys(monkeypatch, tmp_path):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(whisper.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.chdir(tmp_path)


def test_resolve_backend_falls_back_to_local(monkeypatch, tmp_path):
    _no_keys(monkeypatch, tmp_path)
    monkeypatch.setattr(whisper, "local_whisper_available", lambda: True)
    assert whisper.resolve_backend() == ("local", None)
    assert whisper.resolve_backend("local") == ("local", None)
    # Forcing an API backend never silently switches to local.
    assert whisper.resolve_backend("groq") == (None, None)


def test_resolve_backend_prefers_key(monkeypatch, tmp_path):
    _no_keys(monkeypatch, tmp_path)
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setattr(whisper, "local_whisper_available", lambda: True)
    assert whisper.resolve_backend() == ("groq", "gsk-test")


def test_resolve_backend_nothing_available(monkeypatch, tmp_path):
    _no_keys(monkeypatch, tmp_path)
    monkeypatch.setattr(whisper, "local_whisper_available", lambda: False)
    assert whisper.resolve_backend() == (None, None)
    assert whisper.resolve_backend("local") == (None, None)


def test_transcribe_video_local_no_speech(monkeypatch, tmp_path):
    _install_fake(monkeypatch, [], language_probability=0.3)
    monkeypatch.setattr(whisper, "extract_audio", lambda video, out: Path(out))
    with pytest.raises(whisper.NoSpeechDetected):
        whisper.transcribe_video("clip.mp4", tmp_path / "a.mp3", backend="local")

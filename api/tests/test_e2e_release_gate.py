import json


class _Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(
            {
                "status": "passed",
                "probe_id": "probe-1",
                "release_gate": {"eligible": True},
            }
        ).encode()


def test_release_gate_passes_only_for_green_probe(monkeypatch, capsys):
    from scripts import check_e2e_release_gate as gate

    monkeypatch.setattr(gate.urllib.request, "urlopen", lambda *_args, **_kwargs: _Response())

    assert gate.run_gate("https://example.test", timeout=1) == 0
    assert "PASS" in capsys.readouterr().out


def test_release_gate_blocks_non_200_or_non_passed_probe(monkeypatch, capsys):
    from scripts import check_e2e_release_gate as gate

    class FailedResponse(_Response):
        status = 503

        def read(self):
            return json.dumps(
                {
                    "status": "failed",
                    "probe_id": "probe-2",
                    "error": "ASR step failed",
                    "release_gate": {"eligible": False},
                }
            ).encode()

    monkeypatch.setattr(gate.urllib.request, "urlopen", lambda *_args, **_kwargs: FailedResponse())

    assert gate.run_gate("https://example.test", timeout=1) == 1
    assert "BLOCK" in capsys.readouterr().err


from backend.sheets import backoff_delays, col_letter


def test_col_letter_single():
    assert col_letter(0) == "A"
    assert col_letter(25) == "Z"


def test_col_letter_double():
    assert col_letter(26) == "AA"
    assert col_letter(27) == "AB"
    assert col_letter(51) == "AZ"
    assert col_letter(52) == "BA"


def test_backoff_is_truncated_exponential():
    delays = backoff_delays(attempts=6, maximum=64.0, jitter=lambda: 0.5)
    assert delays == [1.5, 2.5, 4.5, 8.5, 16.5, 32.5]
    capped = backoff_delays(attempts=9, maximum=64.0, jitter=lambda: 0.0)
    assert capped[-1] == 64.0


class _FakeResp:
    def __init__(self, status):
        self.status = status
        self.reason = ""


def _http_error(status):
    from googleapiclient.errors import HttpError
    return HttpError(_FakeResp(status), b"boom")


def test_execute_with_backoff_retries_then_succeeds(monkeypatch):
    from backend import sheets
    monkeypatch.setattr(sheets.time, "sleep", lambda s: None)
    calls = {"n": 0}

    class Req:
        def execute(self):
            calls["n"] += 1
            if calls["n"] < 3:
                raise _http_error(429)
            return {"ok": True}

    assert sheets._execute_with_backoff(Req()) == {"ok": True}
    assert calls["n"] == 3


def test_execute_with_backoff_raises_immediately_on_4xx(monkeypatch):
    from backend import sheets
    import pytest
    monkeypatch.setattr(sheets.time, "sleep", lambda s: None)
    calls = {"n": 0}

    class Req:
        def execute(self):
            calls["n"] += 1
            raise _http_error(404)

    with pytest.raises(sheets.SheetsError):
        sheets._execute_with_backoff(Req())
    assert calls["n"] == 1


def test_execute_with_backoff_wraps_transport_errors(monkeypatch):
    from backend import sheets
    import pytest
    monkeypatch.setattr(sheets.time, "sleep", lambda s: None)

    class Req:
        def execute(self):
            raise OSError("socket died")

    with pytest.raises(sheets.SheetsError):
        sheets._execute_with_backoff(Req())

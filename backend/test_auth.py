from backend.auth import domain_ok


def test_domain_ok_accepts_miva():
    assert domain_ok("ada@miva.university", "miva.university")


def test_domain_ok_is_case_insensitive():
    assert domain_ok("Ada@MIVA.University", "miva.university")


def test_domain_ok_rejects_other_domains():
    assert not domain_ok("mallory@gmail.com", "miva.university")
    assert not domain_ok("mallory@miva.university.evil.com", "miva.university")
    assert not domain_ok("mallory@notmiva.university", "miva.university")


def test_domain_ok_rejects_blank():
    assert not domain_ok("", "miva.university")
    assert not domain_ok(None, "miva.university")

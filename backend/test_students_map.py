import pytest

from backend.students_map import (
    HeaderError,
    map_rows,
    parse_drive_id,
    resolve_headers,
)

HEADERS = [
    "Timestamp", "Student ID ", "Matriculation Number", "Full Names ",
    "Residential Address ", "Programme of Study", "Active Phone Number",
    "Upload Passport Photograph ", "Student Name", "Student Email",
    "Matriculation No", "Programme", "Cohort", "Current Level-Semester",
]


def test_resolve_headers_strips_and_maps():
    cols = resolve_headers(HEADERS)
    assert cols["ts"] == 0
    assert cols["student_id"] == 1
    assert cols["photo"] == 7
    assert cols["email"] == 9
    assert cols["level"] == 13


def test_resolve_headers_missing_required_raises_named():
    with pytest.raises(HeaderError) as err:
        resolve_headers(["Timestamp", "Full Names"])
    assert "Student ID" in str(err.value)


def test_parse_drive_id_variants():
    fid = "1AbC-def_9xyzLMNOPQRSTUVWXyz01234"
    assert parse_drive_id(f"https://drive.google.com/open?id={fid}") == fid
    assert parse_drive_id(f"https://drive.google.com/file/d/{fid}/view") == fid
    assert parse_drive_id(fid) == fid
    assert parse_drive_id("not a link") is None
    assert parse_drive_id("") is None


def _row(**kw):
    base = {"ts": "8/01/2026 10:00:00", "student_id": "MIVA/2024/001", "matric_form": "CSC/24/001",
            "matric_staff": "", "name_form": "Ada  Obi", "name_staff": "", "email": "ada@miva.university",
            "prog_form": "BSc CS", "prog_staff": "", "cohort": "C7", "level": "200-1",
            "photo": "https://drive.google.com/open?id=1AbC-def_9xyzLMNOPQRSTUVWXyz01234"}
    base.update(kw)
    return base


def test_map_rows_coalesce_prefers_staff_columns():
    out, skipped = map_rows([_row(name_staff="Ada Obi-Staff", matric_staff="CSC/24/999", prog_staff="BSc Comp Sci")])
    assert out[0]["full_name"] == "Ada Obi-Staff"
    assert out[0]["matric"] == "CSC/24/999"
    assert out[0]["programme"] == "BSc Comp Sci"
    assert skipped == 0


def test_map_rows_falls_back_to_form_columns_and_normalizes():
    out, _ = map_rows([_row()])
    assert out[0]["full_name"] == "Ada Obi"          # whitespace collapsed
    assert out[0]["matric"] == "CSC/24/001"
    assert out[0]["natural_key"] == "MIVA/2024/001"  # student_id wins
    assert out[0]["photo_drive_file_id"] == "1AbC-def_9xyzLMNOPQRSTUVWXyz01234"


def test_map_rows_key_priority_and_skip():
    out, skipped = map_rows([
        _row(student_id="", matric_form="", matric_staff=""),          # falls to email
        _row(student_id="", matric_form="", email="", name_form="X"),  # no key -> skipped
    ])
    assert out[0]["natural_key"] == "ada@miva.university"
    assert len(out) == 1 and skipped == 1


def test_map_rows_dedupe_latest_timestamp_wins():
    out, _ = map_rows([
        _row(ts="8/01/2026 10:00:00", name_form="Old Name"),
        _row(ts="8/02/2026 09:00:00", name_form="New Name"),
    ])
    assert len(out) == 1
    assert out[0]["full_name"] == "New Name"

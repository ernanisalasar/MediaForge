import pytest

from mediaforge.errors import PathSecurityError
from mediaforge.services.fs_utils import ensure_within, safe_join, sanitize_filename, unique_path


@pytest.mark.parametrize("raw,expected", [
    ("video.mp4", "video.mp4"),
    ("../../etc/passwd", "passwd"),
    ("..\\..\\Windows\\system32\\cmd.exe", "cmd.exe"),
    ("a<b>c:d\"e|f?g*.mp4", "a_b_c_d_e_f_g_.mp4"),
    ("CON.mp4", "_CON.mp4"),
    ("nul", "_nul"),
    ("   ", "arquivo"),
    ("..", "arquivo"),
    ("...", "arquivo"),
    (".oculto.mp4", "oculto.mp4"),
    ("nome com ponto final.", "nome com ponto final"),
    ("rtl\u202egpj.exe", "rtlgpj.exe"),
    ("ctrl\x00\x1fchar.mp3", "ctrlchar.mp3"),
])
def test_sanitize(raw, expected):
    assert sanitize_filename(raw) == expected


def test_sanitize_limits_length_and_keeps_extension():
    out = sanitize_filename("a" * 500 + ".mp4")
    assert len(out) <= 150 and out.endswith(".mp4")


def test_safe_join_stays_inside(tmp_path):
    p = safe_join(tmp_path, "../fora.mp4")
    assert p.parent == tmp_path.resolve()


def test_ensure_within_rejects_escape(tmp_path):
    with pytest.raises(PathSecurityError):
        ensure_within(tmp_path, tmp_path.parent / "x.txt")


def test_unique_path(tmp_path):
    f = tmp_path / "a.mp4"
    assert unique_path(f) == f
    f.write_bytes(b"x")
    assert unique_path(f).name == "a (1).mp4"

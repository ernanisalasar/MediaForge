"""Garante, por inspeção do código-fonte, as regras de produto do projeto."""
import re
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "mediaforge"
SOURCES = {p: p.read_text(encoding="utf-8") for p in PKG.rglob("*.py")}


def test_only_yt_dlp_is_used_for_youtube():
    pattern = re.compile(r"\b(youtube_dl|pytube|pytubefix|youtube_dlc|you_get)\b", re.I)
    assert not [p.name for p, s in SOURCES.items() if pattern.search(s)]


def test_no_cookie_or_credential_handling():
    pattern = re.compile(r"(browser_cookie3|cookiefile|cookiesfrombrowser|cookies_from_browser|Cookie\s*:)", re.I)
    assert not [p.name for p, s in SOURCES.items() if pattern.search(s)]


def test_no_shell_execution():
    pattern = re.compile(r"(shell\s*=\s*True|os\.system\(|os\.popen\()")
    assert not [p.name for p, s in SOURCES.items() if pattern.search(s)]


def test_no_telemetry_or_third_party_endpoints():
    allowed = {"studio.youtube.com", "takeout.google.com", "www.youtube.com", "ffmpeg.org", "example.com"}
    urls = set()
    for s in SOURCES.values():
        urls |= set(re.findall(r"https?://([A-Za-z0-9.\-]+)", s))
    assert urls - allowed - {"www.w3.org"} == set(), urls


def test_only_two_youtube_shortcuts_exist():
    from mediaforge.services.source_policy import STUDIO_URL, TAKEOUT_URL
    assert STUDIO_URL == "https://studio.youtube.com/" and TAKEOUT_URL == "https://takeout.google.com/"

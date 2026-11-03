import pytest

from mediaforge.errors import SourcePolicyError
from mediaforge.services.source_policy import (
    SourcePolicy, check_ip, is_youtube_url, normalize_youtube_video_url, redact_url,
)


@pytest.mark.parametrize("url", [
    "https://example.com/video.mp4", "http://example.com:8080/a/b.mp3", "HTTPS://Example.com/x.webm",
])
def test_valid_urls(public_policy, url):
    assert public_policy.validate_url(url) == url


@pytest.mark.parametrize("url", [
    "", "   ", "ftp://example.com/a.mp4", "file:///etc/passwd", "javascript:alert(1)",
    "//example.com/a.mp4", "https:///a.mp4", "https://user:pass@example.com/a.mp4", "http://exa mple.com",
])
def test_invalid_urls(public_policy, url):
    with pytest.raises(SourcePolicyError):
        public_policy.validate_url(url)


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/a.mp4", "http://127.1.2.3/a", "http://[::1]/a", "http://0.0.0.0/a",
    "http://10.0.0.1/a", "http://172.16.5.4/a", "http://192.168.1.1/a", "http://100.64.0.1/a",
    "http://169.254.169.254/latest/meta-data", "http://169.254.170.2/v2", "http://100.100.100.200/",
    "http://[fd00:ec2::254]/", "http://[fe80::1]/", "http://[::ffff:127.0.0.1]/",
    "http://localhost/a", "http://foo.localhost/a", "http://metadata.google.internal/computeMetadata/v1/",
    "http://printer.local/a", "http://224.0.0.1/a",
])
def test_private_and_metadata_blocked(public_policy, url):
    with pytest.raises(SourcePolicyError):
        public_policy.validate_url(url)


def test_numeric_host_variants_resolved_and_blocked():
    # resolvedor devolve loopback para formas numéricas exóticas (como o getaddrinfo faria)
    policy = SourcePolicy(resolver=lambda h, p: ["127.0.0.1"])
    for url in ("http://2130706433/a", "http://0x7f.0.0.1/a", "http://evil.example/a"):
        with pytest.raises(SourcePolicyError):
            policy.validate_url(url)


def test_any_private_ip_among_resolved_blocks():
    policy = SourcePolicy(resolver=lambda h, p: ["93.184.216.34", "10.0.0.7"])
    with pytest.raises(SourcePolicyError):
        policy.validate_url("https://rebind.example/a.mp4")


def test_youtube_url_still_rejects_private_dns():
    policy = SourcePolicy(resolver=lambda h, p: ["10.0.0.7"])
    with pytest.raises(SourcePolicyError):
        policy.validate_url("https://www.youtube.com/watch?v=BaW_jenozKc")


def test_unresolvable_host_rejected():
    policy = SourcePolicy(resolver=lambda h, p: [])
    with pytest.raises(SourcePolicyError):
        policy.validate_url("https://nao-existe.example/a.mp4")


def test_check_ip_accepts_public():
    check_ip("93.184.216.34")
    check_ip("2606:2800:220:1:248:1893:25c8:1946")


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=BaW_jenozKc", "https://youtu.be/BaW_jenozKc",
    "https://m.youtube.com/watch?v=BaW_jenozKc", "https://music.youtube.com/watch?v=BaW_jenozKc",
    "https://YOUTUBE.com/shorts/BaW_jenozKc",
])
def test_youtube_detected_and_allowed(public_policy, url):
    assert is_youtube_url(url)
    assert public_policy.validate_url(url) == url


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=BaW_jenozKc&list=PL123",
    "https://youtu.be/BaW_jenozKc?si=share-token",
    "https://www.youtube.com/shorts/BaW_jenozKc",
])
def test_youtube_video_url_normalized_without_playlist_or_tracking(url):
    assert normalize_youtube_video_url(url) == "https://www.youtube.com/watch?v=BaW_jenozKc"


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/playlist?list=PL123",
    "https://www.youtube.com/channel/UC123",
    "https://www.youtube-nocookie.com/embed/BaW_jenozKc",
    "https://www.youtube.com/watch?v=not-a-valid-id",
])
def test_youtube_playlist_and_non_video_pages_rejected(url):
    with pytest.raises(SourcePolicyError, match="vídeo"):
        normalize_youtube_video_url(url)


def test_non_youtube_lookalikes_not_flagged():
    assert not is_youtube_url("https://notyoutube.com/a.mp4")
    assert not is_youtube_url("https://example.com/youtube.com/a.mp4")
    assert not is_youtube_url("https://www.youtube-nocookie.com/embed/BaW_jenozKc")


def test_redact_url_removes_secrets():
    out = redact_url("https://user:pw@cdn.example.com:8443/a/b.mp4?token=SEGREDO&sig=abc#frag")
    assert out == "https://cdn.example.com:8443/a/b.mp4"
    assert "SEGREDO" not in out and "pw" not in out

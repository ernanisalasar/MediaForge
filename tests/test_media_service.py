import sys
import threading
import time
from pathlib import Path

import pytest

from mediaforge.errors import DestinationExistsError, MediaServiceError
from mediaforge.models.formats import AUDIO_FORMATS, VIDEO_FORMATS, allowed_bitrates, get_format
from mediaforge.services import media_service as ms
from mediaforge.services.media_service import (
    ConversionCancelled, ConversionOptions, MediaService, available_resolutions, build_command,
    parse_encoders, quality_notes, run_process, validate_options,
)
from mediaforge.services.metadata_service import MediaInfo, StreamInfo, parse_ffprobe, probe


def fake_info(height=1080, vcodec="h264", acodec="aac", abr=128000, has_video=True, has_audio=True):
    return MediaInfo(
        path=Path("/tmp/entrada.mp4"), size_bytes=1000, duration=10.0, container="mov,mp4",
        video=StreamInfo(codec=vcodec, width=height * 16 // 9, height=height) if has_video else None,
        audio=StreamInfo(codec=acodec, sample_rate=44100, channels=2, bitrate=abr) if has_audio else None,
    )


# ---------------------------------------------------------------- formatos e opções
def test_catalog_has_requested_formats():
    assert {f.key for f in VIDEO_FORMATS} == {"mp4", "webm", "mov", "mkv"}
    assert {f.key for f in AUDIO_FORMATS} == {"mp3", "m4a", "wav", "flac", "opus"}


def test_bitrates_only_where_meaningful():
    assert allowed_bitrates(get_format("mp3")) == (128, 192, 256, 320)
    assert allowed_bitrates(get_format("opus")) == (128, 192, 256)
    assert allowed_bitrates(get_format("wav")) == () and allowed_bitrates(get_format("flac")) == ()


def test_no_upscaling_options():
    opts = {k: ok for k, _l, ok, _r in available_resolutions(fake_info(height=720))}
    assert opts == {"original": True, "1080": False, "720": False, "480": True, "360": True}


def test_validate_rejects_upscale_and_wrong_mode():
    with pytest.raises(MediaServiceError, match="resolução"):
        validate_options(fake_info(720), ConversionOptions("video", "mp4", "1080"))
    with pytest.raises(MediaServiceError, match="não tem vídeo"):
        validate_options(fake_info(has_video=False), ConversionOptions("video", "mp4"))
    with pytest.raises(MediaServiceError, match="áudio"):
        validate_options(fake_info(has_audio=False), ConversionOptions("audio", "mp3"))
    with pytest.raises(MediaServiceError, match="kbps"):
        validate_options(fake_info(), ConversionOptions("audio", "opus", audio_bitrate=320))
    with pytest.raises(ValueError):
        validate_options(fake_info(), ConversionOptions("audio", "xyz"))


def test_lossless_warning_for_lossy_source():
    notes = quality_notes(fake_info(acodec="mp3"), ConversionOptions("audio", "flac"))
    assert notes and "não recupera" in notes[0]
    assert not quality_notes(fake_info(acodec="flac"), ConversionOptions("audio", "flac"))


def test_bitrate_above_source_warning():
    notes = quality_notes(fake_info(abr=96000, acodec="mp3"), ConversionOptions("audio", "mp3", audio_bitrate=320))
    assert notes and "não melhora" in notes[0]


# ---------------------------------------------------------------- construção segura do comando
def test_command_is_list_of_strings_without_shell(tmp_path):
    evil = tmp_path / "a; rm -rf ~ && $(whoami) `id`.mp4"
    cmd = build_command("ffmpeg", evil, tmp_path / "saida.mkv", fake_info(), ConversionOptions("video", "mkv"))
    assert isinstance(cmd, list) and all(isinstance(a, str) for a in cmd)
    assert str(evil.resolve()) in cmd  # nome malicioso permanece UM único argumento
    assert cmd[cmd.index("-i") + 1] == str(evil.resolve())


def test_command_uses_absolute_paths_even_for_dash_names(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cmd = build_command("ffmpeg", Path("-rf.mp4"), Path("-out.mp3"), fake_info(), ConversionOptions("audio", "mp3"))
    assert not any(a.startswith("-rf") or a == "-out.mp3" for a in cmd)


def test_video_mp4_copies_h264_when_possible_and_scales_when_needed(tmp_path):
    same = build_command("ffmpeg", tmp_path / "a.mp4", tmp_path / "b.mp4", fake_info(), ConversionOptions("video", "mp4"))
    assert same[same.index("-c:v") + 1] == "copy"
    scaled = build_command("ffmpeg", tmp_path / "a.mp4", tmp_path / "b.mp4", fake_info(), ConversionOptions("video", "mp4", "720"))
    assert scaled[scaled.index("-c:v") + 1] == "libx264" and "scale=-2:720" in scaled
    vp9 = build_command("ffmpeg", tmp_path / "a.mp4", tmp_path / "b.webm", fake_info(), ConversionOptions("video", "webm"))
    assert "libvpx-vp9" in vp9 and "libopus" in vp9


@pytest.mark.parametrize("key,codec", [("mp3", "libmp3lame"), ("m4a", "aac"), ("wav", "pcm_s16le"), ("flac", "flac"), ("opus", "libopus")])
def test_audio_codecs_and_bitrate(tmp_path, key, codec):
    cmd = build_command("ffmpeg", tmp_path / "a.mp4", tmp_path / f"b.{key}", fake_info(), ConversionOptions("audio", key, audio_bitrate=256))
    assert cmd[cmd.index("-c:a") + 1] == codec and "-vn" in cmd
    assert ("-b:a" in cmd) == (key not in ("wav", "flac"))


def test_parse_encoders():
    out = "Encoders:\n ------\n V....D libx264              libx264 H.264\n A....D aac                  AAC\n"
    assert parse_encoders(out) == {"libx264", "aac"}


def test_output_never_equals_source(tmp_path):
    src = tmp_path / "clip.mp4"
    out = MediaService.resolve_output(src, tmp_path, "clip", get_format("mp4"))
    assert out.name == "clip (convertido).mp4"
    out2 = MediaService.resolve_output(src, tmp_path, "../../fuga", get_format("mkv"))
    assert out2.parent == tmp_path.resolve() and out2.name == "fuga.mkv"


# ---------------------------------------------------------------- ffprobe
def test_parse_ffprobe_ignores_cover_art():
    data = {
        "streams": [
            {"codec_type": "video", "codec_name": "mjpeg", "disposition": {"attached_pic": 1}},
            {"codec_type": "audio", "codec_name": "mp3", "sample_rate": "44100", "channels": 2, "bit_rate": "128000"},
        ],
        "format": {"duration": "12.5", "format_name": "mp3", "size": "100"},
    }
    info = parse_ffprobe(data, Path("x.mp3"))
    assert info.kind == "audio" and info.duration == 12.5 and info.audio.sample_rate == 44100


def test_probe_real_files(sample_video, sample_audio, tools):
    v = probe(sample_video, tools)
    assert v.kind == "video" and (v.video.width, v.video.height) == (320, 240) and v.video.codec == "h264"
    assert v.audio.codec == "aac" and v.duration and 1.5 < v.duration < 2.5
    a = probe(sample_audio, tools)
    assert a.kind == "audio" and a.audio.codec == "mp3" and a.audio.channels in (1, 2)


def test_probe_rejects_non_media(tmp_path, tools):
    bad = tmp_path / "texto.mp4"
    bad.write_text("isto não é mídia")
    with pytest.raises(MediaServiceError):
        probe(bad, tools)
    with pytest.raises(MediaServiceError):
        probe(tmp_path / "inexistente.mp4", tools)


# ---------------------------------------------------------------- conversões reais
@pytest.mark.parametrize("key", ["mp4", "mkv", "mov", "webm"])
def test_convert_video_formats(tmp_path, tools, sample_video, key):
    svc = MediaService(tools)
    events = []
    out = svc.convert(sample_video, tmp_path, "saida", ConversionOptions("video", key), progress_cb=events.append)
    info = probe(out, tools)
    assert out.suffix == f".{key}" and info.has_video and info.has_audio
    assert events and events[-1].fraction == 1.0
    assert sample_video.exists()  # original preservado
    assert not [p for p in tmp_path.iterdir() if ".part" in p.name]


def test_upscale_is_refused(tmp_path, tools, sample_video):
    # a origem tem 240p: qualquer "redução" listada (360/480/720/1080) seria aumento e deve ser recusada
    with pytest.raises(MediaServiceError, match="resolução"):
        MediaService(tools).convert(sample_video, tmp_path, "x", ConversionOptions("video", "mp4", "360"))
    assert list(tmp_path.iterdir()) == []


def test_resize_down_from_larger_source(tmp_path, tools):
    import subprocess
    big = tmp_path / "grande.mp4"
    subprocess.run([tools.ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=10:duration=1",
                    "-pix_fmt", "yuv420p", str(big)], check=True)
    out = MediaService(tools).convert(big, tmp_path / "o", "p", ConversionOptions("video", "mp4", "360"))
    assert probe(out, tools).video.height == 360


@pytest.mark.parametrize("key", ["mp3", "m4a", "wav", "flac", "opus"])
def test_extract_audio_from_video(tmp_path, tools, sample_video, key):
    out = MediaService(tools).convert(sample_video, tmp_path, "audio", ConversionOptions("audio", key, audio_bitrate=192))
    info = probe(out, tools)
    assert info.kind == "audio" and out.suffix == f".{key}"


def test_audio_file_to_audio_and_video_mode_rejected(tmp_path, tools, sample_audio):
    svc = MediaService(tools)
    assert svc.convert(sample_audio, tmp_path, "a", ConversionOptions("audio", "wav")).exists()
    with pytest.raises(MediaServiceError, match="não tem vídeo"):
        svc.convert(sample_audio, tmp_path, "b", ConversionOptions("video", "mp4"))


def test_existing_destination_requires_confirmation(tmp_path, tools, sample_video):
    svc = MediaService(tools)
    opts = ConversionOptions("audio", "mp3")
    first = svc.convert(sample_video, tmp_path, "x", opts)
    first.write_bytes(b"conteudo-do-usuario")
    with pytest.raises(DestinationExistsError):
        svc.convert(sample_video, tmp_path, "x", opts)
    assert first.read_bytes() == b"conteudo-do-usuario"
    svc.convert(sample_video, tmp_path, "x", opts, overwrite=True)
    assert first.read_bytes() != b"conteudo-do-usuario"


def test_corrupt_input_gives_clear_error(tmp_path, tools):
    bad = tmp_path / "ruim.mp4"
    bad.write_bytes(b"\x00" * 2048)
    with pytest.raises(MediaServiceError):
        MediaService(tools).convert(bad, tmp_path, "x", ConversionOptions("video", "mp4"))


def test_thumbnail(tmp_path, tools, sample_video):
    assert MediaService(tools).make_thumbnail(sample_video, tmp_path / "t.png", 0.5)
    assert not MediaService(tools).make_thumbnail(tmp_path / "nao.mp4", tmp_path / "t2.png")


# ---------------------------------------------------------------- processo: cancelamento e falhas
def test_run_process_cancel_terminates_process():
    ev = threading.Event()
    threading.Timer(0.5, ev.set).start()
    t0 = time.time()
    with pytest.raises(ConversionCancelled):
        run_process([sys.executable, "-c", "import time; time.sleep(30)"], None, None, ev)
    assert time.time() - t0 < 10


def test_run_process_failure_reports_stderr():
    code = "import sys; sys.stderr.write('Invalid data found when processing input\\n'); sys.exit(1)"
    with pytest.raises(MediaServiceError, match="corrompido"):
        run_process([sys.executable, "-c", code], None, None, None)


def test_run_process_missing_executable():
    with pytest.raises(MediaServiceError):
        run_process(["/caminho/que/nao/existe/ffmpeg"], None, None, None)


def test_run_process_parses_progress():
    code = ("import sys\n"
            "for us in (1000000, 2500000, 5000000):\n"
            "    print(f'out_time_us={us}'); print('speed=2.0x'); sys.stdout.flush()\n"
            "    import time; time.sleep(0.15)\n")
    got = []
    run_process([sys.executable, "-c", code], 5.0, got.append, None)
    assert got and got[-1].fraction == pytest.approx(1.0)
    assert any(p.eta_seconds is not None for p in got)


def test_cancel_real_conversion_cleans_partial(tmp_path, tools):
    import subprocess
    big = tmp_path / "longo.mp4"
    subprocess.run([tools.ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30:duration=120",
                    "-c:v", "libx264", "-preset", "ultrafast", str(big)], check=True)
    ev = threading.Event()
    threading.Timer(1.0, ev.set).start()
    with pytest.raises(ConversionCancelled):
        MediaService(tools).convert(big, tmp_path / "o", "x", ConversionOptions("video", "webm"), cancel_event=ev)
    leftovers = list((tmp_path / "o").iterdir())
    assert leftovers == [] and big.exists()

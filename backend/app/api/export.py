"""Export API routes: download MIDI, MusicXML, PDF, ZIP."""

import shutil
import subprocess
import zipfile
import io
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from app.utils.file_storage import get_output_dir

# Lazy import for music21 — heavy, only needed for PDF generation and MusicXML parsing
_m21 = None
def _get_music21():
    global _m21
    if _m21 is None:
        import music21 as m
        _m21 = m
    return _m21

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/{task_id}/midi")
async def download_midi(task_id: str):
    """Download the transcribed MIDI file."""
    midi_path = get_output_dir(task_id) / "transcribed_clean.mid"
    if not midi_path.exists():
        raise HTTPException(status_code=404, detail="MIDI 文件不存在")
    return FileResponse(
        midi_path,
        media_type="audio/midi",
        filename=f"{task_id}_piano.mid",
    )


@router.get("/{task_id}/musicxml")
async def download_musicxml(task_id: str):
    """Download the MusicXML score."""
    xml_path = get_output_dir(task_id) / "score.musicxml"
    if not xml_path.exists():
        raise HTTPException(status_code=404, detail="MusicXML 文件不存在")
    return FileResponse(
        xml_path,
        media_type="application/vnd.recordare.musicxml+xml",
        filename=f"{task_id}_score.musicxml",
    )


@router.get("/{task_id}/pdf")
async def download_pdf(task_id: str):
    """Download the PDF score (generated server-side via LilyPond or MuseScore)."""
    pdf_path = get_output_dir(task_id) / "score.pdf"
    if not pdf_path.exists():
        # Try to generate PDF from MusicXML
        xml_path = get_output_dir(task_id) / "score.musicxml"
        if not xml_path.exists():
            raise HTTPException(status_code=404, detail="MusicXML 文件不存在，无法生成 PDF")

        try:
            pdf_path = _render_pdf(xml_path)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"PDF 生成失败: {e}",
            )

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"{task_id}_piano_score.pdf",
    )


@router.get("/{task_id}/audio")
async def download_audio(task_id: str):
    """Download synthesized audio (WAV) from transcribed MIDI."""
    out_dir = get_output_dir(task_id)
    audio_path = out_dir / "synthesized.wav"
    if not audio_path.exists():
        midi_path = out_dir / "transcribed_clean.mid"
        if not midi_path.exists():
            raise HTTPException(status_code=404, detail="MIDI 文件不存在，无法合成音频")
        try:
            audio_path = _synthesize_audio(midi_path)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"音频合成失败: {e}",
            )

    return FileResponse(
        audio_path,
        media_type="audio/wav",
        filename=f"{task_id}_piano.wav",
    )


@router.get("/{task_id}/musicxml_text")
async def get_musicxml_text(task_id: str):
    """Get MusicXML content as text (for frontend OSMD rendering)."""
    xml_path = get_output_dir(task_id) / "score.musicxml"
    if not xml_path.exists():
        raise HTTPException(status_code=404, detail="MusicXML 文件不存在")
    return PlainTextResponse(
        xml_path.read_text(encoding="utf-8"),
        media_type="application/xml",
    )


@router.get("/{task_id}/zip")
async def download_zip(task_id: str):
    """Download all files (MIDI + MusicXML + audio) as a ZIP archive."""
    out_dir = get_output_dir(task_id)
    midi_path = out_dir / "transcribed_clean.mid"
    xml_path = out_dir / "score.musicxml"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if midi_path.exists():
            zf.write(str(midi_path), f"{task_id}_piano.mid")
        if xml_path.exists():
            zf.write(str(xml_path), f"{task_id}_score.musicxml")
        # Try to include audio if available
        audio_path = out_dir / "synthesized.wav"
        if not audio_path.exists():
            try:
                audio_path = _synthesize_audio(midi_path) if midi_path.exists() else None
            except Exception:
                audio_path = None
        if audio_path and audio_path.exists():
            zf.write(str(audio_path), f"{task_id}_piano.wav")

    buf.seek(0)
    return FileResponse(
        buf,
        media_type="application/zip",
        filename=f"{task_id}_notedigger.zip",
    )


def _render_pdf(musicxml_path: Path) -> Path:
    """Render MusicXML to PDF using music21 + LilyPond if available."""
    pdf_path = musicxml_path.with_suffix(".pdf")

    score = _get_music21().converter.parse(str(musicxml_path))

    # Try LilyPond first (better engraving)
    try:
        lilypond = shutil.which("lilypond")
        if lilypond:
            ly_path = musicxml_path.with_suffix(".ly")
            score.write("lilypond", fp=str(ly_path))
            subprocess.run(
                ["lilypond", "--pdf", "-o", str(musicxml_path.parent), str(ly_path)],
                capture_output=True,
                check=True,
            )
            # LilyPond output has different filename pattern
            expected = musicxml_path.parent / f"{musicxml_path.stem}.pdf"
            if expected.exists():
                expected.rename(pdf_path)
                return pdf_path
    except Exception:
        pass

    # Fallback: music21's built-in PDF writer (requires MuseScore or LilyPond)
    try:
        score.write("musicxml.pdf", fp=str(pdf_path))
    except Exception:
        # Last resort: just return the MusicXML file
        raise RuntimeError("无法生成 PDF，请安装 LilyPond 或 MuseScore")

    return pdf_path


def _synthesize_audio(midi_path: Path) -> Path:
    """Synthesize MIDI to audio for preview playback.

    Tries FluidSynth first (best quality), falls back to pure Python
    sine-wave synthesis (always works, zero deps).
    """
    wav_path = midi_path.with_suffix(".wav")

    # Try FluidSynth first for best quality
    soundfont_paths = [
        "/usr/share/sounds/sf2/FluidR3_GM.sf2",
        "/usr/share/sounds/sf2/TimGM6mb.sf2",
    ]

    soundfont = None
    for sf in soundfont_paths:
        if Path(sf).exists():
            soundfont = sf
            break

    if soundfont and shutil.which("fluidsynth"):
        try:
            subprocess.run(
                ["fluidsynth", "-ni", soundfont, str(midi_path), "-F", str(wav_path), "-r", "22050"],
                capture_output=True, check=True, timeout=30,
            )
            return wav_path
        except Exception:
            pass  # Fall through to Python synth

    # Pure Python fallback — always works
    from app.services.midi_to_audio import midi_to_wav
    return midi_to_wav(midi_path, wav_path)

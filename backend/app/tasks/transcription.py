"""Async transcription task: audio → MIDI → MusicXML pipeline."""

import traceback
from pathlib import Path

import pretty_midi

from app.tasks.celery_app import celery_app
from app.services.audio import preprocess_audio, validate_audio
from app.services.midi_to_xml import midi_to_musicxml
from app.services.youtube import download_audio, is_supported_url
from app.models.aria_amt import transcribe_audio_python
from app.models.basic_pitch_model import transcribe_basic_pitch
from app.models.simple_amt import transcribe_simple
from app.models.cloud_amt import transcribe_cloud, is_cloud_available
from app.models.chord_detect import detect_chords, format_chord_line
from app.models.arranger import arrange_piano, STYLES
from app.models.postprocess import postprocess_midi, get_midi_info
from app.utils.file_storage import get_output_dir, get_upload_path


def _run_pipeline_with_progress(
    task_id: str,
    source_type: str,
    source_path: str | None = None,
    source_url: str | None = None,
    options: dict | None = None,
    progress_callback=None,
) -> dict:
    """Pipeline with progress callbacks for real-time UI updates."""
    cb = progress_callback or (lambda stage, pct: None)
    options = options or {}
    output_dir = get_output_dir(task_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1: Get audio
        cb("获取音频…", 10)
        audio_path = _acquire_audio(task_id, source_type, source_path, source_url)
        original_filename = Path(source_path).name if source_path else "audio"

        # Step 2: Validate
        cb("分析音频…", 20)
        meta = validate_audio(audio_path)

        # Step 3: Preprocess
        cb("音频预处理…", 30)
        processed_path = output_dir / "processed.wav"
        preprocess_audio(audio_path, processed_path)

        # Step 4: Transcribe
        model_choice = options.get("model", "auto")

        cb("AI 识别音符中…（最慢的一步）", 50)
        if model_choice == "aria-amt":
            # Try cloud GPU first, then local CUDA
            if is_cloud_available():
                raw_midi_path = transcribe_cloud(processed_path, output_dir)
            else:
                raw_midi_path = transcribe_audio_python(processed_path, output_dir, model="medium-double")
        elif model_choice == "basic-pitch":
            raw_midi_path = transcribe_basic_pitch(processed_path, output_dir, quality="medium")
        elif model_choice == "simple":
            raw_midi_path = transcribe_simple(processed_path, output_dir)
        else:
            # Auto-select: cloud > basic-pitch > simple
            if is_cloud_available():
                raw_midi_path = transcribe_cloud(processed_path, output_dir)
            else:
                raw_midi_path = transcribe_basic_pitch(processed_path, output_dir, quality="medium")

        # Step 5: Post-process
        cb("优化谱面…", 70)
        clean_midi_path = output_dir / "transcribed_clean.mid"
        postprocess_midi(raw_midi_path, clean_midi_path)

        # Step 5.5: Chord detection (needed for arrangement)
        cb("分析和弦…", 75)
        # Detect tempo from MIDI for accurate chord window sizing
        detected_bpm = 120.0
        try:
            midi_temp = pretty_midi.PrettyMIDI(str(clean_midi_path))
            detected_bpm = midi_temp.estimate_tempo()
            if detected_bpm <= 0 or detected_bpm > 300:
                detected_bpm = 120.0
        except Exception:
            detected_bpm = 120.0

        try:
            chords = detect_chords(str(clean_midi_path), bpm=detected_bpm)
            chord_line = format_chord_line(chords)
        except Exception:
            chords = []
            chord_line = ""

        # Step 6: Piano arrangement (optional)
        do_arrange = options.get("arrange", False)
        arrange_style = options.get("style", "broken")
        arrange_diff = options.get("difficulty", "medium")

        if do_arrange and chords:
            cb(f"编曲中·{STYLES.get(arrange_style, {}).get('name', arrange_style)}…", 85)
            try:
                arranged_path = output_dir / "arranged.mid"
                arrange_piano(
                    str(clean_midi_path),
                    str(arranged_path),
                    style=arrange_style,
                    difficulty=arrange_diff,
                    bpm=detected_bpm,
                )
                clean_midi_path = arranged_path  # Use arranged version for sheet music
            except Exception as e:
                print(f"Arrangement skipped: {e}")

        # Step 7: Convert to MusicXML (AFTER arrangement so it uses arranged MIDI)
        cb("生成五线谱…", 95)
        musicxml_path = output_dir / "score.musicxml"
        midi_to_musicxml(clean_midi_path, musicxml_path)

        # Step 8: Done
        cb("完成", 100)
        midi_info = get_midi_info(clean_midi_path)

        # Resolve engine name for display
        engine_display = model_choice
        if model_choice == "aria-amt":
            engine_display = "aria-amt"
        elif model_choice == "basic-pitch":
            engine_display = "basic-pitch"
        elif model_choice == "simple":
            engine_display = "simple"
        else:
            # auto mode — resolve what was actually used
            if is_cloud_available():
                engine_display = "aria-amt (cloud)"
            else:
                engine_display = "basic-pitch"

        return {
            "task_id": task_id,
            "status": "completed",
            "midi_url": f"/api/v1/export/{task_id}/midi",
            "musicxml_url": f"/api/v1/export/{task_id}/musicxml",
            "engine": engine_display,
            "chord_line": chord_line,
            "chords": chords[:8],
            "arranged": do_arrange,
            "style": arrange_style if do_arrange else None,
            "metadata": {**meta, **midi_info, "original_filename": original_filename},
            "percent": 100,
            "stage": "完成",
        }

    except Exception as e:
        cb("失败", 0)
        return {
            "task_id": task_id,
            "status": "failed",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "percent": 0,
            "stage": "错误",
        }


def _run_pipeline(
    task_id: str,
    source_type: str,
    source_path: str | None = None,
    source_url: str | None = None,
    options: dict | None = None,
) -> dict:
    """
    Full transcription pipeline: audio → MIDI → MusicXML.
    Works in both sync (DEV_MODE) and async (Celery) modes.
    """
    return _run_pipeline_with_progress(
        task_id=task_id,
        source_type=source_type,
        source_path=source_path,
        source_url=source_url,
        options=options,
    )


def _acquire_audio(
    task_id: str,
    source_type: str,
    source_path: str | None,
    source_url: str | None,
) -> Path:
    """Get audio file from upload, URL, or recording."""
    if source_type == "file" and source_path:
        return Path(source_path)

    elif source_type == "url" and source_url:
        output_dir = get_output_dir(task_id)
        info = download_audio(source_url, output_dir)
        return Path(info["file_path"])

    elif source_type == "recording" and source_path:
        return Path(source_path)

    else:
        raise ValueError(f"Invalid source: type={source_type}, path={source_path}, url={source_url}")


# Celery task wrapper (used in production with Redis broker)
@celery_app.task(bind=True, name="transcribe_audio_task")
def transcribe_audio_task(
    self,
    task_id: str,
    source_type: str,
    source_path: str | None = None,
    source_url: str | None = None,
    options: dict | None = None,
) -> dict:
    """Celery-bound wrapper. For sync execution, call _run_pipeline directly."""
    return _run_pipeline(
        task_id=task_id,
        source_type=source_type,
        source_path=source_path,
        source_url=source_url,
        options=options,
    )

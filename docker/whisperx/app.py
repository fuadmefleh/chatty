"""SCAFFOLD - see Dockerfile's header comment for context.

Implements the /transcribe contract expected by
src/core/stt/whisperx_http.py: transcription + segment-level speaker labels
work end-to-end via whisperx + pyannote diarization. Per-speaker voice
EMBEDDING extraction (the speaker_embeddings field, which feeds
skills/speakers/'s voice-roster auto-matching) is intentionally left as a
TODO stub - filling it in requires pulling per-segment embeddings out of the
pyannote pipeline (e.g. via its embedding sub-model), which varies enough by
pyannote/whisperx version that it's left for a deployer to wire up against
their own installed versions rather than guessed here.
"""
import os
import tempfile
from pathlib import Path

import whisperx
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

app = FastAPI()

DEVICE = os.environ.get("STT_LOCAL_DEVICE", "cpu")
COMPUTE_TYPE = "int8" if DEVICE == "cpu" else "float16"
MODEL_SIZE = os.environ.get("STT_LOCAL_MODEL_SIZE", "base")
HUGGINGFACE_TOKEN = os.environ.get("HUGGINGFACE_TOKEN")

_model = whisperx.load_model(MODEL_SIZE, DEVICE, compute_type=COMPUTE_TYPE)
_diarize_model = None
if HUGGINGFACE_TOKEN:
    _diarize_model = whisperx.DiarizationPipeline(use_auth_token=HUGGINGFACE_TOKEN, device=DEVICE)


@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form("en"),
    diarize: str = Form("false"),
):
    with tempfile.NamedTemporaryFile(suffix=Path(file.filename).suffix or ".m4a", delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        audio = whisperx.load_audio(tmp_path)
        result = _model.transcribe(audio, language=language)

        segments = result.get("segments") or []
        speaker_embeddings = None

        if diarize.lower() == "true" and _diarize_model is not None:
            align_model, align_metadata = whisperx.load_align_model(
                language_code=result["language"], device=DEVICE
            )
            result = whisperx.align(segments, align_model, align_metadata, audio, DEVICE)
            diarize_segments = _diarize_model(tmp_path)
            result = whisperx.assign_word_speakers(diarize_segments, result)
            segments = result.get("segments") or []

            # TODO: extract a per-speaker-label embedding vector here (e.g.
            # via pyannote's embedding model over each speaker's segments)
            # and populate speaker_embeddings as {label: [floats]}. Left
            # unimplemented in this scaffold - see module docstring.
            speaker_embeddings = {}

        text = " ".join(s.get("text", "").strip() for s in segments).strip()

        return JSONResponse({
            "text": text,
            "segments": segments,
            "speaker_embeddings": speaker_embeddings,
        })
    finally:
        os.unlink(tmp_path)

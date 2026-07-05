# SCAFFOLD, NOT A FINISHED COMPONENT.
#
# src/core/stt/whisperx_http.py POSTs multipart {file, language, diarize} to
# /transcribe and expects back {"text": str, "segments": [{start,end,speaker,
# text}, ...], "speaker_embeddings": {label: [floats]}} - the
# speaker_embeddings field specifically (feeding skills/speakers/'s voice
# roster auto-matching) is NOT part of any generic WhisperX API wrapper found
# at the time this scaffold was written (checked several public
# whisperx-api-server-style images - none emit voice embeddings in this
# shape). app.py below stubs the endpoint and wires up whisperx + pyannote,
# but the diarization -> per-speaker-embedding extraction logic needs to be
# filled in against your own WhisperX/pyannote setup before this is usable.
#
# Enable via: docker compose --profile whisperx up -d whisperx
# and set STT_ENGINE_URL=http://whisperx:8003 in .env.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn python-multipart whisperx pyannote.audio

COPY app.py /app/app.py

EXPOSE 8003
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8003"]

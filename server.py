import os
import tempfile
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, PlainTextResponse
from faster_whisper import WhisperModel


MODEL_SIZE = os.getenv("MODEL_SIZE", "large-v3")
DEVICE = os.getenv("DEVICE", "cuda")
COMPUTE_TYPE = os.getenv("COMPUTE_TYPE", "float16")
BEAM_SIZE = int(os.getenv("BEAM_SIZE", "5"))

app = FastAPI(title="Local Faster-Whisper Server")

print(f"Loading model: {MODEL_SIZE}, device={DEVICE}, compute_type={COMPUTE_TYPE}")
model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
print("Model loaded.")


def format_timestamp(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours = milliseconds // 3_600_000
    milliseconds %= 3_600_000
    minutes = milliseconds // 60_000
    milliseconds %= 60_000
    secs = milliseconds // 1000
    milliseconds %= 1000
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"


def segments_to_srt(segments: list[dict]) -> str:
    output = []
    for index, seg in enumerate(segments, start=1):
        start = format_timestamp(seg["start"])
        end = format_timestamp(seg["end"])
        text = seg["text"].strip()
        output.append(f"{index}\n{start} --> {end}\n{text}\n")
    return "\n".join(output)


def segments_to_text(segments: list[dict]) -> str:
    return "\n".join(seg["text"].strip() for seg in segments)


async def transcribe_file(
    file: UploadFile,
    language: Optional[str] = None,
    response_format: str = "json",
):
    suffix = os.path.splitext(file.filename or "")[1] or ".audio"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(await file.read())
        temp_path = temp_file.name

    try:
        language = None if language in (None, "", "auto") else language
        segments_generator, info = model.transcribe(
            temp_path,
            language=language,
            task="transcribe",
            beam_size=BEAM_SIZE,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )

        segments = []
        for segment in segments_generator:
            segments.append(
                {
                    "start": float(segment.start),
                    "end": float(segment.end),
                    "text": segment.text.strip(),
                }
            )

        text = segments_to_text(segments)

        if response_format == "srt":
            return PlainTextResponse(
                segments_to_srt(segments),
                media_type="text/plain; charset=utf-8",
            )

        if response_format == "text":
            return PlainTextResponse(
                text,
                media_type="text/plain; charset=utf-8",
            )

        return JSONResponse(
            {
                "text": text,
                "language": info.language,
                "duration": info.duration,
                "segments": segments,
            }
        )

    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": MODEL_SIZE,
        "device": DEVICE,
        "compute_type": COMPUTE_TYPE,
    }


@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    response_format: str = Form("json"),
):
    return await transcribe_file(file, language, response_format)


@app.post("/v1/audio/transcriptions")
async def openai_compatible_transcriptions(
    file: UploadFile = File(...),
    model: str = Form("whisper-1"),
    language: Optional[str] = Form(None),
    response_format: str = Form("json"),
):
    return await transcribe_file(file, language, response_format)

"""Evidence file validation, private storage and text extraction.

Uploaded files are untrusted: we check the extension, the file signature (magic bytes)
and the size, store them under a random name outside any web-served folder, and never
execute them."""
from __future__ import annotations

import hashlib
import logging
import re
import secrets
import shutil
import subprocess
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from xml.etree import ElementTree

from .errors import ApiError

log = logging.getLogger("haq.evidence")

# extension -> (kind, canonical mime)
ALLOWED = {
    "jpg": ("image", "image/jpeg"), "jpeg": ("image", "image/jpeg"),
    "png": ("image", "image/png"), "webp": ("image", "image/webp"),
    "pdf": ("document", "application/pdf"),
    "docx": ("document", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "txt": ("document", "text/plain"),
    "wav": ("audio", "audio/wav"), "mp3": ("audio", "audio/mpeg"), "m4a": ("audio", "audio/mp4"),
    "ogg": ("audio", "audio/ogg"), "webm": ("audio", "audio/webm"), "opus": ("audio", "audio/ogg"),
    "mp4": ("video", "video/mp4"), "mov": ("video", "video/quicktime"),
}
MEDIA_KINDS = {"audio", "video"}


def _sig_ok(ext: str, head: bytes) -> bool:
    if ext in ("jpg", "jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext == "png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext == "webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if ext == "pdf":
        return head.startswith(b"%PDF-")
    if ext == "docx":
        return head.startswith(b"PK\x03\x04")
    if ext == "wav":
        return head[:4] == b"RIFF" and head[8:12] == b"WAVE"
    if ext == "mp3":
        return head.startswith(b"ID3") or (len(head) > 1 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0)
    if ext in ("m4a", "mp4", "mov"):
        return head[4:8] in (b"ftyp", b"moov", b"wide", b"mdat", b"free")
    if ext in ("ogg", "opus"):
        return head.startswith(b"OggS")
    if ext == "webm":
        return head.startswith(b"\x1a\x45\xdf\xa3")
    if ext == "txt":
        if b"\x00" in head:
            return False
        try:
            head.decode("utf-8")
        except UnicodeDecodeError as e:
            # a multi-byte character may be cut at the buffer edge
            return e.start >= len(head) - 4
        return True
    return False


def safe_display_name(name: str) -> str:
    """Keep the original name for display only (never used as a path)."""
    base = re.split(r"[\\/]", name or "")[-1]
    base = re.sub(r"[\x00-\x1f<>:\"|?*]", "_", base).strip(" .")
    return (base or "file")[:150]


@dataclass
class StoredFile:
    storage_name: str
    original_name: str
    ext: str
    kind: str
    mime_type: str
    size_bytes: int
    sha256: str


def store_upload(stream: BinaryIO, original_name: str, storage_dir: Path, max_bytes: int, max_media_bytes: int) -> StoredFile:
    display = safe_display_name(original_name)
    ext = display.rsplit(".", 1)[-1].lower() if "." in display else ""
    if ext not in ALLOWED:
        raise ApiError(415, "unsupported_file_type",
                       "This file type is not supported. Use a photo (JPG, PNG, WebP), PDF, Word (DOCX), text, audio (MP3, WAV, M4A, OGG, WebM) or video (MP4, MOV).")
    kind, mime = ALLOWED[ext]
    limit = max_media_bytes if kind in MEDIA_KINDS else max_bytes
    storage_name = secrets.token_hex(16) + "." + ext
    target = storage_dir / storage_name
    tmp = storage_dir / (storage_name + ".part")
    h = hashlib.sha256()
    size = 0
    head = b""
    try:
        with open(tmp, "xb") as out:
            while True:
                chunk = stream.read(1024 * 256)
                if not chunk:
                    break
                if len(head) < 64:
                    head += chunk[: 64 - len(head)]
                size += len(chunk)
                if size > limit:
                    raise ApiError(413, "file_too_large", f"This file is larger than {limit // (1024 * 1024)} MB.")
                h.update(chunk)
                out.write(chunk)
        if size == 0:
            raise ApiError(422, "empty_file", "This file is empty. The upload may not have finished — please try again.")
        if not _sig_ok(ext, head):
            raise ApiError(415, "file_content_mismatch", "The file's contents do not match its type. It may be damaged or renamed.")
        tmp.rename(target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return StoredFile(storage_name, display, ext, kind, mime, size, h.hexdigest())


# --- Text extraction --------------------------------------------------------------------------

class ExtractionUnsupported(Exception):
    pass


MAX_EXTRACT_CHARS = 20000


def extract_text(path: Path, ext: str, ocr_languages: str = "eng", stt_model: str = "off") -> str:
    if ext == "txt":
        return path.read_text(encoding="utf-8", errors="replace")[:MAX_EXTRACT_CHARS]
    if ext == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        parts = []
        for page in reader.pages[:50]:
            parts.append(page.extract_text() or "")
            if sum(map(len, parts)) > MAX_EXTRACT_CHARS:
                break
        text = "\n".join(parts).strip()
        if not text:
            raise ExtractionUnsupported("No text layer in this PDF (it may be a scan). OCR for scanned PDFs is not enabled.")
        return text[:MAX_EXTRACT_CHARS]
    if ext == "docx":
        return _docx_text(path)[:MAX_EXTRACT_CHARS]
    if ext in ("jpg", "jpeg", "png", "webp"):
        return _ocr(path, ocr_languages)[:MAX_EXTRACT_CHARS]
    if stt_model != "off" and stt_available():
        return _transcribe(path, stt_model)[:MAX_EXTRACT_CHARS]
    raise ExtractionUnsupported("Audio and video are stored safely but not transcribed: no speech-to-text service is configured.")


# --- Offline speech-to-text (Whisper via faster-whisper) --------------------------------------

_stt_lock = threading.Lock()
_stt_models: dict = {}


def stt_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:
        return False


def load_stt_model(name: str):
    """Load (and on first use download) the Whisper model. Runs on the CPU, works offline afterwards."""
    with _stt_lock:
        if name not in _stt_models:
            from faster_whisper import WhisperModel
            _stt_models[name] = WhisperModel(name, device="cpu", compute_type="int8")
        return _stt_models[name]


def _transcribe(path: Path, model_name: str) -> str:
    model = load_stt_model(model_name)
    with _stt_lock:  # one transcription at a time keeps memory low on small laptops
        segments, _info = model.transcribe(str(path), beam_size=5)
        text = " ".join(seg.text.strip() for seg in segments).strip()
    if not text:
        raise ExtractionUnsupported("No speech could be heard in this recording. It is still attached.")
    return text


def _docx_text(path: Path) -> str:
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(path) as z:
        info = z.getinfo("word/document.xml")
        if info.file_size > 20 * 1024 * 1024:  # zip-bomb guard
            raise ValueError("document.xml too large")
        root = ElementTree.fromstring(z.read(info))
    paras = []
    for p in root.iter(ns + "p"):
        paras.append("".join(t.text or "" for t in p.iter(ns + "t")))
    return "\n".join(x for x in paras if x.strip())


def ocr_available() -> bool:
    return shutil.which("tesseract") is not None


def _ocr(path: Path, languages: str) -> str:
    if not ocr_available():
        raise ExtractionUnsupported("Text could not be read from this image: OCR (Tesseract) is not installed on the server.")
    # Pass the path as an argument, never through a shell.
    proc = subprocess.run(["tesseract", str(path), "stdout", "-l", languages],
                          capture_output=True, timeout=120, check=False)
    if proc.returncode != 0:
        raise RuntimeError("OCR failed")
    text = proc.stdout.decode("utf-8", errors="replace").strip()
    if not text:
        raise ExtractionUnsupported("No readable text was found in this image.")
    return text


# --- Finding amounts and dates (suggestions only) ------------------------------------------

_AMOUNT_RE = re.compile(
    r"(?:₹|rs\.?|inr|rupees?)\s*([0-9]{1,3}(?:,[0-9]{2,3})+(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)"
    r"|(?<![/\-.\d])([0-9]{1,3}(?:,[0-9]{2,3})+(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)\s*(?:/-|rs\.?|rupees?|inr)",
    re.IGNORECASE,
)
_MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
_DATE_RES = [
    re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"),
    re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4}|\d{2})\b"),
    re.compile(rf"\b(\d{{1,2}})\s+({_MONTHS})[a-z]*\.?,?\s+(\d{{4}})\b", re.IGNORECASE),
]
_MONTH_NUM = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def find_amounts(text: str) -> list[str]:
    found: list[str] = []
    for m in _AMOUNT_RE.finditer(text or ""):
        raw = (m.group(1) or m.group(2) or "").replace(",", "")
        try:
            val = f"{float(raw):.2f}"
        except ValueError:
            continue
        if val not in found and float(val) > 0:
            found.append(val)
    return found[:20]


def find_dates(text: str) -> list[str]:
    """Return ISO dates (YYYY-MM-DD). Numeric dates are read as day/month/year (Indian convention)."""
    out: list[str] = []

    def add(y: int, m: int, d: int):
        if y < 100:
            y += 2000
        if 1990 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31:
            iso = f"{y:04d}-{m:02d}-{d:02d}"
            if iso not in out:
                out.append(iso)

    t = text or ""
    for m in _DATE_RES[0].finditer(t):
        add(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    for m in _DATE_RES[1].finditer(t):
        add(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    for m in _DATE_RES[2].finditer(t):
        add(int(m.group(3)), _MONTH_NUM[m.group(2).lower()[:3]], int(m.group(1)))
    return out[:20]


_INJECTION_RE = re.compile(
    r"ignore (all |any )?(previous|prior|above) instructions|system prompt|you are now|disregard (the )?(rules|instructions)|reveal .*(password|token|other users)",
    re.IGNORECASE,
)


def looks_like_instructions(text: str) -> bool:
    return bool(_INJECTION_RE.search(text or ""))

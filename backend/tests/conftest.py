import io
import os
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path

# Make importing app.main (which builds a module-level app) harmless during tests.
_IMPORT_DIR = tempfile.mkdtemp(prefix="haq-import-")
os.environ.setdefault("HAQ_DATA_DIR", _IMPORT_DIR)
os.environ["APP_ENV"] = "test"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.security import rate_limiter  # noqa: E402


@pytest.fixture
def settings(tmp_path):
    s = Settings()
    s.app_env = "test"
    s.data_dir = tmp_path
    s.secret_key = "test-secret-key-" + "x" * 40
    s.cors_origins = []
    s.storage_dir.mkdir(parents=True, exist_ok=True)
    return s


@pytest.fixture
def app(settings):
    rate_limiter.reset()
    rate_limiter.enabled = False
    a = create_app(settings)
    yield a
    rate_limiter.enabled = True


@pytest.fixture
def client(app):
    return TestClient(app)


def latest_code(app, email):
    with app.state.ctx.db.connection() as c:
        row = c.execute("SELECT body FROM email_outbox WHERE to_email = ? ORDER BY rowid DESC LIMIT 1", (email,)).fetchone()
    import re
    return re.search(r"\b(\d{6})\b", row["body"]).group(1)


class Party:
    def __init__(self, client, token, user):
        self.client, self.token, self.user = client, token, user

    @property
    def h(self):
        return {"Authorization": f"Bearer {self.token}"}

    def get(self, url, **kw):
        return self.client.get(url, headers={**self.h, **kw.pop("headers", {})}, **kw)

    def post(self, url, **kw):
        return self.client.post(url, headers={**self.h, **kw.pop("headers", {})}, **kw)

    def patch(self, url, **kw):
        return self.client.patch(url, headers={**self.h, **kw.pop("headers", {})}, **kw)

    def put(self, url, **kw):
        return self.client.put(url, headers={**self.h, **kw.pop("headers", {})}, **kw)


def make_party(client, app, role, email=None, verify=True, **extra):
    email = email or f"{role}-{uuid.uuid4().hex[:8]}@example.com"
    body = {"email": email, "password": "Passw0rd!", "display_name": extra.pop("display_name", role.title()), **extra}
    r = client.post(f"/api/auth/register/{role}", json=body)
    assert r.status_code == 201, r.text
    p = Party(client, r.json()["token"], r.json()["user"])
    if verify:
        r = p.post("/api/auth/verify-email", json={"code": latest_code(app, email)})
        assert r.status_code == 200, r.text
        p.user = r.json()["user"]
    return p


@pytest.fixture
def worker(client, app):
    return make_party(client, app, "worker", display_name="Asha Devi", phone="9876543210")


@pytest.fixture
def employer(client, app):
    return make_party(client, app, "employer", display_name="Ravi Kumar", business_name="Kumar Builders")


def full_draft(worker, employer_email, **overrides):
    r = worker.post("/api/claims", json={"description": "I worked 18 days on the building site but was only paid part of my wages.", "language": "en"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    fields = {"employer_name": "Kumar Builders", "employer_email": employer_email, "work_type": "Construction helper",
              "start_date": "2026-09-01", "end_date": "2026-09-20", "amount_claimed": "6400",
              "requested_outcome": "Please pay the remaining wages."}
    fields.update(overrides)
    r = worker.patch(f"/api/claims/{cid}", json=fields)
    assert r.status_code == 200, r.text
    return cid


def submit(worker, cid, shared=(), key=None):
    text = worker.get(f"/api/claims/{cid}").json()["complaint_text"] or "This is my complaint about unpaid wages for September."
    return worker.post(f"/api/claims/{cid}/submit", json={"confirm": True, "complaint_text": text, "shared_evidence_ids": list(shared)},
                       headers={"Idempotency-Key": key or uuid.uuid4().hex})


# --- sample files -------------------------------------------------------------------------

def make_pdf(text: str) -> bytes:
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode() + o + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n".encode())
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return out.getvalue()


def make_docx(paragraphs: list[str]) -> bytes:
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{ns}"><w:body>{body}</w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


MP3_BYTES = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 200
WAV_BYTES = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 100
PNG_HEADER = b"\x89PNG\r\n\x1a\n"

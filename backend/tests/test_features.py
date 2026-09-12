from __future__ import annotations

import io
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.auth import create_access_token
from app.main import app
from app.services.embeddings import embedding_service


def test_resume_upload_magic_bytes_and_path_masking():
    with TestClient(app) as client:
        # Register and login to get access token
        reg = client.post(
            "/auth/register",
            json={"email": "pdf_test@example.com", "password": "secure-password-123"},
        )
        assert reg.status_code == 201
        token = client.post(
            "/auth/login",
            json={"email": "pdf_test@example.com", "password": "secure-password-123"},
        ).json()["access_token"]

        headers = {"Authorization": f"Bearer {token}"}

        # 1. Invalid magic bytes rejection
        fake_pdf = io.BytesIO(b"Hello world, I am not really a PDF file")
        res_fake = client.post(
            "/resumes",
            headers=headers,
            files={"file": ("resume.pdf", fake_pdf, "application/pdf")},
        )
        assert res_fake.status_code == 422
        assert "magic bytes" in res_fake.json()["error"]["message"]

        # 2. Valid authentic PDF magic bytes acceptance
        valid_pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
        valid_pdf = io.BytesIO(valid_pdf_content)
        res_valid = client.post(
            "/resumes",
            headers=headers,
            files={"file": ("candidate_resume.pdf", valid_pdf, "application/pdf")},
        )
        assert res_valid.status_code == 202
        data = res_valid.json()
        assert data["status"] == "pending"
        resume_id = data["resume_id"]

        # 3. Verify server local filesystem path is never exposed in API list/detail responses
        resumes_list = client.get("/resumes", headers=headers).json()
        target = next((r for r in resumes_list if r["id"] == resume_id), None)
        assert target is not None
        # Must only contain the filename/UUID, never C:\ or /app/uploads
        assert not target["filename"].startswith("C:")
        assert not target["filename"].startswith("/")
        assert not target["filename"].startswith("./")
        assert target["filename"].endswith(".pdf")


def test_websocket_subprotocol_authentication():
    with TestClient(app) as client:
        reg = client.post(
            "/auth/register",
            json={"email": "ws_user@example.com", "password": "secure-password-123"},
        )
        assert reg.status_code == 201
        user_id = reg.json()["id"]
        token = create_access_token(user_id)

        # 1. Valid handshake via Sec-WebSocket-Protocol subprotocols ['access_token', '<JWT>']
        with client.websocket_connect(
            "/ws/notifications",
            subprotocols=["access_token", token],
        ) as websocket:
            init_msg = websocket.receive_json()
            assert init_msg == {"type": "connected", "channel": "notifications"}

            # Send ping
            websocket.send_json({"type": "ping"})
            pong_msg = websocket.receive_json()
            assert pong_msg == {"type": "pong"}

        # 2. Rejection on invalid token
        try:
            with client.websocket_connect(
                "/ws/notifications",
                subprotocols=["access_token", "invalid.jwt.token"],
            ) as websocket:
                websocket.receive_text()
                assert False, "Should have disconnected"
        except WebSocketDisconnect as exc:
            assert exc.code == 4401


def test_embeddings_singleton_and_semantic_expansion():
    # Verify singleton instance
    assert embedding_service is not None
    # Test ontology expansion
    expanded = embedding_service.expand_skills(["React", "FastAPI"])
    assert any(name == "React" and src == "resume" for name, src, _ in expanded)
    assert any(name == "FastAPI" and src == "resume" for name, src, _ in expanded)
    # Should include semantically related skills
    semantic_skills = [name for name, src, _ in expanded if src == "semantic"]
    assert len(semantic_skills) > 0

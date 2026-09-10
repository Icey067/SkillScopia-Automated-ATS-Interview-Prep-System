from pathlib import Path

from app.services.resume_processor import dummy_extract_text


def test_dummy_extraction_includes_filename_and_demo_skills(tmp_path: Path):
    resume = tmp_path / "candidate.pdf"
    resume.write_bytes(b"%PDF-demo")

    text = dummy_extract_text(str(resume))

    assert "candidate.pdf" in text
    assert "FastAPI" in text

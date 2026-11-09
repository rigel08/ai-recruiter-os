import pytest

from app.services.parsing import UnreadableDocument, extract_text
from tests.helpers import make_docx, make_pdf


def test_reads_pdf_text():
    text = extract_text("cv.PDF", make_pdf(["Asha Verma", "Skills: Python (FastAPI), SQL"]))
    assert "Asha Verma" in text
    assert "Python (FastAPI)" in text


def test_reads_docx_text():
    text = extract_text("cv.docx", make_docx(["Asha Verma", "Skills: Python"]))
    assert text.splitlines() == ["Asha Verma", "Skills: Python"]


def test_reads_txt():
    assert extract_text("cv.txt", "Asha Verma".encode()) == "Asha Verma"


@pytest.mark.parametrize("file_name", ["cv.doc", "cv.png", "cv"])
def test_unsupported_types_explain_why(file_name):
    with pytest.raises(UnreadableDocument, match="Upload PDF, DOCX or TXT"):
        extract_text(file_name, b"anything")


@pytest.mark.parametrize("file_name", ["cv.pdf", "cv.docx"])
def test_damaged_files_are_unreadable(file_name):
    with pytest.raises(UnreadableDocument):
        extract_text(file_name, b"this is not really that kind of file")

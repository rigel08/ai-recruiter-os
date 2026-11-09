"""Turn uploaded resume files into plain text."""

from __future__ import annotations

import io
import zipfile
from pathlib import PurePath
from xml.etree import ElementTree

from pypdf import PdfReader

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".txt")

# Caps the size of the DOCX's text part once unzipped, so a small
# malicious file can't expand into gigabytes of memory.
_MAX_DOCX_XML_BYTES = 20 * 1024 * 1024
_WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class UnreadableDocument(Exception):
    """The file can't be turned into text. The message says why, for a recruiter."""


def extract_text(file_name: str, data: bytes) -> str:
    extension = PurePath(file_name).suffix.lower()
    if extension == ".pdf":
        return _pdf_text(data)
    if extension == ".docx":
        return _docx_text(data)
    if extension == ".txt":
        return data.decode("utf-8", errors="replace")
    shown = extension or "files without an extension"
    raise UnreadableDocument(f"{shown} isn't supported. Upload PDF, DOCX or TXT.")


def _pdf_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            # Many "protected" PDFs only restrict printing and open with an
            # empty password. Anything else really is locked.
            reader.decrypt("")
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # pypdf raises many different types on damaged files
        raise UnreadableDocument("The PDF couldn't be opened. It may be damaged or password-protected.") from exc
    return "\n".join(pages)


def _docx_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            info = archive.getinfo("word/document.xml")
            if info.file_size > _MAX_DOCX_XML_BYTES:
                raise UnreadableDocument("The DOCX file is too large to read.")
            root = ElementTree.fromstring(archive.read(info))
    except UnreadableDocument:
        raise
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
        raise UnreadableDocument("The DOCX file couldn't be opened. It may be damaged.") from exc
    paragraphs = (
        "".join(node.text or "" for node in paragraph.iter(f"{_WORD_NS}t"))
        for paragraph in root.iter(f"{_WORD_NS}p")
    )
    return "\n".join(paragraphs)

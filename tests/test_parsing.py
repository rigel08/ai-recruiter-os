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


# ---------- M2: two-column PDFs ----------

from app.services.facts import extract_facts  # noqa: E402
from app.services.parsing import split_columns  # noqa: E402
from tests.helpers import make_two_column_pdf  # noqa: E402

LEFT = ["Divya Rao", "Senior Software Engineer", "divya.rao@example.com", "Mobile: 9000000101", "Skills",
        "Java, Spring Boot, SQL", "PostgreSQL, Docker, AWS", "Notice Period", "30 Days", "Current CTC: 19.5 LPA"]
RIGHT = ["Summary", "Backend engineer with 7 years of", "experience building payment services",
         "in Java and Spring Boot.", "Work history", "Senior Engineer, Northgate Payments",
         "Hyderabad (2022 to present)", "Expected CTC: 24 LPA", "Current Location: Hyderabad",
         "Total Experience: 7 Years 2 Months"]


@pytest.mark.parametrize("row_by_row", [False, True])
def test_two_column_pdf_is_read_column_by_column(row_by_row):
    text = extract_text("cv.pdf", make_two_column_pdf(LEFT, RIGHT, row_by_row=row_by_row))
    assert text.splitlines() == LEFT + RIGHT
    facts = {field: fact.value for field, fact in extract_facts(text).items()}
    # Before this fix the row-by-row file lost the notice period: its label and value were on
    # lines shared with the other column.
    assert facts == {"phone": "+91 90000 00101", "total_experience": 7.17, "notice_period": 30.0,
                     "current_ctc": 19.5, "expected_ctc": 24.0, "current_location": "Hyderabad"}


def test_single_column_pdf_is_left_alone():
    lines = ["Asha Verma", "asha@example.com", "Notice Period: 30 Days", "Built reporting dashboards in Power BI."]
    assert extract_text("cv.pdf", make_pdf(lines)).splitlines() == lines


def test_label_and_value_rows_are_not_mistaken_for_columns():
    table = "\n".join(f"{label:<30}{value}" for label, value in [
        ("Name", "Asha Verma"), ("Notice Period", "30 Days"), ("Current CTC", "8 LPA"), ("Expected CTC", "11 LPA"),
        ("Location", "Pune"), ("Total Experience", "4 Years"), ("Phone", "9000000000"), ("Email", "asha@example.com")])
    assert split_columns(table) is None


def test_a_few_right_aligned_dates_are_not_columns():
    page = "\n".join(["Asha Verma", "Senior Analyst, Northwind Ltd" + " " * 20 + "Jan 2021 to Mar 2024",
                      "Built dashboards for the finance team.", "Analyst, Tailspin Ltd" + " " * 28 + "Jun 2018 to Dec 2020",
                      "Cleaned and modelled sales data.", "Skills: SQL, Excel, Power BI"])
    assert split_columns(page) is None


def test_doc_and_photo_files_say_what_to_do():
    with pytest.raises(UnreadableDocument, match="open it in Word"):
        extract_text("cv.doc", b"anything")
    with pytest.raises(UnreadableDocument, match="photo or scan"):
        extract_text("cv.jpg", b"anything")

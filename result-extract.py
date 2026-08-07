#!/usr/bin/env python3
"""
FBISE SSC-II Result Gazette → clean JSON
Handles two-column layout properly using PyMuPDF blocks
"""

import re
import json
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

import fitz  # pymupdf

# ------------------------------------------------------------------
PDF_PATH = r"C:\Users\BOSS\Downloads\analyze-result-master\10th-result-pages.pdf"
OUTPUT_JSON = "students.json"
OUTPUT_JSONL = "students.jsonl"
# ------------------------------------------------------------------
grades = ["A1", "A", "B", "C", "D", "E"]

ALLOWED_SUBJECTS = {"ARB", "B-M", "BIO", "C-S", "C-S (HIC)", "CHE", "CIV", "CNM", "CPD", "E-A",
    "E-C (HIC)", "E-C", "E-E", "ECO", "EDU", "F-A", "F-A (HIC)", "FFN", "FRN",
    "GEO", "HN", "HOP", "HPE (HIC)", "HPE", "I-H", "I-S", "IAD", "ISL (HIC)",
    "ISL", "L-S", "MTH", "OHE (HIC)", "OHE", "P-A", "P-C", "P-E", "PCL", "PER",
    "PHI", "PHY", "PSY", "SHE", "SOC", "STS", "U-C (HIC)", "U-C", "U-E",
    "ARB:I", "ARB:II", "B-S", "BIO:I", "BIO:II", "BNK", "C-G", "C-S:I",
    "C-S:I (HIC)", "C-S:II", "C-S:II (HIC)", "CAH", "CDV", "CHE:I", "CHE:II",
    "CIV:I", "CIV:II", "CST", "E-A:I", "E-A:II", "E-C:I (HIC)", "E-C:I",
    "E-C:II (HIC)", "E-C:II", "E-E:I", "E-E:II", "ECO:I", "ECO:II", "EDU:I",
    "EDU:II", "F-A:I", "F-A:I (HIC)", "F-A:II", "F-A:II (HIC)", "GEO:I",
    "GEO:II", "HMI", "HOP:I", "HOP:II", "HPE:I (HIC)", "HPE:I",
    "HPE:II (HIC)", "HPE:II", "I-H:I", "I-S:I", "I-S:II", "IH1:II", "IH2:II",
    "L-S:I", "L-S:II", "MTH:I", "MTH:II", "OHE:I (HIC)", "OHE:I",
    "OHE:II (HIC)", "OHE:II", "P-A:I", "P-A:II", "PCL:I", "PCL:II", "PER:I",
    "PER:II", "PHI:I", "PHI:II", "PHY:I", "PHY:II", "PRE", "PST", "PST (HIC)",
    "PSY:I", "PSY:II", "SOC:I", "SOC:II", "STS:I", "STS:II", "U-C:I (HIC)",
    "U-C:I", "U-C:II (HIC)", "U-C:II", "U-E:I", "U-E:II",
    "AMD:I", "AMD:I (HIC)", "AMD:II", "AMD:II (HIC)", "C-G:I", "C-G:II",
    "C-T:I", "C-T:II", "DMF:I", "DMF:II", "E-L:I", "E-L:II", "E-W:I",
    "E-W:II", "EDU:I (HIC)", "EDU:II (HIC)", "EHE:I (HIC)", "EHE:I",
    "EHE:II (HIC)", "EHE:II", "F-N:I", "F-N:II", "G-M:I", "G-M:II", "G-S:I",
    "G-S:I (HIC)", "G-S:II", "G-S:II (HIC)", "GOP:I", "GOP:II", "I-H:II",
    "IKH-I", "IKH-II", "ISL-I (HIC)", "ISL-I", "ISL-II", "ISL-II (HIC)",
    "MAT:I", "MAT:I (HIC)", "MAT:II", "MAT:II (HIC)", "PST-I",
    "PST-I (HIC)", "PST-II", "PST-II (HIC)", "WWF:I", "WWF:II",
    "AMD", "BUD", "CHR", "CT-", "DFA", "DMF", "E-W", "EDU (HIC)", "ETM",
    "FN-", "G-M", "G-S", "G-S (HIC)", "GOP", "HE-", "MAT", "MAT (HIC)",
    "SDN", "SKM", "THQ",}
ALLOWED_REMARKS = {
    "Absent", "All Paper(s) Cancelled", "Cancelled", "Change of Subject",
    "Not Printable", "Problem Case (O.L.)", "R-Later",
    "Rel. Paper(s) Cancelled", "RW", "RW-Elg.", "RW-Elg. & S.E", "RW-Fee",
    "RW-Fee & S.E", "Special Exam.", "Add. Cleared", "Add. N. Cleared",
    "Result Imp.", "Result Not Imp.", "IBCC Case",
}
ALLOWED_GRADES = {"A1", "A", "B", "C", "D", "E", "F"}
INSTITUTION_KEYWORDS = (
    "SCHOOL", "COLLEGE", "EDUCATORS", "MADRISSA", "MADRASSAH",
    "ACADEMY", "INSTITUTE", "PUBLIC", "MODEL", "GRAMMAR", "EDUCATION",
    "HIGHER", "SECONDARY", "SYSTEM", "SYSTEMS", "APS", "BOYS", "GIRLS",
    "SCHOOLS", "EDUCATIONAL", "EDUCATIONALS", "CAMPUS", "INSTITUITE",
    "EX-PRIVATE CANDIDATES", "EX PRIVATE CANDIDATES", "ALJAMIA", "JAMIA",
    "EDUCASIA", "JAMIATUL", "EDUCATOR", "CENTRE", "DAR", "ULOOM",
    "LEARNING", "FOUNDATION", "UNIVERSITY", "BLOOMFIELD", "IQRA",
    "MADRASA", "AKADEMIE", "ACADMY", "ADVANCED", "STUDIES", "COLLEGIATE",
    "SCIENCES", "SCHOOLZ", "CADETCOLLEGE", "SCHOOLING", "TCF", "ISLAMABAD",
    "CANTT", "DISTT", "TEHSIL", "GOVT", "GOVERNMENT", "FG", "F.G.",
    "ARMY", "OPF", "FATIMIYAH", "RIGHT SCHOOL"
)

STATUS = {
    "PASS",
    "FAIL",
    "COMPT.",
    "ABSENT",
}

VALID_GRADES = {"A1", "A", "B", "C", "D", "E", "F"}


def is_institution_line(line: str) -> bool:
    line = line.strip()
    if not line:
        return False

    # Never treat a line that starts with a roll number as institution
    if re.match(r"^\d{6,7}\b", line):
        return False

    line_upper = line.upper()

    # Explicit section
    if "EX-PRIVATE" in line_upper:
        return True

    # Must contain at least one strong school keyword
    strong_keywords = (
        "SCHOOL", "COLLEGE", "ACADEMY", "INSTITUTE", "MADRAS", "MADRASA",
        "JAMIA", "UNIVERSITY", "CAMPUS", "FOUNDATION", "CADET",
        "HIGHER SECONDARY", "PUBLIC SCHOOL", "GOVT", "GOVERNMENT",
        "ARMY PUBLIC", "OPF PUBLIC", "FATIMIYAH", "RIGHT SCHOOL",
        "F.G.", "FG ", "TCF"
    )
    if not any(kw in line_upper for kw in strong_keywords):
        return False

    # Reject pure board headers
    if "FEDERAL BOARD" in line_upper or "INTERMEDIATE AND SECONDARY" in line_upper:
        return False

    # Reject lines that look like student names (too short or contain status)
    if len(line.split()) <= 3 and not re.search(r"\(\d{3,5}\)", line):
        return False

    return True


def normalize_status(raw: str) -> str:
    s = raw.upper().strip().rstrip(".")
    mapping = {
        "COMPT": "COMPT.",
        "COMP": "COMPT.",
        "RW-FEE": "RW-Fee",
        "RW-ELG": "RW-Elg.",
        "RW": "RW",
        "R-LATER": "R-Later",
        "ADD N CLEARED": "ADD. N. CLEARED",
        "ADD CLEARED": "ADD. CLEARED",
        "ADD.N.CLEARED": "ADD. N. CLEARED",
        "ADD.CLEARED": "ADD. CLEARED",
    }
    return mapping.get(s, raw.strip())


def clean_institution(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip()
    name = re.sub(r"\s+\d{4}\s*$", "", name)
    return name

def parse_one_student(roll_no: str, text: str, institution: Optional[str]) -> Dict[str, Any]:
    text = re.sub(r"\s+", " ", text).strip()

    # ----------------------------------------------------------
    # Fix glued status (YOUSAFZPASS, BUKHACOMPT., etc.)
    # ----------------------------------------------------------
    glued = re.search(r"([A-Z])(PASS|COMPT\.?|ABSENT|FAIL)\b", text, re.I)
    if glued:
        text = text[:glued.start(2)] + " " + text[glued.start(2):]

    # ----------------------------------------------------------
    # 1. Detect only the 4 main statuses
    # ----------------------------------------------------------
    status = None
    status_match = None

    priority = [
        (r"\b(COMPT\.?|COMP\.?)\b", lambda m: "COMPT."),
        (r"\b(PASS)\b",             lambda m: "PASS"),
        (r"\b(ABSENT)\b",           lambda m: "Absent"),
        (r"\b(FAIL)\b",             lambda m: "FAIL"),
    ]

    for pattern, status_func in priority:
        m = re.search(pattern, text, re.I)
        if m:
            status = status_func(m)
            status_match = m
            break

    if status is None:
        # No main status → try to extract special remarks (RW-Fee, etc.)
        special = re.search(
            r"\b(RW\s*-?\s*FEE\.?|RW\s*-?\s*ELG\.?|RW|R\s*-?\s*LATER|Add\.?\s*N?\.?\s*Cleared)\b",
            text, re.I
        )
        if special:
            name = text[:special.start()].strip() or None
            remarks = special.group(0).strip()
            if name:
                name = re.sub(r"\s+", " ", name).strip() or None
            return {
                "roll_no": roll_no,
                "name": name,
                "status": None,
                "marks": None,
                "grade": None,
                "remarks": remarks,
                "institution": institution,
            }
        else:
            return {
                "roll_no": roll_no,
                "name": text or None,
                "status": None,
                "marks": None,
                "grade": None,
                "remarks": None,
                "institution": institution,
            }

    # ----------------------------------------------------------
    # Main status found
    # ----------------------------------------------------------
    before = text[:status_match.start()].strip()
    after  = text[status_match.end():].strip()

    # Clean name
    name = before
    if name:
        name = re.sub(r"\b(PASS|FAIL|COMPT\.?|ABSENT)\b", "", name, flags=re.I)
        name = re.sub(r"[A-Z]-?[A-Z]:[IVX]+\s*", "", name)
        name = re.sub(r"\s+", " ", name).strip() or None

    # ----------------------------------------------------------
    # Extract marks / grade / remarks
    # ----------------------------------------------------------
    marks = None
    grade = None
    remarks = None

    m = re.match(r"^(\d{1,4})\s*([A-F]1?)?\b\s*(.*)$", after, re.I)
    if m:
        marks = int(m.group(1))
        if m.group(2) and m.group(2).upper() in VALID_GRADES:
            grade = m.group(2).upper()
        remarks = m.group(3).strip() or None
    else:
        m = re.match(r"^([A-F]1?)\b\s*(.*)$", after, re.I)
        if m and m.group(1).upper() in VALID_GRADES:
            grade = m.group(1).upper()
            remarks = m.group(2).strip() or None
        else:
            remarks = after or None

    # Safety: pure number in remarks → marks
    if remarks and marks is None:
        m = re.fullmatch(r"(\d{1,4})", remarks.strip())
        if m:
            marks = int(m.group(1))
            remarks = None

    # Safety: remarks starts with a grade
    if remarks and grade is None:
        m = re.match(r"^([A-F]1?)\b\s*(.*)$", remarks, re.I)
        if m and m.group(1).upper() in VALID_GRADES:
            grade = m.group(1).upper()
            remarks = m.group(2).strip() or None

    # ----------------------------------------------------------
    # Special rescues for PASS + number hidden in remarks
    # ----------------------------------------------------------
    if status == "PASS" and marks is None and remarks:
        # IBCC Case 217
        m = re.search(r"(IBCC\s+Case)\s+(\d{1,4})\b", remarks, re.I)
        if m:
            marks = int(m.group(2))
            remarks = m.group(1).strip()
        else:
            # Result Imp. / Result Not Imp.
            m = re.search(r"(Result\s+(?:Not\s+)?Imp\.?)\s+(\d{1,4})\b", remarks, re.I)
            if m:
                marks = int(m.group(2))
                remarks = m.group(1).strip()
            else:
                # Add. Cleared 93
                m = re.search(r"(Add\.?\s*N?\.?\s*Cleared)\s+(\d{1,4})\b", remarks, re.I)
                if m:
                    marks = int(m.group(2))
                    remarks = m.group(1).strip()
                else:
                    # Plain number at start
                    m = re.match(r"^(\d{1,4})\b(.*)$", remarks.strip())
                    if m:
                        marks = int(m.group(1))
                        remarks = m.group(2).strip() or None

    # ----------------------------------------------------------
    # Final remarks cleaning (Whitelist + rules)
    # ----------------------------------------------------------
    if remarks:
        remarks = remarks.lstrip(". ").strip()
        remarks = re.sub(r"\s+", " ", remarks).strip()

        cleaned_parts = []

        # First: protect multi-word special remarks
        multi_word_remarks = [
            "IBCC Case",
            "Add. Cleared", "Add. N. Cleared",
            "Result Imp.", "Result Not Imp.",
            "RW-Elg.", "RW-Fee",
            "RW-Elg. & S.E", "RW-Fee & S.E",
            "All Paper(s) Cancelled",
            "Rel. Paper(s) Cancelled",
            "Problem Case (O.L.)",
            "Change of Subject",
            "Special Exam.",
            "Not Printable",
        ]

        remaining = remarks
        for phrase in multi_word_remarks:
            pattern = re.compile(re.escape(phrase), re.I)
            if pattern.search(remaining):
                cleaned_parts.append(phrase)
                remaining = pattern.sub(" ", remaining).strip()

        # Now process remaining single tokens
        tokens = remaining.split()
        for token in tokens:
            token_clean = token.strip(".,;()")
            upper = token_clean.upper()

            # Never keep grades in remarks
            if upper in VALID_GRADES:
                continue

            # Keep allowed single-word special remarks
            if (token_clean in ALLOWED_REMARKS or
                upper in {r.upper() for r in ALLOWED_REMARKS}):
                cleaned_parts.append(token_clean)
                continue

            # Subjects ONLY allowed when status is COMPT.
            if status == "COMPT.":
                if (token_clean in ALLOWED_SUBJECTS or
                    upper in {s.upper() for s in ALLOWED_SUBJECTS}):
                    cleaned_parts.append(token_clean)

        remarks = " ".join(cleaned_parts).strip() or None

    return {
        "roll_no": roll_no,
        "name": name,
        "status": status,
        "marks": marks,
        "grade": grade,
        "remarks": remarks,
        "institution": institution,
    }
def process_column_text(column_text: str, current_institution: Optional[str]) -> Tuple[List[Dict], Optional[str]]:
    """Parse one column (left or right) of a page."""
    students = []
    lines = column_text.splitlines()
    i = 0
    n = len(lines)
    institution = current_institution

    while i < n:
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        if is_institution_line(line):
            institution = clean_institution(line)
            i += 1
            continue

        m = re.match(r"^(\d{6,7})\s*(.*)$", line)
        if not m:
            i += 1
            continue

        roll_no = m.group(1)
        rest = m.group(2).strip()

        # Collect continuation lines carefully
        block = []
        if rest:
            block.append(rest)

        j = i + 1
        while j < n:
            nxt = lines[j].strip()
            if not nxt:
                j += 1
                continue

            # Hard stop conditions
            if re.match(r"^\d{6,7}\b", nxt):
                break
            if is_institution_line(nxt):
                break

            block.append(nxt)
            j += 1

        full = " ".join(block)
        student = parse_one_student(roll_no, full, institution)
        students.append(student)
        i = j

    return students, institution

def extract_students_from_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    doc = fitz.open(pdf_path)
    all_students = []
    current_institution = None

    for page_num, page in enumerate(doc, 1):
        # Get text blocks with positions
        blocks = page.get_text("blocks", sort=True)  # list of (x0,y0,x1,y1,text, ...)

        if not blocks:
            continue

        # Find approximate middle of the page to split left / right columns
        page_width = page.rect.width
        mid_x = page_width * 0.48   # slightly left of center works better for these gazettes

        left_blocks = []
        right_blocks = []

        for b in blocks:
            x0, y0, x1, y1, text, *_ = b
            text = text.strip()
            if not text:
                continue
            # decide column by the left edge of the block
            if x0 < mid_x:
                left_blocks.append((y0, text))
            else:
                right_blocks.append((y0, text))

        # sort by vertical position
        left_blocks.sort(key=lambda t: t[0])
        right_blocks.sort(key=lambda t: t[0])

        left_text = "\n".join(t[1] for t in left_blocks)
        right_text = "\n".join(t[1] for t in right_blocks)

        # parse left column
        left_students, current_institution = process_column_text(left_text, current_institution)
        all_students.extend(left_students)

        # parse right column
        right_students, current_institution = process_column_text(right_text, current_institution)
        all_students.extend(right_students)

    doc.close()
    return all_students


def main():
    pdf = Path(PDF_PATH)
    if not pdf.exists():
        print(f"ERROR: PDF not found → {pdf}")
        return

    print(f"Processing (two-column aware): {pdf}")
    students = extract_students_from_pdf(str(pdf))
    print(f"Found {len(students):,} student records")

    with open(OUTPUT_JSONL, "w", encoding="utf-8") as f:
        for s in students:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"Wrote → {OUTPUT_JSONL}")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(students, f, ensure_ascii=False, indent=2)
    print(f"Wrote → {OUTPUT_JSON}")



if __name__ == "__main__":
    main()
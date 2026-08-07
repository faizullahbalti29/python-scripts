#!/usr/bin/env python3
"""
Extract INSTITUTION WISE RESULT PERFORMANCE tables from FBISE SSC-II Result Gazette PDF
and save as clean structured JSON.

Handles watermark noise (single letters/digits inserted by vertical text).
"""

import pdfplumber
import json
import re
import sys
from pathlib import Path

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------
PDF_PATH = "12-institutions.pdf"
OUTPUT_JSON = "12_institutions.json"
# ------------------------------------------------------------

def clean_line(line: str) -> str:
    """Remove watermark single-character noise and normalize spaces."""
    # Remove isolated single letters / dots that are not part of words
    line = re.sub(r'(?<=\s)[a-zA-Z.](?=\s)', ' ', line)
    line = re.sub(r'(?<=\s)[a-zA-Z.](?=\d)', ' ', line)
    line = re.sub(r'(?<=\d)[a-zA-Z.](?=\s)', ' ', line)
    # Remove trailing single letter after institution name
    line = re.sub(r'\s+[a-zA-Z.]$', '', line)
    # Collapse multiple spaces
    line = re.sub(r'\s+', ' ', line).strip()
    # print("printing lines:",line)
    return line


def extract_numbers(text: str) -> list:
    """Extract numbers (int or float) from a cleaned data line."""
    # Keep only digits, dots and spaces
    cleaned = re.sub(r'[^\d.\s]', ' ', text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
   
    nums = []
    for tok in cleaned.split():
        if re.fullmatch(r'\d+\.\d+', tok):
            nums.append(float(tok))
        elif re.fullmatch(r'\d+', tok):
            nums.append(int(tok))
    # print(f"Extracting numbers from: '{nums}'")
    return nums


def process_pdf(pdf_path: Path) -> list:
    records = []
    current_code = ""
    current_name = ""

    def _normalize_group_key(name: str) -> str:
        """Normalize group display name into kebab-case key: 'Science General' -> 'science-general'"""
        n = name.replace(':', '').strip()
        n = re.sub(r'\s+', ' ', n)
        n = n.lower().strip()
        n = n.replace(' ', '-')
        n = re.sub(r'[^a-z0-9\-]', '', n)
        return n

    anomalies = []

    def _report_anomaly(kind: str, page: int, line: str, extra: str = ""):
        entry = {"kind": kind, "page": page, "line": line}
        if extra:
            entry["extra"] = extra
        anomalies.append(entry)
        print(f"ANOMALY [{kind}] page {page}: {line} {extra}")

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        # print(f"📄 Processing {total_pages} pages...")

        for page_num, page in enumerate(pdf.pages, 1):
            # show progress per page
            print(f"Processing page {page_num}/{total_pages}", flush=True)

            text = page.extract_text() or ""
            raw_lines = [l.strip() for l in text.splitlines() if l.strip()]

            for raw in raw_lines:
                line = clean_line(raw)

                # Skip headers / titles
                if any(kw in line.upper() for kw in [
                    "FEDERAL BOARD", "RESULT GAZETTE", "INSTITUTION WISE",
                    "GRADE WISE", "INSTITUTION / GROUP", "FBISE - COMPUTER"
                ]):
                    continue
                if re.fullmatch(r'[a-zA-Z.]?', line) or len(line) < 3:
                    continue

                # ---- Institution header: starts with 3-5 digit code ----
                m = re.match(r'^(\d{3,5})\s+(.+)$', line)
                if m:
                    # print("institution matched: ",m)
                    current_code = m.group(1)
                    current_name = m.group(2).strip()
                    # Sometimes a trailing digit from watermark remains
                    current_name = re.sub(r'\s+\d+$', '', current_name).strip()
                    continue
                # ---- Data rows: group lines (SCIENCE / HUMANITIES / PRE-MEDICAL / Total etc.) ----
                # Maintain a current_record for the active institution and store per-group stats
                GROUPS = ["SCIENCE", "HUMANITIES", "TOTAL", "PRE-MEDICAL", "PRE-ENGINEERING", "COMMERCE", "GENERAL", "SCIENCE GENERAL","PRE-HOME ECONOMICS"]

                # If we have an explicit code header, ensure a current record exists
                if current_code and len(current_code) >= 3:
                    # initialize current_record if not present or mismatched
                    if not records or records[-1].get("code") != current_code or records[-1].get("institution") != current_name:
                        current_record = {
                            "code": current_code,
                            "institution": current_name,
                            "groups": {}
                        }
                        records.append(current_record)
                    else:
                        current_record = records[-1]

                    # Try match group line like "SCIENCE ..." or "Total : ..."
                    m = re.match(r'^(SCIENCE|HUMANITIES|Total\s*:|TOTAL)\s*(.*)$', line, re.I)
                    if m:
                        raw_group = m.group(1)
                        group = raw_group.replace(':', '').strip().title()
                        nums = extract_numbers(m.group(2))
                        if len(nums) < 14:
                            _report_anomaly("group_incomplete", page_num, line, f"group={group}")
                            continue
                        while len(nums) < 15:
                            nums.append(0)
                        nums = nums[:15]
                        group_stats = {
                            "enrolled": int(nums[0]),
                            "absent": int(nums[1]),
                            "appd": int(nums[2]),
                            "rl": int(nums[3]),
                            "ufm": int(nums[4]),
                            "fail": int(nums[5]),
                            "pass": int(nums[6]),
                            "grades": {
                                "A1": int(nums[7]),
                                "A":  int(nums[8]),
                                "B":  int(nums[9]),
                                "C":  int(nums[10]),
                                "D":  int(nums[11]),
                                "E":  int(nums[12]),
                            },
                            "pass_percentage": float(nums[13]),
                            "gpa": float(nums[14]),
                        }
                        # normalize key (kebab-case)
                        key = _normalize_group_key(group)
                        current_record["groups"][key] = group_stats
                        continue

                # If we reach here, either no numeric code was found earlier or the line may be an institution name or group without a code
                word_counts = len(line.split())
                if word_counts < 3:
                    if line != "G Pass":
                        _report_anomaly("short_line", page_num, line)
                        continue
                else:
                    first_token = line.split()[0].upper()
                    # If the line starts with a known group, treat it as a group for the current (last) institution
                    if first_token in GROUPS:
                        if not records:
                            # group line with no institution context
                            _report_anomaly("group_without_institution", page_num, line)
                            continue
                        current_record = records[-1]
                        # normalize group name and extract numbers from rest
                        gm = re.match(r'^(?P<group>[A-Za-z\- ]+)\s*:??\s*(?P<rest>.*)$', line)
                        if not gm:
                            _report_anomaly("group_parse_fail", page_num, line)
                            continue
                        raw_group = gm.group('group')
                        group = raw_group.strip().title()
                        rest = gm.group('rest')
                        nums = extract_numbers(rest)
                        if len(nums) < 14:
                            _report_anomaly("group_incomplete", page_num, line, f"group={group}")
                            continue
                        while len(nums) < 15:
                            nums.append(0)
                        nums = nums[:15]
                        group_stats = {
                            "enrolled": int(nums[0]),
                            "absent": int(nums[1]),
                            "appd": int(nums[2]),
                            "rl": int(nums[3]),
                            "ufm": int(nums[4]),
                            "fail": int(nums[5]),
                            "pass": int(nums[6]),
                            "grades": {
                                "A1": int(nums[7]),
                                "A":  int(nums[8]),
                                "B":  int(nums[9]),
                                "C":  int(nums[10]),
                                "D":  int(nums[11]),
                                "E":  int(nums[12]),
                            },
                            "pass_percentage": float(nums[13]),
                            "gpa": float(nums[14]),
                        }
                        key = _normalize_group_key(group)
                        current_record["groups"][key] = group_stats
                        continue
                    else:
                        # line looks like an institution name without code — start a new record
                        current_code = ""
                        current_name = line
                        current_record = {
                            "code": current_code,
                            "institution": current_name,
                            "groups": {}
                        }
                        records.append(current_record)
                        continue
                        
                        
   
    return records


def main():
    pdf_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(PDF_PATH)
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(OUTPUT_JSON)

    if not pdf_path.exists():
        print(f"❌ PDF not found: {pdf_path}")
        sys.exit(1)

    records = process_pdf(pdf_path)

    if not records:
        print("⚠️  No records extracted. Something is wrong with the parser.")
        sys.exit(1)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    # Quick stats
    institutions = len({r["code"] for r in records})
    print(f"\n✅ Done!")
    print(f"   Records   : {len(records)}")
    # print(f"   Institutions: {institutions}")
    print(f"   Output    : {out_path.resolve()}")


if __name__ == "__main__":
    main()

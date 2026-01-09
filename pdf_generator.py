#!/usr/bin/env python3
"""
report_card_app_v11_pdfgen_v2.py

Updated report generator for BIGS Campus Report System.

Features implemented (per user request):
 - Admin options: Bulk (all grades) or Selected grade generation (PDF or JPG).
 - Class-teacher option: generate reports (PDF or JPG) for assigned grade(s).
 - Teachers: can download admin-generated zips for their grades.
 - Report layout refinements:
     * Signature labels row moved 20 mm to the right (so labels align under signatures).
     * Comments/Status/Prepared-on block moved 10 mm up.
     * Class Teacher Comments read from skills.csv -> Remarks column.
     * Section B title simplified to "Section B — Holistic Development".
     * Header rows in both tables are bold and uppercase.
     * Student name printed as: "Firstname Lastname — Grade 10State" with numeric grade bolded.
     * Section B score column centered.
     * Section A columns TE, CE, Scored, Full Marks, Percentage, Grade centered.
     * Subject column width increased by 5 mm. Column "Total Scored" renamed to "Scored".
 - Creates per-grade reports in report_data/grade_X/reports and a zip file.
 - Optional JPG creation (requires pdf2image + poppler).
 - Callable as a module: from report_card_app_v11_pdfgen_v2 import generate_reports_admin, generate_reports_for_grade, generate_all_reports
 - Runnable as script: will generate all grades (bulk) using frame image if present.
"""

import io
import os
import csv
import zipfile
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.lib.utils import ImageReader

# Try pdf2image for JPG conversion
try:
    from pdf2image import convert_from_bytes
    PDF2IMAGE_AVAILABLE = True
except Exception:
    PDF2IMAGE_AVAILABLE = False

# --- Paths and constants ---
BASE_DIR = Path(__file__).resolve().parent
REPORT_DATA = BASE_DIR / "report_data"
ADMIN_DIR = REPORT_DATA / "admin"
TOTAL_ROW_COLOR = "#C7B994"
FIXED_SKILLS = ["Remembering", "Understanding", "Applying", "Regularity & Punctuality", "Neatness & Orderliness"]

# Ensure structure exists
for p in (REPORT_DATA, ADMIN_DIR):
    p.mkdir(parents=True, exist_ok=True)

# --- Utilities: CSV read/write ---


def read_csv_dict(path: Path) -> List[dict]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fieldnames: List[str], rows: List[dict]):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


# --- Lookup helpers for grade/remarks scales ---


def lookup_grade(pct: float, grade_scale_rows: List[dict]) -> str:
    """Return grade string from grade_scale.csv based on percentage (pct)."""
    if not grade_scale_rows:
        return ""
    for g in grade_scale_rows:
        # Support headers having either Min%/Max% or Min/Max
        try:
            mn = safe_float(g.get("Min%", g.get("Min", 0)))
            mx = safe_float(g.get("Max%", g.get("Max", 100)))
            if mn <= pct <= mx:
                return (g.get("Grade", "") or g.get("Score", "")).strip()
        except Exception:
            continue
    return ""


def lookup_remark(score, remarks_rows: List[dict]) -> str:
    """Return remark text for a given skill score (score is usually integer)."""
    if not remarks_rows:
        return ""
    for r in remarks_rows:
        # Accept "Score" -> "Remark"
        s = r.get("Score")
        if s is not None and s != "":
            try:
                if int(float(s)) == int(float(score)):
                    return r.get("Remark", "")
            except Exception:
                continue
    # fallback: try Min/Max ranges (if provided)
    for r in remarks_rows:
        try:
            mn = safe_float(r.get("Min", r.get("Min%", 0)))
            mx = safe_float(r.get("Max", r.get("Max%", 5)))
            if mn <= safe_float(score, -999) <= mx:
                return r.get("Remark", "")
        except Exception:
            continue
    return ""


# --- PDF generation function (core) ---


def create_report_pdf_bytes_v2(
    student_name: str,
    grade_label: str,
    academic_rows: List[dict],
    skills_rows: List[dict],
    comments: str,
    parent_sig_path: Optional[Path],
    grade_scale_rows: List[dict],
    remarks_scale_rows: List[dict],
    frame_image: Optional[Path],
    prepared_on: Optional[str] = None,
    principal_sign_path: Optional[str] = None,
    class_teacher_sign_path: Optional[str] = None,
) -> bytes:
    """
    Create a single student's report PDF bytes with new layout rules.

    - frame_image (Path) if provided will be drawn edge-to-edge (A4).
    - academic_rows: list of dicts with keys: Subject, TE, CE, Full_Marks, Remarks
    - skills_rows: list of dicts with keys: Skill, Score, Remark (Remark may be overwritten from remarks_scale)
    """

    buf = io.BytesIO()
    width, height = A4
    c = canvas.Canvas(buf, pagesize=A4)

    # Draw full-page frame image (edge-to-edge) if exists
    if frame_image and Path(frame_image).exists():
        try:
            img = ImageReader(str(frame_image))
            c.drawImage(img, 0, 0, width=width, height=height, preserveAspectRatio=True, mask="auto")
        except Exception:
            pass

    # Content area - centered inside frame (you can tweak margins)
    left_margin = 18 * mm
    right_margin = 18 * mm
    top_margin = 65 * mm
    bottom_margin = 18 * mm
    content_width = width - left_margin - right_margin

    # Header: student name and grade. Name Title Case; Grade numeric bold
    y = height - top_margin + 6 * mm
    # Student name (uppercase)
    student_title = student_name.upper()
    c.setFont("Helvetica-Bold", 14)
    c.drawString(left_margin, y, student_title)


    # Grade label: e.g., "Grade 10" or "Grade 6"
    # We need to bold the numeric portion only. Find digits in grade_label
    grade_text = grade_label or ""
    # If grade_label contains digits, bold that number
    import re

    m = re.search(r"(\d+)", grade_text)
    if m:
        prefix = grade_text[: m.start()].strip()     # e.g., "Grade"
        number = m.group(1)                          # e.g., "10"
        suffix = grade_text[m.end():].strip()        # e.g., "State"

        # Convert suffix (e.g., "state") to uppercase
        if suffix:
            suffix = suffix.upper()

            from reportlab.pdfbase.pdfmetrics import stringWidth

            # Right-align entire constructed label
            full_grade_text = f"{prefix} {number}{('-' + suffix) if suffix else ''}".strip()
            total_width = stringWidth(full_grade_text, "Helvetica", 14)
            x_start = width - right_margin - total_width

            # Draw prefix (e.g., "Grade")
            c.setFont("Helvetica", 14)
            c.drawString(x_start, y, prefix)

            # Compute width of prefix + space
            prefix_width = stringWidth(prefix + " ", "Helvetica", 14)

            # Draw numeric (bold)
            c.setFont("Helvetica-Bold", 14)
            c.drawString(x_start + prefix_width, y, number)

            # Draw hyphen + suffix (normal font)
            num_width = stringWidth(number, "Helvetica-Bold", 14)
            c.setFont("Helvetica", 14)
        if suffix:
            c.drawString(x_start + prefix_width + num_width, y, f"-{suffix}")
    else:
        c.setFont("Helvetica", 14)
        c.drawRightString(width - right_margin, y, grade_text)

    y -= 10 * mm

    # Prepare totals for overall percentage/status
    total_scored = 0.0
    total_full = 0.0
    for r in academic_rows:
        # Only include in total if marks are present (not None)
        # We assume if TE is None, the subject hasn't been graded yet.
        te_val = r.get("TE")
        ce_val = r.get("CE")
        
        if te_val is None and ce_val is None:
            continue
            
        # Treat None as 0 for calculation if one is present but not other? 
        # Or just treat as 0. Let's safe_float it for the sum if at least one is present.
        te = safe_float(te_val, 0)
        ce = safe_float(ce_val, 0)
        full = safe_float(r.get("Full_Marks", 100))
        
        total_scored += (te + ce)
        total_full += full
        
    overall_pct = (total_scored / total_full * 100) if total_full else 0.0
    status_text = "PASSED" if overall_pct >= 40 else "FAILED"

    # --- Section A: Academic Performance ---
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left_margin, y, "Section A — Academic Performance")
    y -= 6 * mm

    # Build table data
    # Header row uppercase & bold
    header = ["Subject", "TE", "CE", "Scored", "Full Marks", "Percentage", "Grade", "Teacher's Remarks"]
    header = [h.upper() for h in header]
    subj_table_data = [header]

    # subject column width increase by +5 mm relative baseline
    # We'll compute column widths proportional to content_width
    # Base widths (as fractions of content_width) approximated
    # We'll allocate more to remarks and subject.
    # Start with fractions and then convert to mm; we will add 5mm to subject
    fractions = [0.18, 0.07, 0.07, 0.10, 0.13, 0.13, 0.07, 0.25]
    # convert fractions to actual widths
    col_widths = [content_width * f for f in fractions]
    # add 5mm to subject column (first column)
    col_widths[0] = col_widths[0] + (5 * mm)
    # recompute rightmost column width to keep total same (subtract from remarks column)
    excess = (content_width - sum(col_widths))
    if abs(excess) > 0.0001:
        # adjust last column
        col_widths[-1] = col_widths[-1] + excess

    # Fill rows
    from reportlab.lib import enums

    for r in academic_rows:
        subj = r.get("Subject", "")
        te_val = r.get("TE")
        ce_val = r.get("CE")
        
        # Check for missing marks (not entered)
        if te_val is None and ce_val is None:
            # Display placeholders
            te_str = "-"
            ce_str = "-"
            scored_str = "-"
            pct_str = "-"
            grade_txt = "-"
            full_str = str(int(safe_float(r.get("Full_Marks", 100)))) # Still show max marks? Or "-"
            full_str = "-" # Let's hide full marks too to indicate "Not evaluated"
        else:
            te = int(safe_float(te_val, 0))
            ce = int(safe_float(ce_val, 0))
            full = int(safe_float(r.get("Full_Marks", 100)))
            scored = te + ce
            pct = (scored / full * 100) if full else 0.0
            grade_txt = lookup_grade(pct, grade_scale_rows)
            
            te_str = str(te)
            ce_str = str(ce)
            scored_str = str(scored)
            full_str = str(full)
            pct_str = f"{pct:.1f}%"

        subj_table_data.append(
            [
                subj,
                te_str,
                ce_str,
                scored_str,
                full_str,
                pct_str,
                grade_txt,
                r.get("Remarks", ""),
            ]
        )

    # TOTAL row
    subj_table_data.append(
        [
            "TOTAL",
            "",
            "",
            str(int(total_scored)),
            str(int(total_full)),
            f"{overall_pct:.1f}%",
            "",
            "",
        ]
    )

    # Create Table
    tbl = Table(subj_table_data, colWidths=col_widths)
    # Table styles: header bold uppercase; center align for specified cols
    ts = TableStyle(
        [
            ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dde2df")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
    )
    # Center-align columns TE(1),CE(2),Scored(3),Full(4),Percentage(5),Grade(6)
    ts.add("ALIGN", (0, 0), (-1, 0), "CENTER")
    ts.add("ALIGN", (1, 1), (6, -1), "CENTER")
    # Left align Subject (0) and Remarks (7)
    ts.add("ALIGN", (0, 1), (0, -2), "LEFT")
    ts.add("ALIGN", (7, 1), (7, -1), "LEFT")
    # Highlight TOTAL row
    last_idx = len(subj_table_data) - 1
    ts.add("BACKGROUND", (0, last_idx), (-1, last_idx), colors.HexColor(TOTAL_ROW_COLOR))
    ts.add("FONTNAME", (0, last_idx), (-1, last_idx), "Helvetica-Bold")
    tbl.setStyle(ts)

    # Draw table
    tbl.wrapOn(c, content_width, height)
    tbl_h = tbl._height
    tbl.drawOn(c, left_margin, y - tbl_h)
    y = y - tbl_h - 8 * mm

    # --- Section B: Holistic Development ---
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left_margin, y, "Section B — Holistic Development")
    y -= 6 * mm

    # Header uppercase & bold
    sb_header = ["SKILLS & WORK HABITS", "SCORE", "REMARKS"]
    sb_header = [h.upper() for h in sb_header]
    skill_table_data = [sb_header]
    for sk in skills_rows:
        skill = sk.get("Skill", "")
        score = sk.get("Score", "")
        # override remark with remarks_scale if available
        rtext = sk.get("Remark", "") or ""
        if remarks_scale_rows:
            lookup = lookup_remark(score, remarks_scale_rows)
            if lookup:
                rtext = lookup
        skill_table_data.append([skill, str(score), rtext])

    # Skill column widths: make it visually similar to section A
    # We'll combine widths for first three subject columns to create the first column width
    skill_col0 = col_widths[0] + col_widths[1] + col_widths[2]
    skill_col1 = col_widths[3]
    skill_col2 = sum(col_widths[4:])
    skill_col_widths = [skill_col0, skill_col1, skill_col2]

    stbl = Table(skill_table_data, colWidths=skill_col_widths)
    st_ts = TableStyle(
        [
            ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dde2df")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
    )
    # Center the score column (second column)
    st_ts.add("ALIGN", (1, 1), (1, -1), "CENTER")
    stbl.setStyle(st_ts)
    stbl.wrapOn(c, content_width, height)
    stbl_h = stbl._height
    stbl.drawOn(c, left_margin, y - stbl_h)
    y = y - stbl_h - 10 * mm

    # --- Comments by Class Teacher, Status and Prepared on ---
    # Move this group 10mm upward relative to previous position (we already reduce y by tables)
    # We'll set baseline at bottom_margin + some offset
    baseline_y = bottom_margin + (48 * mm) + (10 * mm)  # moved 10mm up from prior baseline
    # Print "Class Teacher Comments:" and the comments (source: comments param OR skills.csv remarks)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left_margin, baseline_y, "Class Teacher Comments:")
    c.setFont("Helvetica", 10)
    # Print up to 4 lines
    lines = str(comments or "").splitlines()[:4]
    for i, ln in enumerate(lines):
        c.drawString(left_margin, baseline_y - (i + 1) * 6 * mm, ln)

    # Status and Prepared on (right aligned)
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(width - right_margin, baseline_y, f"Status: {status_text}")
    c.setFont("Helvetica", 10)
    prepared_str = prepared_on if prepared_on else datetime.now().strftime("%d-%m-%Y")
    c.drawRightString(width - right_margin, baseline_y - 7 * mm, f"Prepared on: {prepared_str}")

    # --- Signatures (centered + anchored to bottom margin) ---
    # All 3 signatures (Principal, Class Teacher, Parent) centered horizontally
    # and placed a fixed distance above the bottom of the A4 page.

    bottom_margin = 20 * mm          # Distance from bottom edge of page
    sig_y_base = bottom_margin + 20 * mm  # Vertical baseline for signatures
    sig_width = 40 * mm
    sig_height = 15 * mm
    spacing = 70 * mm                # Horizontal spacing between signatures

    # Center the full signature group horizontally
    group_width = 2 * spacing + sig_width
    page_center_x = width / 2
    group_start_x = page_center_x - group_width / 2  # Leftmost signature X start

    # --- Individual signature & label offsets (fine-tuning) ---
    sig_offsets = {
        "Principal": {"x": 0, "y": 0},
        "Class Teacher": {"x": 0, "y": 0},
        "Parent": {"x": 5, "y": 0},
    }

    # Relative label offsets (below signature images)
    label_offsets = {
        "Principal": {"x": 4, "y": -6},
        "Class Teacher": {"x": 0, "y": -6},
        "Parent": {"x": 4, "y": -6},
    }

    # --- Global fine-tuning (affects all signatures / labels together) ---
    image_global_shift = {"x": -4.5, "y": 3}   # move all signature images together
    label_global_shift = {"x": 10, "y": 3}   # move all labels independently

    labels = ["Principal", "Class Teacher", "Parent"]
    sig_paths = [
        principal_sign_path,
        class_teacher_sign_path,
        Path(parent_sig_path) if parent_sig_path else None,
    ]

    for i, (label, sf) in enumerate(zip(labels, sig_paths)):
        # Compute image position
        x = group_start_x + i * spacing + (sig_offsets[label]["x"] + image_global_shift["x"]) * mm
        y = sig_y_base + (sig_offsets[label]["y"] + image_global_shift["y"]) * mm

        # Draw signature image (if available)
        if sf and Path(sf).exists():
            try:
                img = ImageReader(str(sf))
                c.drawImage(img, x, y, width=sig_width, height=sig_height,
                            preserveAspectRatio=True, mask="auto")
            except Exception:
                pass

        # Draw label text (positioned independently)
        lx = x + (label_offsets[label]["x"] + label_global_shift["x"]) * mm
        ly = y + (label_offsets[label]["y"] + label_global_shift["y"]) * mm
        c.setFont("Helvetica-Bold", 9)
        c.drawString(lx, ly, label)



    c.showPage()
    c.save()
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes


# --- PDF -> JPG conversion helper ---


def pdf_to_jpg_bytes(pdf_bytes: bytes, dpi: int = 200) -> bytes:
    if not PDF2IMAGE_AVAILABLE:
        raise RuntimeError(
            "pdf2image not available; install pdf2image and Poppler (and ensure pdfinfo is in PATH) for JPG conversion."
        )
    images = convert_from_bytes(pdf_bytes, dpi=dpi, fmt="jpeg")
    b = io.BytesIO()
    images[0].save(b, format="JPEG", quality=95)
    return b.getvalue()

# --- Adapter for Database Data ---
def create_report_card_bytes(
    student_name: str,
    student_grade: str,
    subjects_scores: List[dict],
    skills_scores: List[dict],
    teacher_comments: str,
    prepared_by: str,
    header_img_path: Optional[str],
    footer_img_path: Optional[str],
    grade_scales: List[dict],
    principal_sign_path: Optional[str] = None,
    parent_sign_path: Optional[str] = None,
    class_teacher_sign_path: Optional[str] = None,
    background_img_path: Optional[str] = None,
):
    """
    Adapter function to map from database dicts to the v2 generator's expected format.
    
    subjects_scores expects keys: 'Subject', 'TE', 'CE', 'Full_Marks', 'Remarks'
    DB query usually returns: name (subj), te_score, ce_score, te_max_marks, ce_max_marks.
    """
    
    # Map Subject Rows
    mapped_acad = []
    for row in subjects_scores:
        # Check keys and map
        subj = row.get("name") or row.get("Subject")
        te = row.get("te_score") if "te_score" in row else row.get("TE")
        ce = row.get("ce_score") if "ce_score" in row else row.get("CE")
        # Full marks calculation: TE Max + CE Max
        te_max = safe_float(row.get("te_max_marks") or row.get("TE_Full_Marks"), 100)
        ce_max = safe_float(row.get("ce_max_marks") or row.get("CE_Full_Marks"), 0)
        full = te_max + ce_max
        remarks = row.get("Remarks") or row.get("remarks") or ""
        
        mapped_acad.append({
            "Subject": subj,
            "TE": te,
            "CE": ce,
            "Full_Marks": full,
            "Remarks": remarks
        })
        
    # Map Skills
    mapped_skills = []
    for sk in skills_scores:
        mapped_skills.append({
            "Skill": sk.get("skill_name") or sk.get("Skill"),
            "Score": sk.get("score") or sk.get("Score"),
            "Remark": sk.get("remark") or sk.get("Remark")
        })
        
    # Standard Remark Mapping
    def get_skill_remark(score):
        try:
            s_int = int(float(score))
            if s_int == 1: return "BEGINNING"
            if s_int == 2: return "PROGRESSING"
            if s_int == 3: return "ACCOMPLISHED"
            if s_int == 4: return "OUTSTANDING"
        except:
            pass
        return ""

    for ms in mapped_skills:
        if not ms.get("Remark"):
            ms["Remark"] = get_skill_remark(ms.get("Score"))
            
    # Frame Image Logic
    # 1. Use background_img_path if provided (Grade Specific)
    # 2. Fallback to default frame if exists
    final_bg = background_img_path
    if not final_bg:
        def_bg = ADMIN_DIR / "a4_report_card_frame.png"
        if def_bg.exists():
            final_bg = str(def_bg)
    
    return create_report_pdf_bytes_v2(
        student_name=student_name,
        grade_label=student_grade,
        academic_rows=mapped_acad,
        skills_rows=mapped_skills,
        comments=teacher_comments,
        parent_sig_path=parent_sign_path,
        grade_scale_rows=grade_scales,
        remarks_scale_rows=[],
        frame_image=final_bg,
        principal_sign_path=principal_sign_path,
        class_teacher_sign_path=class_teacher_sign_path
    )

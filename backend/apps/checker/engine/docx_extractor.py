from __future__ import annotations
import re
import hashlib
from typing import Optional, Dict, Any, List

from docx import Document

# ---------- helpers ----------
def _norm_text(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s

def _norm_heading_key(s: str) -> str:
    """
    用于匹配结构标题：
    - 去掉前缀编号：'1 ВВЕДЕНИЕ' / '1.2. ' / 'ГЛАВА 1' 等
    - 去掉尾部标点
    - 大写
    """
    s = _norm_text(s)
    s = re.sub(r"^[\dIVXLCDM]+(\.[\dIVXLCDM]+)*[\)\.\-–: ]+", "", s, flags=re.I)
    s = re.sub(r"[\.:\-–\s]+$", "", s)
    return s.upper()
def _text_hash(s: str) -> str:
    # 用于 idx 漂移兜底：固定取前 80 字做 hash
    t = _norm_text(s)[:80].encode("utf-8", errors="ignore")
    return hashlib.sha1(t).hexdigest()[:12]

def _is_heading_style(style_name: Optional[str]) -> bool:
    if not style_name:
        return False
    sn = style_name.lower()
    # 英文/俄文 Word 都可能出现：Heading 1 / Заголовок 1
    return ("heading" in sn) or ("заголовок" in sn)

def _heading_level(style_name: Optional[str]) -> Optional[int]:
    if not style_name:
        return None
    m = re.search(r"(\d+)", style_name)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None

def extract_docx_snapshot(docx_path: str) -> dict:
    """
    MVP 提取：段落文本、段落样式（字体大小、是否居中、是否全大写）、节的页边距、行距。
    注意：docx 没有真实页码，这里用“段落索引/章节锚点”代替；页码用 '?'。
    """
    doc = Document(docx_path)

    # section format (取第一个 section)
    sec = doc.sections[0]
    margins_mm = {
        "left_mm": round(sec.left_margin.mm, 2),
        "right_mm": round(sec.right_margin.mm, 2),
        "top_mm": round(sec.top_margin.mm, 2),
        "bottom_mm": round(sec.bottom_margin.mm, 2),
        "page_width_mm": round(sec.page_width.mm, 2),
        "page_height_mm": round(sec.page_height.mm, 2),
    }

    paragraphs = []
    for i, p in enumerate(doc.paragraphs):
        text = (p.text or "").strip()
        if not text:
            continue
        style_name = p.style.name if p.style is not None else None

        # 取 run 的首个非空字体信息
        font_name = None
        font_size = None
        for r in p.runs:
            if r.text and r.font:
                if r.font.name:
                    font_name = r.font.name
                if r.font.size:
                    font_size = float(r.font.size.pt)
                if font_name or font_size:
                    break

        line_spacing = None
        if p.paragraph_format and p.paragraph_format.line_spacing:
            try:
                line_spacing = float(p.paragraph_format.line_spacing)
            except Exception:
                line_spacing = None
        alignment = p.alignment
        alignment_code = int(alignment) if alignment is not None else None
        alignment_text = str(alignment) if alignment is not None else "None"

        paragraphs.append({
            "idx": i,
            "text": text,
            "text_u": text.upper(),
            "text_hash": _text_hash(text),
            "snippet": text[:120],
            "char_len": len(text),
            "style": style_name,
            "is_heading_style": _is_heading_style(style_name),
            "heading_level": _heading_level(style_name),
            "font_name": font_name,
            "font_size_pt": font_size,
            "is_upper": text.isupper(),
            "line_spacing": line_spacing,
            "alignment": alignment,
            "alignment_text": alignment_text,
            "alignment_code": alignment_code,
        })
        # anchor_map：将“结构标题”映射到段落 idx（多策略：优先 heading style，再兜底靠文本全匹配）
    anchor_map: Dict[str, int] = {}
    for p in paragraphs:
        key = _norm_heading_key(p["text"])
        if not key:
            continue

        # 如果是 heading style，优先收录
        if p["is_heading_style"]:
            anchor_map.setdefault(key, p["idx"])

    # 兜底：没有 heading style 的情况下，收录全大写且短的行（典型 структурные элементы）
    if not anchor_map:
        for p in paragraphs:
            t = p["text"]
            key = _norm_heading_key(t)
            if len(t) <= 80 and t.isupper():
                anchor_map.setdefault(key, p["idx"])

    return {
        "version": "snapshot_v1",
        "margins": margins_mm,
        "paragraphs": paragraphs,
        "anchor_map": anchor_map,  # { "ВВЕДЕНИЕ": 50, ... }
    }

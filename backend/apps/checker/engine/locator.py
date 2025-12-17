# apps/checker/engine/locator.py
from __future__ import annotations
import re
from typing import Optional, Dict, Any, List

def _norm_text(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s

def _norm_heading_key(s: str) -> str:
    s = _norm_text(s)
    s = re.sub(r"^[\dIVXLCDM]+(\.[\dIVXLCDM]+)*[\)\.\-–: ]+", "", s, flags=re.I)
    s = re.sub(r"[\.:\-–\s]+$", "", s)
    return s.upper()

def build_para_index(snapshot: dict) -> dict:
    """为重定位构建索引：hash->idx，upper_text->idx"""
    idx_by_hash = {}
    idx_by_upper = {}
    for p in snapshot.get("paragraphs", []):
        if p.get("text_hash"):
            idx_by_hash.setdefault(p["text_hash"], p["idx"])
        if p.get("text_u"):
            idx_by_upper.setdefault(p["text_u"], p["idx"])
    return {"idx_by_hash": idx_by_hash, "idx_by_upper": idx_by_upper}

def locate_anchor(snapshot: dict, anchor: str) -> Optional[int]:
    amap = snapshot.get("anchor_map", {}) or {}
    key = _norm_heading_key(anchor)
    # return amap.get(key)
    return amap.get((key or "").strip().upper())

def attach_location(
    snapshot: dict,
    issue: Dict[str, Any],
    *,
    anchor: Optional[str] = None,
    para_idx: Optional[int] = None
    ) -> Dict[str, Any]:
    """
    给 issue 打上定位字段（不覆盖已有有效字段）。
    推荐字段：
    - anchor: "ВВЕДЕНИЕ"
    - para_idx: 123
    - snippet: "..."
    - text_hash: "ab12cd..."
    - page: "?"  (docx 无真实页码，先占位)
    """
    out = dict(issue)  # ✅ 不原地污染

    paragraphs: List[dict] = snapshot.get("paragraphs") or []
    idx_map = {p.get("idx"): p for p in paragraphs if p.get("idx") is not None}

    # 1) anchor：只在传入且 issue 没有时写入
    if anchor and not out.get("anchor"):
        out["anchor"] = anchor

    # 2) para_idx：优先显式 para_idx；否则用 anchor 定位；只写入有效 idx
    resolved_idx: Optional[int] = None

    if out.get("para_idx") is not None:
        resolved_idx = out.get("para_idx")
    elif para_idx is not None:
        resolved_idx = para_idx
    elif anchor:
        # locate_anchor 必须返回 int 或 None
        ai = locate_anchor(snapshot, anchor)
        if ai is not None:
            resolved_idx = ai

    if resolved_idx is not None and resolved_idx in idx_map and out.get("para_idx") is None:
        out["para_idx"] = int(resolved_idx)

    # 3) snippet/hash：只有找到段落才填
    p = idx_map.get(out.get("para_idx"))
    if p:
        out.setdefault("snippet", p.get("snippet"))
        out.setdefault("text_hash", p.get("text_hash"))
    else:
        out.setdefault("snippet", None)
        out.setdefault("text_hash", None)

    # 4) 页码：docx 先占位，不覆盖已有 page
    # out.setdefault("page", "?")
    return out

def relocalize_issue(snapshot: dict, issue: Dict[str, Any]) -> Dict[str, Any]:
    """
    idx 漂移兜底：如果 para_idx 找不到了，用 text_hash 或 snippet 重新找。
    """
    paragraphs: List[dict] = snapshot.get("paragraphs", []) or []
    idx_map = {p["idx"]: p for p in paragraphs}
    if issue.get("para_idx") in idx_map:
        return issue  # 仍然有效

    index = build_para_index(snapshot)

    h = issue.get("text_hash")
    if h and h in index["idx_by_hash"]:
        issue["para_idx"] = index["idx_by_hash"][h]
        p = idx_map.get(issue["para_idx"])
        if p:
            issue["snippet"] = p.get("snippet")
        return issue

    # 兜底：用 snippet 的 upper 匹配
    snip = _norm_text(issue.get("snippet") or "")
    if snip:
        key = snip.upper()
        idx = index["idx_by_upper"].get(key)
        if idx is not None:
            issue["para_idx"] = idx
            p = idx_map.get(idx)
            if p:
                issue["text_hash"] = p.get("text_hash")
            return issue

    return issue

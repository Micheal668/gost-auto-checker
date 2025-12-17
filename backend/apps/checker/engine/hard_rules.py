from __future__ import annotations
from typing import Any, Dict, List
from .locator import attach_location
from .docx_extractor import _norm_heading_key
def _map_severity(gost_sev: str) -> str:
    mapping = {"BLOCKER": "HIGH", "MAJOR": "MEDIUM", "MINOR": "LOW", "INFO": "NEED_REVIEW"}
    return mapping.get((gost_sev or "").upper(), "NEED_REVIEW")


def _issue(rule: dict, message: str, suggestion: str, page: str = "?", category: str = "GOST") -> Dict[str, Any]:
    return {
        "page": page,
        "severity": _map_severity(rule.get("severity", "INFO")),
        "category": category,
        "rule_id": rule.get("id"),
        "clause": rule.get("clause"),
        "message": message,
        "suggestion": suggestion,
    }


def _norm(s: str) -> str:
    return (s or "").strip()


def _texts(snapshot: dict) -> List[str]:
    paras = snapshot.get("paragraphs") or []
    out = []
    for p in paras:
        t = _norm(p.get("text", ""))
        if t:
            out.append(t)
    return out


# def _alignment_is_center(alignment_value: Any) -> bool:
#     if alignment_value is None:
#         return False
#     s = str(alignment_value).upper()
#     if "CENTER" in s:
#         return True
#     # 兼容你目前保存的 "1"/"2" 这类
#     return s.strip() in {"1", "2"}
def run_hard_rules(runtime: dict, snapshot: dict) -> list[dict]:
    findings: list[dict] = []
    paragraphs = snapshot["paragraphs"]
    margins = snapshot["margins"]

    # 示例：结构元素 presence（锚点=缺失的标题本身）
    req_titles = None
    sev = "MAJOR"
    for r in runtime.get("rules", []):
        if r.get("op") == "CHECK_STRUCTURE_PRESENCE":
            req_titles = r.get("args", {}).get("required_elements", [])
            sev = r.get("severity", "MAJOR")
            break

    if req_titles:
        text_all_u = set(p["text_u"] for p in paragraphs)
        for title in req_titles:
            if title.upper() not in text_all_u:
                issue = {
                    "severity": "HIGH" if sev == "BLOCKER" else "MEDIUM",
                    "category": "STRUCTURE",
                    "message": f"Отсутствует обязательный структурный элемент: «{title}»",
                    "suggestion": f"Добавьте раздел «{title}» согласно ГОСТ 7.32-2017.",
                }
                # 缺失项没法指向具体段落：只挂 anchor（让前端知道这是“缺结构”）
                findings.append(attach_location(snapshot, issue, anchor=title, para_idx=None))

    # 示例：页边距（属于 document 级，不指向段落）
    target = {"left_mm": 30, "right_mm": 15, "top_mm": 20, "bottom_mm": 20}
    for k, v in target.items():
        real = margins.get(k)
        if real is None:
            continue
        if abs(real - v) > 1.0:
            issue = {
                "severity": "MEDIUM",
                "category": "LAYOUT",
                "message": f"Неверное поле {k}: требуется {v} мм, фактически {real} мм",
                "suggestion": "Откройте параметры страницы и установите поля по ГОСТ.",
            }
            findings.append(attach_location(snapshot, issue, anchor="DOCUMENT", para_idx=None))

    # 示例：字号 < 12，指向具体段落 idx
    for p in paragraphs[:200]:
        fs = p.get("font_size_pt")
        if fs is not None and fs < 12:
            issue = {
                "severity": "LOW",
                "category": "FONT",
                "message": f"Слишком маленький шрифт: {fs} pt.",
                "suggestion": "Установите размер шрифта не менее 12 pt.",
            }
            findings.append(attach_location(snapshot, issue, anchor=None, para_idx=p["idx"]))
            break

    if not findings:
        issue = {
            "severity": "LOW",
            "category": "MVP",
            "message": "Явных нарушений по базовым автоматическим правилам не найдено (MVP-проверка).",
            "suggestion": "Для полного соответствия требуется расширить набор правил и/или включить AI-проверку.",
        }
        findings.append(attach_location(snapshot, issue, anchor="DOCUMENT", para_idx=None))

    return findings
def push_issue(snapshot, issues, rule, issue, *, anchor=None, para_idx=None):
    issue.setdefault("rule_id", rule.get("id"))
    issue.setdefault("clause", rule.get("clause"))
    issues.append(attach_location(snapshot, issue, anchor=anchor, para_idx=para_idx))

# =========================
# 单条规则执行（给 Celery 逐条跑 + 进度条用）
# =========================
def run_rule(snapshot: dict, rule: dict) -> List[dict]:
    op = rule.get("op")
    args = rule.get("args", {}) or {}

    paragraphs = snapshot.get("paragraphs") or []
    margins = snapshot.get("margins") or {}
    all_texts = _texts(snapshot)
    all_upper = {t.upper() for t in all_texts}

    issues: List[dict] = []

    # 4.1 CHECK_STRUCTURE_PRESENCE
    if op == "CHECK_STRUCTURE_PRESENCE":
        required = args.get("required_elements", []) or []
        for title in required:
            t = _norm(title)
            if not t:
                continue
            if t.upper() not in all_upper:
                issues.append(_issue(
                    rule,
                    message=f"Отсутствует обязательный структурный элемент: «{t}».",
                    suggestion=f"Добавьте раздел «{t}» и оформите заголовок по ГОСТ 7.32-2017."
                ))
        return issues

    # 6.1.1 CHECK_PAGE_FORMAT（MVP：字号 + 行距）
    if op == "CHECK_PAGE_FORMAT":
        min_fs = args.get("min_font_size_pt")
        line_spacing_req = args.get("line_spacing")

        # 字号检查
        if min_fs is not None:
            try:
                min_fs = float(min_fs)
            except Exception:
                min_fs = None

        if min_fs is not None:
            for p in paragraphs[:500]:
                fs = p.get("font_size_pt")
                if fs is None:
                    continue
                try:
                    fs = float(fs)
                except Exception:
                    continue
                if fs < min_fs:
                    issues.append(_issue(
                        rule,
                        message=f"Размер шрифта меньше нормы: {fs} pt (< {min_fs} pt). Фрагмент: «{_norm(p.get('text',''))[:80]}».",
                        suggestion=f"Установите размер шрифта не менее {min_fs} pt (обычно 14 pt для основного текста)."
                    ))
                    break

        # 行距检查（只能粗糙）
        if line_spacing_req is not None:
            try:
                line_spacing_req = float(line_spacing_req)
            except Exception:
                line_spacing_req = None

        if line_spacing_req is not None:
            for p in paragraphs[:500]:
                ls = p.get("line_spacing")
                if ls is None:
                    continue
                try:
                    ls = float(ls)
                except Exception:
                    continue
                if abs(ls - line_spacing_req) > 0.2:
                    issues.append(_issue(
                        rule,
                        message=f"Возможное несоответствие межстрочного интервала: {ls} (ожидается ~{line_spacing_req}). Фрагмент: «{_norm(p.get('text',''))[:80]}».",
                        suggestion=f"Проверьте межстрочный интервал и выставьте около {line_spacing_req}.",
                        category="REVIEW"
                    ))
                    break

        return issues

    # 6.1.1.margins CHECK_MARGINS
    if op == "CHECK_MARGINS":
        tol = float(args.get("tolerance_mm", 1.0))
        for k in ("left_mm", "right_mm", "top_mm", "bottom_mm"):
            target = args.get(k)
            if target is None:
                continue
            real = margins.get(k)
            if real is None:
                continue
            try:
                target = float(target)
                real = float(real)
            except Exception:
                continue
            if abs(real - target) > tol:
                issues.append(_issue(
                    rule,
                    message=f"Неверное поле {k}: требуется {target} мм, фактически {real} мм.",
                    suggestion="Откройте параметры страницы и установите поля согласно ГОСТ."
                ))
        return issues

    # 6.2.1 CHECK_HEADING_FORMAT（MVP：只针对结构标题）
    if op == "CHECK_HEADING_FORMAT":
        need_upper = bool(args.get("uppercase", False))
        need_center = bool(args.get("centered", False))
        need_no_dot = bool(args.get("no_trailing_period", False))
        need_new_page = bool(args.get("start_new_page", False))  # MVP: 可先做提示或弱校验

        structural_titles = set(args.get("titles", []) or [])
        if not structural_titles:
            structural_titles = {
                "ТИТУЛЬНЫЙ ЛИСТ","РЕФЕРАТ","СОДЕРЖАНИЕ","ВВЕДЕНИЕ",
                "ОСНОВНАЯ ЧАСТЬ","ЗАКЛЮЧЕНИЕ","СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ","ПРИЛОЖЕНИЯ"
            }

        structural_upper = {s.upper() for s in structural_titles}

        for p in snapshot.get("paragraphs", []):
            t = (p.get("text") or "").strip()
            if not t:
                continue

            t_u = p.get("text_u") or t.upper()
            if t_u not in structural_upper:
                continue

            # ✅ 大小写校验按参数控制
            ok_upper = (p.get("is_upper") is True) if need_upper else True

            # ✅ 居中校验：先用 extractor 的 alignment 字符串兜底
            # align_raw = p.get("alignment")
            # if align_raw is None:
                # align_raw = str(p.get("alignment") or "")
            align_raw = p.get("alignment_text")
            if align_raw is None:
                align_raw = str(p.get("alignment_text") or "")
            ok_center = (("CENTER" in str(align_raw).upper()) if need_center else True)
            # ✅ 末尾句点校验
            ok_no_dot = (not t.endswith(".")) if need_no_dot else True

            # ✅ start_new_page：docx 很难精确验证“新页开始”
            # MVP策略：给 NEED_REVIEW 提示，不阻断
            start_new_page_issue = None
            if need_new_page:
                start_new_page_issue = {
                    "severity": "NEED_REVIEW",
                    "category": "HEADING",
                    "message": f"Проверьте, что структурный элемент начинается с новой страницы: «{t}»",
                    "suggestion": "В Word: вставьте разрыв страницы перед заголовком структурного элемента.",
                }

            if (not ok_upper) or (not ok_center) or (not ok_no_dot):
                parts = []
                if need_upper and not ok_upper:
                    parts.append("ПРОПИСНЫЕ")
                if need_center and not ok_center:
                    parts.append("по центру")
                if need_no_dot and not ok_no_dot:
                    parts.append("без точки в конце")

                issue = {
                    "severity": "MAJOR",
                    "category": "HEADING",
                    "message": f"Заголовок оформлен неверно: «{t}» (требуется: {', '.join(parts)})",
                    "suggestion": "Исправьте формат заголовка согласно ГОСТ 7.32-2017.",
                    "rule_id": rule.get("id"),
                    "clause": rule.get("clause"),
                }
                # issues.append(attach_location(snapshot, issue, anchor=t, para_idx=p.get("idx")))
                push_issue(snapshot, issues, rule, {
   "severity": "MAJOR",
   "category": "...",
   "message": "...",
   "suggestion": "...",
                }, anchor="ВВЕДЕНИЕ", para_idx=p.get("idx"))

            if need_new_page:
                issue2 = {
                "severity": "NEED_REVIEW",
                "category": "HEADING",
                "message": f"Проверьте, что структурный элемент начинается с новой страницы: «{t}»",
                "suggestion": "В Word: вставьте разрыв страницы перед заголовком структурного элемента.",
                "rule_id": rule.get("id"),
                "clause": rule.get("clause"),
                }
                push_issue(snapshot, issues, rule, {
   "severity": "MAJOR",
   "category": "...",
   "message": "...",
   "suggestion": "...",
                }, anchor="ВВЕДЕНИЕ", para_idx=p.get("idx"))

                # issues.append(attach_location(snapshot, issue2, anchor=t, para_idx=p.get("idx")))
            break
        return issues


    # 5.3.2 CHECK_ABSTRACT_COMPONENTS（MVP：粗糙关键词扫描）
    if op == "CHECK_ABSTRACT_COMPONENTS":
        required = args.get("required", []) or []
        # MVP：只检查是否出现 ключевые слова / ключевые слова: / объем 等关键片段
        joined = "\n".join(all_texts).lower()
        missing = []
        for item in required:
            it = _norm(item).lower()
            if not it:
                continue
            # 很粗糙：按词片段查找
            if it not in joined:
                missing.append(item)
        if missing:
            issues.append(_issue(
                rule,
                message=f"В реферате обязательные блоки: {', '.join(missing)}.",
                suggestion="Проверьте раздел «РЕФЕРАТ»: добавьте сведения об объёме, ключевые слова и текст реферата."
            ))
        return issues

    # 5.3.2.1 CHECK_KEYWORD_COUNT（MVP：查“Ключевые слова:”后面按逗号拆）
    if op == "CHECK_KEYWORD_COUNT":
        min_k = int(args.get("min", 5))
        max_k = int(args.get("max", 15))
        joined = "\n".join(all_texts)

        # 尝试找 “Ключевые слова” 行
        line = None
        for t in all_texts:
            if "ключев" in t.lower() and ":" in t:
                line = t
                break

        if line is None:
            issues.append(_issue(
                rule,
                message="Не найден блок «Ключевые слова: ...» для проверки количества ключевых слов.",
                suggestion="Добавьте строку «Ключевые слова: ...» в реферат и перечислите 5–15 терминов.",
                category="REVIEW"
            ))
            return issues

        after = line.split(":", 1)[1]
        keywords = [k.strip() for k in after.split(",") if k.strip()]
        n = len(keywords)
        if n < min_k or n > max_k:
            issues.append(_issue(
                rule,
                message=f"Количество ключевых слов вне диапазона: {n} (нужно {min_k}–{max_k}).",
                suggestion=f"Отредактируйте ключевые слова до {min_k}–{max_k} позиций."
            ))
        return issues

    # 其它规则：MVP 先提示需要人工/后续实现（保证“规则不空转”）
    issues.append(_issue(
        rule,
        message=f"Правило {rule.get('id')} ({op}) пока не реализовано в MVP-движке и требует расширения/ручной проверки.",
        suggestion="Отметьте для ручной проверки или расширьте движок правил для этого op.",
        category="REVIEW"
    ))
    return issues


# =========================
# 批量执行（兜底/一次跑全 rules）
# =========================
def run_hard_rules(snapshot: dict, standard: dict) -> List[dict]:
    rules = (standard or {}).get("rules", []) or []
    findings: List[dict] = []

    for rule in rules:
        findings.extend(run_rule(snapshot, rule))

    if not findings:
        findings.append({
            "page": "?",
            "severity": "LOW",
            "category": "INFO",
            "message": "Явных нарушений по базовым автоматическим правилам не найдено (MVP-проверка).",
            "suggestion": "Для полного соответствия расширьте набор правил и/или включите AI-проверку.",
        })

    return findings

#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from datetime import datetime, UTC

try:
    import yaml
except Exception as e:
    raise SystemExit(
        "PyYAML not installed. Install it ONLY for compile stage:\n"
        "  pip install PyYAML\n"
        f"Original error: {e}"
    )

# check.type -> runtime op code 映射（后端只认 op）
TYPE_TO_OP = {

    # ===== 结构 =====
    "structure_presence": "CHECK_STRUCTURE_PRESENCE",
    "optional_elements_allowed": "CHECK_OPTIONAL_ELEMENTS_ALLOWED",
    "is_first_page": "CHECK_IS_FIRST_PAGE",
    "required_fields": "CHECK_REQUIRED_FIELDS",
    "abstract_components": "CHECK_ABSTRACT_COMPONENTS",
    "toc_completeness": "CHECK_TOC_COMPLETENESS",

    # ===== 条件 =====
    "required_if": "CHECK_REQUIRED_IF",
    "conditional_optional": "CHECK_CONDITIONAL_OPTIONAL",
    "allowed_absence": "CHECK_ALLOWED_ABSENCE",

    # ===== 格式 / 版式 =====
    "notes_and_footnotes": "CHECK_NOTES_AND_FOOTNOTES",
    "page_format": "CHECK_PAGE_FORMAT",
    "margins": "CHECK_MARGINS",
    "heading_format": "CHECK_HEADING_FORMAT",
    "pagination": "CHECK_PAGINATION",
    "page_number_hidden": "CHECK_PAGE_NUMBER_HIDDEN",

    # ===== 内容计数 / 引用 =====
    "keyword_count": "CHECK_KEYWORD_COUNT",
    "citation_numeric_brackets": "CHECK_CITATION_NUMERIC_BRACKETS",
    "format_reference": "CHECK_FORMAT_REFERENCE",
    "external_standard_reference": "CHECK_EXTERNAL_STANDARD_REFERENCE",

    # ===== 图表 / 附录 / 公式 =====
    "table_rules": "CHECK_TABLE_RULES",
    "figure_rules": "CHECK_FIGURE_RULES",
    "formula_rules": "CHECK_FORMULA_RULES",
    "appendix_rules": "CHECK_APPENDIX_RULES",

    # ===== AI / 人工 =====
    "semantic_review": "CHECK_SEMANTIC_REVIEW",
}

# TYPE_TO_OP.update({
#     "is_first_page": "CHECK_IS_FIRST_PAGE",
#     "required_fields": "CHECK_REQUIRED_FIELDS",
#     "keyword_count": "CHECK_KEYWORD_COUNT",
#     "toc_completeness": "CHECK_TOC_COMPLETENESS",
#     "conditional_optional": "CHECK_CONDITIONAL_OPTIONAL",
#     "allowed_absence": "CHECK_ALLOWED_ABSENCE",
#     "required_if": "CHECK_REQUIRED_IF",
#     "abstract_components": "CHECK_ABSTRACT_COMPONENTS",
#     "format_reference": "CHECK_FORMAT_REFERENCE",
# })

SEVERITY_ENUM = {"BLOCKER", "MAJOR", "MINOR", "INFO"}

def _die(msg: str):
    raise ValueError(msg)

def _require(obj: dict, key: str, ctx: str):
    if key not in obj:
        _die(f"Missing required field '{key}' at {ctx}")

def _as_list(v, ctx: str):
    if not isinstance(v, list):
        _die(f"Expected list at {ctx}, got {type(v).__name__}")
    return v

def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        _die("DSL YAML must be a mapping at top level.")
    return data

def validate_top(dsl: dict):
    for k in ["standard", "severity_levels", "rules"]:
        _require(dsl, k, "root")

    std = dsl["standard"]
    if not isinstance(std, dict):
        _die("standard must be a mapping.")

    for k in ["code", "title", "version", "effective_date", "language"]:
        _require(std, k, "standard")

    sev = _as_list(dsl["severity_levels"], "severity_levels")
    for s in sev:
        if s not in SEVERITY_ENUM:
            _die(f"Invalid severity_levels item: {s}")

    rules = _as_list(dsl["rules"], "rules")
    if not rules:
        _die("rules is empty.")
    return std, rules

def normalize_rule(rule: dict, i: int) -> dict:
    ctx = f"rules[{i}]"
    if not isinstance(rule, dict):
        _die(f"{ctx} must be a mapping.")

    for k in ["id", "severity", "title", "scope", "check"]:
        _require(rule, k, ctx)

    rid = str(rule["id"])
    sev = str(rule["severity"]).upper()
    if sev not in SEVERITY_ENUM:
        _die(f"{ctx}.severity invalid: {sev}")

    check = rule["check"]
    if not isinstance(check, dict):
        _die(f"{ctx}.check must be a mapping.")
    _require(check, "type", f"{ctx}.check")

    ctype = str(check["type"])
    if ctype not in TYPE_TO_OP:
        _die(f"{ctx}.check.type not supported: {ctype}")

    op = TYPE_TO_OP[ctype]

    # 把除 'type' 外的字段都视为 args（包含 required_elements 等）
    args = {k: check[k] for k in check.keys() if k != "type"}

    runtime_rule = {
        "id": rid,
        "severity": sev,
        "title": str(rule["title"]),
        "scope": str(rule["scope"]),
        "op": op,
        "args": args,  # 稳定结构：后端只认 op + args
    }

    # 可选字段保留（用于追溯/展示）
    for opt in ["clause", "tags", "basis", "description"]:
        if opt in rule:
            runtime_rule[opt] = rule[opt]

    return runtime_rule

def compile_dsl(dsl_path: Path, out_path: Path):
    dsl = load_yaml(dsl_path)
    std, rules = validate_top(dsl)

    runtime = {
        "runtime_format": "GOST_RUNTIME_RULESET",
        "runtime_version": "1.0",

        "compiled_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),

        "standard": std,
        "severity_levels": dsl["severity_levels"],
        "rules": [],
        "index": {
            "by_id": {},
            "by_op": {},
            "by_scope": {},
        }
    }

    seen_ids = set()
    unsupported = []

    for i, r in enumerate(rules):
        check = r.get("check", {})
        ctype = (check.get("type") if isinstance(check, dict) else None)
        if ctype not in TYPE_TO_OP:
            unsupported.append((i, ctype))
            continue
        
        rr = normalize_rule(r, i)
        rid = rr["id"]
        if rid in seen_ids:
            _die(f"Duplicate rule id: {rid}")
        seen_ids.add(rid)

        runtime["rules"].append(rr)

        runtime["index"]["by_id"][rid] = len(runtime["rules"]) - 1
        runtime["index"]["by_op"].setdefault(rr["op"], []).append(rid)
        runtime["index"]["by_scope"].setdefault(rr["scope"], []).append(rid)

    if unsupported:
        lines = [f"rules[{i}].check.type = {t}" for i, t in unsupported]
        _die("Unsupported check.type found:\n" + "\n".join(lines))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(runtime, ensure_ascii=False, indent=2), encoding="utf-8")

def main():
    if len(sys.argv) < 2:
        print("Usage: compile_dsl.py <gost_7_32_2017.yaml> [out.runtime.json]")
        sys.exit(2)

    dsl_path = Path(sys.argv[1]).resolve()
    if not dsl_path.exists():
        raise SystemExit(f"Input not found: {dsl_path}")

    if len(sys.argv) >= 3:
        out_path = Path(sys.argv[2]).resolve()
    else:
        out_path = dsl_path.with_suffix("").with_suffix(".runtime.json")  # a.yaml -> a.runtime.json

    compile_dsl(dsl_path, out_path)
    print(f"OK: compiled runtime json -> {out_path}")

if __name__ == "__main__":
    main()

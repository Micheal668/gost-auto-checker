from pathlib import Path
from .rule_loader import load_rules
from .hard_rules import run_hard_rules
from .result_writer import write_result
from .docx_extractor import extract_text  # 如果你后面要用


def run_checker(input_path: str, media_root: Path) -> dict:
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    rules = load_rules()
    text = extract_text(input_file)  # 你之前注释了，但下面又在用
    issues = run_hard_rules(text, rules)
    result_path = write_result(media_root, input_file.stem, issues)

    return {
        "issues": issues,
        "result_path": str(result_path),
    }

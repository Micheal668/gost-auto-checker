import subprocess
from pathlib import Path

SOFFICE = "/Applications/LibreOffice.app/Contents/MacOS/soffice"

def docx_to_pdf(docx_path: str, out_dir: str) -> str:
    docx = Path(docx_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    cmd = [
        SOFFICE,
        "--headless",
        "--convert-to", "pdf",
        "--outdir", str(out),
        str(docx),
    ]

    subprocess.run(cmd, check=True)

    pdf_path = out / (docx.stem + ".pdf")
    if not pdf_path.exists():
        raise RuntimeError("PDF conversion failed")

    return str(pdf_path)

import os
from pathlib import Path
import argparse


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export pages from a PDF to PNG images using PyMuPDF")
    p.add_argument("--pdf", default="ss.pdf", help="Path to PDF (default: ss.pdf)")
    p.add_argument("--outdir", default="docs", help="Output directory (default: docs)")
    p.add_argument("--pages", default="1-2", help="Pages to export, 1-based (e.g., 1-1 or 1-3)")
    p.add_argument("--dpi", type=int, default=150, help="Export DPI (default: 150)")
    return p.parse_args()


def parse_range(s: str, total: int) -> range:
    if "-" in s:
        a, b = s.split("-", 1)
        start = max(1, int(a))
        end = min(total, int(b))
        return range(start, end + 1)
    idx = int(s)
    idx = min(max(1, idx), total)
    return range(idx, idx + 1)


def main():
    args = parse_args()
    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    try:
        import fitz  # PyMuPDF
    except Exception as e:
        raise SystemExit("PyMuPDF not installed. Run: pip install pymupdf")

    doc = fitz.open(pdf_path)
    pages = parse_range(args.pages, len(doc))
    for pno in pages:
        page = doc.load_page(pno - 1)
        mat = fitz.Matrix(args.dpi / 72, args.dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        out = outdir / f"ss-{pno}.png"
        pix.save(out.as_posix())
        print(f"Wrote {out}")
    doc.close()


if __name__ == "__main__":
    main()



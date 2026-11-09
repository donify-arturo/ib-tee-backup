"""
Marker OCR for chosen pages of one PDF. Runs in its own environment (.venv-marker, Python 3.12, marker-pdf 1.10.1),
so it imports nothing from this project. Started by `python -m ingest.scan_ocr marker`.

    marker_worker.py <pdf> <out.jsonl> <page,page,...>

Finished pages are appended immediately, so stopping and restarting loses at most the page in progress.
"""
import json
import sys
import tempfile
import time
from pathlib import Path

DPI = 200


def main(pdf_path: str, out_path: str, pages_arg: str) -> None:
    out = Path(out_path)
    wanted = [int(p) for p in pages_arg.split(",")]
    done = {json.loads(l)["page"] for l in out.read_text(encoding="utf-8").splitlines() if l.strip()} if out.exists() else set()
    todo = [p for p in wanted if p not in done]
    print(f"{Path(pdf_path).name}: {len(done & set(wanted))}/{len(wanted)} done, {len(todo)} to do", flush=True)
    if not todo:
        return

    import pypdfium2
    from marker.config.parser import ConfigParser
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict

    cfg = ConfigParser({"output_format": "markdown", "force_ocr": True, "disable_image_extraction": True})
    conv = PdfConverter(config=cfg.generate_config_dict(), artifact_dict=create_model_dict())
    pdf = pypdfium2.PdfDocument(pdf_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        one = Path(tmp) / "page.pdf"
        for n in todo:
            t0 = time.time()
            pdf[n - 1].render(scale=DPI / 72).to_pil().convert("RGB").save(one, resolution=DPI)
            md = conv(str(one)).markdown
            with out.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"page": n, "markdown": md, "seconds": round(time.time() - t0)}, ensure_ascii=False) + "\n")
            print(f"page {n}: {round(time.time() - t0)} s", flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:4])

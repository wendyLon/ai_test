"""Test runner for PDF/OCR extraction examples.

Place sample PDFs under `tests/samples/` (e.g. `tests/samples/sample_flyer.pdf`).
Run this script to process them with the OCR pipeline and output parsed JSON.
"""
import sys
from pathlib import Path
from platform.extractor.pdf_ocr import PDFOCRProcessor

SAMPLES_DIR = Path('tests/samples')

def run():
    p = PDFOCRProcessor(out_dir='data/raw/pdfs')
    if not SAMPLES_DIR.exists():
        print('No samples directory found. Create tests/samples/ and add PDFs to test.')
        return
    for pdf in SAMPLES_DIR.glob('*.pdf'):
        print('Processing', pdf)
        out = p.process_pdf(pdf)
        fields, conf = p.parse_text_to_fields((out.get('text','') or '') + '\n' + (out.get('ocr_text','') or ''), source_url=str(pdf))
        print('Parsed fields:', fields)
        print('Confidences:', conf)

if __name__ == '__main__':
    run()

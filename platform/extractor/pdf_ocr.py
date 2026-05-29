"""PDF and OCR processing utilities.

Features:
- Detect PDF links and image flyers
- Download PDFs
- Extract text via pdfplumber and pymupdf
- Extract images and run OCR via pytesseract with preprocessing
- Save original PDF, OCR text, parsed JSON
"""
import os
import io
import re
import json
import hashlib
from pathlib import Path
from typing import List, Tuple, Dict, Optional

import requests
from PIL import Image, ImageFilter, ImageOps

try:
    import pdfplumber
except Exception:
    pdfplumber = None

try:
    import fitz  # pymupdf
except Exception:
    fitz = None

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    import cv2
    import numpy as np
except Exception:
    cv2 = None
    np = None


class PDFOCRProcessor:
    def __init__(self, out_dir: str = 'data/raw/pdfs', ocr_lang: str = 'chi_tra+eng'):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.ocr_lang = ocr_lang

    def download(self, url: str) -> Optional[Path]:
        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code != 200:
                return None
            digest = hashlib.sha256(url.encode('utf-8')).hexdigest()[:12]
            fname = f"{digest}.pdf"
            path = self.out_dir / fname
            with open(path, 'wb') as f:
                f.write(resp.content)
            return path
        except Exception:
            return None

    def extract_text_pdfplumber(self, pdf_path: Path) -> str:
        if pdfplumber is None:
            return ''
        text_parts = []
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ''
                    text_parts.append(text)
        except Exception:
            return ''
        return '\n'.join(text_parts)

    def extract_images_pymupdf(self, pdf_path: Path) -> List[Path]:
        images = []
        if fitz is None:
            return images
        doc = fitz.open(str(pdf_path))
        for i in range(len(doc)):
            page = doc[i]
            for img_index, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image['image']
                ext = base_image.get('ext', 'png')
                img_name = f"{pdf_path.stem}_p{i}_{img_index}.{ext}"
                img_path = pdf_path.with_name(img_name)
                with open(img_path, 'wb') as f:
                    f.write(image_bytes)
                images.append(img_path)
        return images

    # Preprocessing: denoise, contrast, rotation correction
    def preprocess_image(self, img_path: Path) -> Image.Image:
        img = Image.open(img_path).convert('L')
        # Enhance contrast
        img = ImageOps.autocontrast(img)
        # Denoise via median filter
        img = img.filter(ImageFilter.MedianFilter(size=3))
        # Convert to numpy for rotation correction if available
        if cv2 is not None and np is not None:
            arr = np.array(img)
            coords = np.column_stack(np.where(arr < 250))
            if coords.shape[0] > 0:
                angle = cv2.minAreaRect(coords)[-1]
                if angle < -45:
                    angle = -(90 + angle)
                else:
                    angle = -angle
                if abs(angle) > 1:
                    # rotate
                    img = img.rotate(angle, expand=True, fillcolor=255)
        return img

    def ocr_image(self, img: Image.Image) -> str:
        if pytesseract is None:
            return ''
        try:
            txt = pytesseract.image_to_string(img, lang=self.ocr_lang)
            return txt
        except Exception:
            # fallback without lang
            try:
                return pytesseract.image_to_string(img)
            except Exception:
                return ''

    def process_pdf(self, pdf_path: Path) -> Dict:
        """Extract text and images from pdf and run OCR on images.

        Returns dict: { 'pdf_path', 'text', 'images': [paths], 'ocr_text': combined_text }
        """
        out = {'pdf_path': str(pdf_path), 'text': '', 'images': [], 'ocr_text': ''}
        text = self.extract_text_pdfplumber(pdf_path)
        out['text'] = text

        images = self.extract_images_pymupdf(pdf_path)
        ocr_texts = []
        for img_path in images:
            try:
                pre = self.preprocess_image(img_path)
                txt = self.ocr_image(pre)
                ocr_texts.append(txt)
            except Exception:
                continue
        out['images'] = [str(p) for p in images]
        out['ocr_text'] = '\n'.join(ocr_texts)

        # Save OCR text
        ocr_path = pdf_path.with_suffix('.ocr.txt')
        with open(ocr_path, 'w', encoding='utf-8') as f:
            f.write(out['ocr_text'])

        # Save parsed JSON
        json_path = pdf_path.with_suffix('.parsed.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

        return out

    # Simple parser to extract fields from text (used as fallback)
    def parse_text_to_fields(self, text: str, source_url: str = None) -> Tuple[Dict, Dict]:
        # returns fields dict and confidence dict
        fields = {}
        conf = {}
        if not text:
            return fields, conf
        # title: first non-empty short line
        for line in text.splitlines():
            s = line.strip()
            if 5 < len(s) < 200:
                fields['title_zh_cn'] = s
                conf['title_zh_cn'] = 0.4
                break
        # date
        m = re.search(r"(\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{1,2}月\d{1,2}日|\d{1,2}/\d{1,2})", text)
        if m:
            fields['schedule_time'] = m.group(0)
            conf['schedule_time'] = 0.5
        # fee
        m2 = re.search(r"(\$\s?\d+[\.,]?\d*|HKD|港幣|免費|免費參加|free)", text, re.I)
        if m2:
            fields['fee'] = m2.group(0)
            conf['fee'] = 0.5
        # venue
        # look for keywords
        for kw in ['地點', '地點：', '地址', 'venue', 'location', '地点']:
            if kw in text:
                i = text.find(kw)
                fields['venue_name'] = text[i:i+120]
                conf['venue_name'] = 0.4
                break
        if source_url:
            fields['web_url'] = source_url
        return fields, conf

    def ocr_image_from_url(self, url: str) -> Tuple[str, float]:
        """Download an image and run OCR, returning text and a crude confidence score."""
        try:
            resp = requests.get(url, timeout=20)
            if resp.status_code != 200:
                return '', 0.0
            img = Image.open(io.BytesIO(resp.content)).convert('L')
            pre = self.preprocess_image_obj(img)
            txt = self.ocr_image(pre)
            # crude confidence: length of OCR text
            conf = min(1.0, len(txt) / 200.0)
            return txt, conf
        except Exception:
            return '', 0.0

    def preprocess_image_obj(self, img: Image.Image) -> Image.Image:
        # apply same preprocessing pipeline but accept Image object
        if img.mode != 'L':
            img = img.convert('L')
        img = ImageOps.autocontrast(img)
        img = img.filter(ImageFilter.MedianFilter(size=3))
        if cv2 is not None and np is not None:
            arr = np.array(img)
            coords = np.column_stack(np.where(arr < 250))
            if coords.shape[0] > 0:
                angle = cv2.minAreaRect(coords)[-1]
                if angle < -45:
                    angle = -(90 + angle)
                else:
                    angle = -angle
                if abs(angle) > 1:
                    img = img.rotate(angle, expand=True, fillcolor=255)
        return img

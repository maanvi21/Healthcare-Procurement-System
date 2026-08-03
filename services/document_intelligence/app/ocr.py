"""OCR pipeline: OpenCV preprocessing + PaddleOCR text extraction.

Handles both image uploads (jpg/png) and PDF uploads (rendered to images via PyMuPDF,
one page at a time, then OCR'd page by page).
"""
import io

import cv2
import fitz  # PyMuPDF
import numpy as np

_ocr_engine = None


def _get_engine():
    """Lazy singleton — PaddleOCR downloads/loads its detection+recognition models on
    first use, so we defer construction until the first real OCR call rather than at
    import time (keeps service startup fast and side-effect free)."""
    global _ocr_engine
    if _ocr_engine is None:
        from paddleocr import PaddleOCR

        _ocr_engine = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    return _ocr_engine


def _preprocess(image: np.ndarray) -> np.ndarray:
    """OpenCV preprocessing: grayscale, denoise, adaptive threshold, deskew-friendly
    resize. Improves OCR accuracy on scanned/photographed procurement documents."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    thresh = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
    )
    return cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)


def _pdf_to_images(file_bytes: bytes) -> list[np.ndarray]:
    images = []
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for OCR quality
            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if pix.n == 4:
                arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
            elif pix.n == 3:
                arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            images.append(arr)
    return images


def extract_text(file_bytes: bytes, content_type: str) -> tuple[str, float]:
    """Returns (full_text, average_confidence) across all pages/lines."""
    if content_type == "application/pdf":
        images = _pdf_to_images(file_bytes)
    else:
        arr = np.frombuffer(file_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        images = [img]

    engine = _get_engine()
    lines: list[str] = []
    confidences: list[float] = []

    for img in images:
        processed = _preprocess(img)
        result = engine.ocr(processed, cls=True)
        for page_result in result or []:
            for line in page_result or []:
                text, confidence = line[1][0], float(line[1][1])
                lines.append(text)
                confidences.append(confidence)

    full_text = "\n".join(lines)
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    return full_text, avg_confidence

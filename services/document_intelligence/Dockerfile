FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download PaddleOCR models at build time so the first request doesn't
# trigger a slow runtime download (which would cause a 504 Gateway Timeout).
# We download the tar files directly and extract them to the expected cache paths.
RUN mkdir -p /root/.paddleocr/whl/det/en/en_PP-OCRv3_det_infer \
             /root/.paddleocr/whl/rec/en/en_PP-OCRv4_rec_infer \
             /root/.paddleocr/whl/cls/ch_ppocr_mobile_v2.0_cls_infer \
 && curl -L https://paddleocr.bj.bcebos.com/PP-OCRv3/english/en_PP-OCRv3_det_infer.tar \
         | tar -xf - -C /root/.paddleocr/whl/det/en/en_PP-OCRv3_det_infer --strip-components=1 \
 && curl -L https://paddleocr.bj.bcebos.com/PP-OCRv4/english/en_PP-OCRv4_rec_infer.tar \
         | tar -xf - -C /root/.paddleocr/whl/rec/en/en_PP-OCRv4_rec_infer --strip-components=1 \
 && curl -L https://paddleocr.bj.bcebos.com/dygraph_v2.0/ch/ch_ppocr_mobile_v2.0_cls_infer.tar \
         | tar -xf - -C /root/.paddleocr/whl/cls/ch_ppocr_mobile_v2.0_cls_infer --strip-components=1

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

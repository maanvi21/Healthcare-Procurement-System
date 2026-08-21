# Sample documents

Test fixtures for the document-intelligence pipeline, carried over from the standalone
prototype. Each exercises a different path through OCR → classification → extraction →
fraud screen.

| File | Exercises |
|---|---|
| `invoice.pdf` | PDF render (PyMuPDF) → OCR → `invoice` classification → invoice-number/total/tax extraction |
| `purchase_order.pdf` | PDF path with `purchase_order` classification and PO-number extraction |
| `sample_invoice.png` | Direct image path (no PDF render), so it also covers OpenCV preprocessing on a raster scan |

Ingest one against a running stack:

```bash
curl -F "file=@services/document_intelligence/samples/invoice.pdf" \
     "http://localhost/api/documents/ingest?source=upload"
```

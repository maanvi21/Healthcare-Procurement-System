# Watched document folders

The document-intelligence watcher polls Input for supported PDF and image files.

- Input: new files awaiting ingestion and processing.
- Processed: source files whose OCR/extraction pipeline completed.
- Failed: files that could not be ingested or processed. A neighboring .error.txt file
  records the failure reason. For database-backed failures, the same reason appears in
  the Document Intelligence detail panel and can be retried there.

The watcher creates all three directories at service startup. On Docker Compose the root
folder is mounted from this directory. Kubernetes mounts a shared ReadWriteMany volume at
/app/watched_documents; the cluster must provide an RWX-capable StorageClass.

Supported extensions: PDF, PNG, JPG/JPEG, TIF/TIFF, BMP.

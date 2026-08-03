FROM python:3.11-slim

RUN pip install --no-cache-dir mlflow==2.16.0

RUN mkdir -p /mlflow/artifacts
WORKDIR /mlflow

EXPOSE 5000

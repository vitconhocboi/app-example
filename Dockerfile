# Lib datanexus nam o repo appvisualize -> truyen qua build context rieng:
#   docker build --build-context datanexus=../appvisualize/lib/datanexus -t taxi-fare-app .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY --from=datanexus . /tmp/datanexus
COPY requirements.txt .
RUN pip install -r requirements.txt "/tmp/datanexus[arrow]" && rm -rf /tmp/datanexus

COPY app.py .
RUN useradd --uid 10001 --create-home app
USER 10001

# Cung port 8501 nhu sso-demo-app -> thay the truc tiep sau nginx/ingress.
EXPOSE 8501
CMD ["gunicorn", "app:server", "--bind=0.0.0.0:8501", "--workers=2", "--threads=4", "--timeout=900"]

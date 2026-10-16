FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py questions.json ./
RUN useradd --create-home --uid 10001 ihc && mkdir -p /data && chown ihc:ihc /data
USER ihc
EXPOSE 8080
CMD ["waitress-serve","--host=0.0.0.0","--port=8080","--threads=4","app:app"]

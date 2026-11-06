FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN mkdir -p /data && chown 10001:10001 /data
COPY --chmod=644 server.py additional_sources.py areas.json sources.json ./
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=3)"]
CMD ["python", "server.py"]

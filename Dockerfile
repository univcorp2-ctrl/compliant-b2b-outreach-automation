FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . && playwright install --with-deps chromium
COPY . .
RUN mkdir -p /app/data /app/exports /app/artifacts
EXPOSE 8000
CMD ["outreach-bot", "serve", "--host", "0.0.0.0", "--port", "8000"]

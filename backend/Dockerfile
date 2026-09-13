FROM python:3.10-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY backend/ ./backend/

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "truelock.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

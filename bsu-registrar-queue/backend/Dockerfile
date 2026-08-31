FROM python:3.14.7-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x start.sh

# Run as an unprivileged user, not root. alembic, init_db and uvicorn on
# port 8000 all work fine without privileges; the app also writes uploaded
# media under /app/uploads, so that tree must be owned by this user.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/uploads/media \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["./start.sh"]

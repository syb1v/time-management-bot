FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/matplotlib

WORKDIR /app
RUN useradd --create-home --uid 10001 bot
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
COPY raspisanie_11g.md vebinary_sotka_sentyabr_2026.md ./
RUN mkdir /app/data && chown -R bot:bot /app
USER bot

CMD ["python", "-m", "time_manager.main"]

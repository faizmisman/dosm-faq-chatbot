FROM python:3.10-slim

# Optional build arg to include local .env (DO NOT use in CI/CD)
ARG INCLUDE_ENV=false

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY train ./train

# Conditionally copy .env only for local development builds
RUN if [ "$INCLUDE_ENV" = "true" ] && [ -f .env ]; then echo "Including local .env in image (dev only)"; cp .env /app/.env; fi
# Pydantic settings will read /app/.env if present; CI builds should not bake secrets.
# Vector store now served from PostgreSQL via DATABASE_URL environment variable

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

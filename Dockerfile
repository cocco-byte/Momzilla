FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY scripts/ scripts/

# No local volume needed - counselor accounts and escalation records live in
# Postgres (MOMZILLA_DATABASE_URL, set at deploy time, e.g. to an Aiven
# connection string). Conversation content never touches disk regardless -
# it's process memory only, so this container is otherwise fully stateless
# and safe to redeploy/restart/scale without a mounted disk.

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

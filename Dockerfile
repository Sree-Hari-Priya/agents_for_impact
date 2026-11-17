FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    fastapi \
    uvicorn \
    pydantic \
    google-cloud-bigquery \
    google-genai \
    google-adk \
    db-dtypes \
    pandas \
    pyarrow

# Copy application files
COPY agent/ /app/agent/

ENV PORT=8080
ENV PYTHONUNBUFFERED=1
ENV GOOGLE_GENAI_USE_VERTEXAI=true
ENV GOOGLE_CLOUD_REGION=us-central1
ENV A4I_DATASET=a4i_early_intervention
ENV A4I_LOCATION=US

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "agent.main:app", "--host", "0.0.0.0", "--port", "8080"]

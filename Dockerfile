FROM python:3.11-slim

LABEL maintainer="Ubermorgen"
LABEL description="Ollama DevOps Agent - AI-powered DevOps automation"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY agent.py .
COPY ollama_backend.py .
COPY smolagents_patches.py .
COPY Modelfile .
COPY install.sh .

# Note: This Dockerfile assumes Ollama is running on the host or another container
# Set OLLAMA_HOST environment variable to point to your Ollama instance
ENV OLLAMA_HOST=http://host.docker.internal:11434

# Create a non-root user
RUN useradd -m -u 1000 devops && chown -R devops:devops /app
USER devops

# Set entrypoint
ENTRYPOINT ["python3", "agent.py"]

# Default command (interactive mode)
CMD ["--interactive"]

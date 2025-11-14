FROM python:3.11-slim

LABEL maintainer="Ubermorgen"
LABEL description="Ollama DevOps Agent - AI-powered DevOps automation"

# Install system dependencies, kubectl, and Docker CLI
RUN apt-get update && apt-get install -y \
    curl \
    git \
    ca-certificates \
    apt-transport-https \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install kubectl
RUN curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.31/deb/Release.key | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg \
    && echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.31/deb/ /' | tee /etc/apt/sources.list.d/kubernetes.list \
    && apt-get update \
    && apt-get install -y kubectl \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI (for Docker operations)
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian bullseye stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update \
    && apt-get install -y docker-ce-cli \
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

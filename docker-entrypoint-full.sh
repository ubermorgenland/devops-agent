#!/bin/bash
set -e

# Start Ollama service in background (suppress logs)
echo "Starting Ollama service..."
OLLAMA_LOGS="${OLLAMA_LOGS:-/dev/null}"
ollama serve > "$OLLAMA_LOGS" 2>&1 &
OLLAMA_PID=$!

# Wait for Ollama to be ready
echo "Waiting for Ollama to be ready..."
while ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
    sleep 1
done

# Check if model exists, create if not
echo "Checking if qwen3-devops model exists..."
if ! ollama list | grep -q "qwen3-devops"; then
    echo "Creating qwen3-devops model..."
    cd /app
    ollama create qwen3-devops -f Modelfile
    echo "Model created successfully!"
else
    echo "Model already exists"
fi

# Function to cleanup on exit
cleanup() {
    echo "Shutting down Ollama..."
    kill $OLLAMA_PID 2>/dev/null || true
    wait $OLLAMA_PID 2>/dev/null || true
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

# Run the agent with provided arguments
echo "Starting DevOps Agent..."
cd /app

# If no arguments provided, don't default to interactive
if [ $# -eq 0 ]; then
    echo "No arguments provided. Use --interactive for interactive mode, or provide a query."
    echo "Example: docker run ... ubermorgenai/ollama-devops:full \"List all files\""
    exit 1
fi

# Check if interactive mode is requested
if [ "$1" = "--interactive" ] || [ "$1" = "-i" ]; then
    # Make sure we have a proper terminal for interactive mode
    if [ -t 0 ] && [ -t 1 ]; then
        python3 agent.py "$@"
    else
        echo "Interactive mode requires a TTY. Use: docker run -it ..."
        exit 1
    fi
else
    # Single command mode
    python3 agent.py "$@"
fi
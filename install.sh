#!/usr/bin/env bash

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "╔══════════════════════════════════════════════════════════╗"
echo "║   Ollama DevOps Agent - Automated Installation          ║"
echo "║   By Ubermorgen                                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${YELLOW}➜${NC} $1"
}

# Check Python version
print_info "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    print_error "Python 3.8 or higher is required. Found: $PYTHON_VERSION"
    exit 1
fi

print_success "Python $PYTHON_VERSION detected"

# Check if Ollama is installed
print_info "Checking Ollama installation..."
if ! command -v ollama &> /dev/null; then
    print_info "Ollama not found. Installing Ollama..."
    
    # Detect OS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            print_info "Installing Ollama via Homebrew..."
            brew install ollama
        else
            print_info "Homebrew not found. Please install Ollama manually from https://ollama.com/download"
            exit 1
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        print_info "Installing Ollama..."
        curl -fsSL https://ollama.com/install.sh | sh
    else
        print_error "Unsupported operating system. Please install Ollama manually from https://ollama.com/download"
        exit 1
    fi
    
    print_success "Ollama installed successfully"
else
    print_success "Ollama already installed"
fi

# Start Ollama service (if not running)
print_info "Checking Ollama service..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    print_info "Starting Ollama service..."
    ollama serve > /dev/null 2>&1 &
    sleep 3
    print_success "Ollama service started"
else
    print_success "Ollama service is running"
fi

# Install Python dependencies
print_info "Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    python3 -m pip install -q -r requirements.txt
    print_success "Python dependencies installed"
else
    print_error "requirements.txt not found"
    exit 1
fi

# Download model from Hugging Face
print_info "Downloading model from Hugging Face..."
MODEL_FILE="qwen3-devops.gguf"
HF_REPO="ubermorgen/qwen3-devops"

if [ ! -f "$MODEL_FILE" ]; then
    print_info "Model not found locally. Downloading..."
    
    # Check if huggingface_hub is installed
    if ! python3 -c "import huggingface_hub" &> /dev/null; then
        print_info "Installing huggingface_hub..."
        python3 -m pip install -q huggingface_hub
    fi
    
    # Download model
    python3 << PYTHON
from huggingface_hub import hf_hub_download
print("Downloading model from Hugging Face...")
hf_hub_download(
    repo_id="$HF_REPO",
    filename="$MODEL_FILE",
    local_dir="."
)
PYTHON
    
    if [ $? -eq 0 ]; then
        print_success "Model downloaded successfully"
    else
        print_error "Failed to download model from Hugging Face"
        print_info "Please download manually from: https://huggingface.co/$HF_REPO"
        exit 1
    fi
else
    print_success "Model file found: $MODEL_FILE"
fi

# Create Ollama model
print_info "Creating Ollama model..."
if ! ollama list | grep -q "qwen-devops-v2"; then
    ollama create qwen-devops-v2 -f Modelfile
    print_success "Ollama model created: qwen-devops-v2"
else
    print_success "Ollama model already exists: qwen-devops-v2"
fi

# Verify installation
print_info "Verifying installation..."
if python3 -c "import smolagents, requests, rich" &> /dev/null; then
    print_success "All Python dependencies are working"
else
    print_error "Some Python dependencies are missing"
    exit 1
fi

if ollama list | grep -q "qwen-devops-v2"; then
    print_success "Ollama model is ready"
else
    print_error "Ollama model verification failed"
    exit 1
fi

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   Installation Complete!                                 ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "To get started:"
echo "  • Interactive mode:  python3 agent.py"
echo "  • Single query:      python3 agent.py \"Your query here\""
echo "  • With approval:     python3 agent.py -a"
echo "  • Verbose mode:      python3 agent.py --verbose"
echo ""
echo "Documentation: https://github.com/ubermorgen/ollama-devops"
echo ""

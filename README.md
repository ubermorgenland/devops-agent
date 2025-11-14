# Ollama DevOps Agent

A lightweight AI-powered DevOps automation tool using a fine-tuned Qwen3-1.7B model with Ollama and SmolAgents. **Specialized for Docker and Kubernetes workflows** with sequential tool execution and structured reasoning.

## Features

- **Sequential Tool Execution**: Calls ONE tool at a time, waits for results, then proceeds
- **Structured Reasoning**: Uses `<think>` and `<plan>` tags to show thought process
- **Validation-Aware**: Checks command outputs for errors before proceeding
- **Multi-Step Tasks**: Handles complex workflows requiring multiple tool calls
- **Approval Mode**: Optional user confirmation before executing each tool call for enhanced safety
- **Resource Efficient**: Optimized for local development (1GB GGUF model)
- **Fast**: Completes typical DevOps tasks in ~10 seconds

## What's Special About This Model?

This model is fine-tuned specifically for DevOps automation with improved reasoning capabilities:

- **Docker & Kubernetes Expert**: Trained on 300+ Docker and Kubernetes workflows (90% of training data)
- **One tool at a time**: Unlike base models that try to call all tools at once, this model executes sequentially
- **Explicit planning**: Shows reasoning with `<think>` and `<plan>` before acting
- **Uses actual values**: Extracts and uses real values from tool responses in subsequent calls
- **Error handling**: Validates each step and tries alternative approaches on failure

### Training Data Focus

The model has been trained on:
- **Docker workflows**: Building images, containers, Docker Compose, optimization
- **Kubernetes operations**: Pods, deployments, services, configurations
- **General DevOps**: File operations, system commands, basic troubleshooting

⚠️ **Note**: The model has limited training on cloud-specific CLIs (gcloud, AWS CLI, Azure CLI). For best results, use it for Docker and Kubernetes tasks.

### Example Output

```
Task: Get all pods in default namespace

Step 1: Execute kubectl command
<tool_call>
{"name": "bash", "arguments": {"command": "kubectl get pods -n default"}}
</tool_call>

[Receives pod list]

Step 2: Provide summary
<tool_call>
{"name": "final_answer", "arguments": {"answer": "Successfully retrieved 10 pods in default namespace..."}}
</tool_call>
```

## Quick Start

### One-Line Installation

```bash
curl -fsSL https://raw.githubusercontent.com/ubermorgenland/devops-agent/main/install.sh | bash
```

This will automatically:
- Install Ollama (if not present)
- Install Python dependencies
- Download the model from Hugging Face
- Create the Ollama model
- Set up the `devops-agent` CLI command

---

### Docker Installation (Config Mounting Approach)

Docker installation with configuration mounting provides practical Docker and Kubernetes DevOps capabilities:

**Tools Included:**
- 🔧 **kubectl** - Kubernetes management
- 🐳 **docker** - Container operations
- 📁 **File operations** - Read/write files
- 🤖 **DevOps agent** - Specialized for Docker & Kubernetes workflows

```bash
# Pull the current image
docker pull ubermorgenai/ollama-devops:latest

# Run with your configurations mounted
docker run -it --rm \
  --add-host=host.docker.internal:host-gateway \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  -v ~/.kube:/home/devops/.kube:ro \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd):/workspace \
  ubermorgenai/ollama-devops:latest
```

**Example Usage:**

```bash
# Kubernetes operations
docker run -it --rm \
  --add-host=host.docker.internal:host-gateway \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  -v ~/.kube:/home/devops/.kube:ro \
  ubermorgenai/ollama-devops:latest \
  "Get all pods in default namespace"

# Docker operations
docker run -it --rm \
  --add-host=host.docker.internal:host-gateway \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  ubermorgenai/ollama-devops:latest \
  "List all running Docker containers"

# Interactive mode with full access
docker run -it --rm \
  --add-host=host.docker.internal:host-gateway \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  -v ~/.kube:/home/devops/.kube:ro \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd):/workspace \
  ubermorgenai/ollama-devops:latest \
  --interactive
```

---

### Manual Installation

#### 1. Prerequisites

**Install Ollama:**

```bash
# macOS: Download from website or use Homebrew
brew install ollama
# OR download from: https://ollama.com/download

# Linux:
curl -fsSL https://ollama.com/install.sh | sh
```

**Install Python dependencies:**

```bash
pip install smolagents requests prompt_toolkit
```

**Note**: `prompt_toolkit` is required for interactive mode with arrow key support and command history.

#### 2. Download the Model

Download the fine-tuned GGUF model (1GB) from Hugging Face:

```bash
# Install huggingface-hub if not already installed
pip install huggingface-hub

# Download the model
huggingface-cli download ubermorgen/qwen3-devops qwen3-devops.gguf --local-dir .
```

Or download manually from: https://huggingface.co/ubermorgen/qwen3-devops

**Note**: Make sure the GGUF file is in the same directory as the `Modelfile`.

#### 3. Create Ollama Model

```bash
ollama create qwen3-devops -f Modelfile
```

#### 4. Run the Agent

**Single query mode:**
```bash
devops-agent "Get all pods in default namespace"
```

**Interactive mode (REPL):**
```bash
devops-agent
# OR
devops-agent --interactive
```

**Verbose mode (show detailed execution):**
```bash
devops-agent "Your query" --verbose
```

**Approval mode (require confirmation before executing tools):**
```bash
# Interactive mode with approval
devops-agent --require-approval
# OR use shorthand
devops-agent -a

# Combine with interactive mode
devops-agent -i -a

# Single query with approval
devops-agent --require-approval "List all Docker containers"

# Using environment variable
REQUIRE_APPROVAL=1 devops-agent
```

## Interactive Mode

The agent supports an interactive REPL (Read-Eval-Print Loop) for continuous task execution:

```bash
devops-agent
```

**Features:**
- Execute multiple tasks in one session
- Real-time thinking indicator with timer
- Clean output showing only tool calls and observations
- **Arrow key support**: Use Up/Down to navigate command history, Left/Right to edit current line
- **Persistent command history**: Commands are saved to `~/.devops_agent_history`
- Optional approval mode for safety (confirm before executing tools)
- Type `exit`, `quit`, or `q` to leave
- Type `help` or `?` for available commands

**Example session:**
```
🤖 DevOps Agent - Interactive Mode
Type your task and press Enter. Type 'exit' or 'quit' to leave.

> Get all pods in default namespace
⠋ thinking... 3s
⏱️ 6s

bash {kubectl get pods -n default}
Observations:
NAME                          READY   STATUS    RESTARTS   AGE
nginx-deployment-abc123       1/1     Running   0          2d

✅ Successfully retrieved all pods in the default namespace...

> Create a simple Dockerfile for Python app
⠋ thinking... 2s
⏱️ 4s

write_file {Dockerfile}
Observations:
Wrote 156 bytes to Dockerfile

✅ Created Dockerfile for Python application...

> exit
Goodbye!
```

**Verbose mode:**
```bash
devops-agent --verbose  # Show detailed execution steps
```

**Approval mode (with example):**
```
$ devops-agent -i -a

🤖 DevOps Agent - Interactive Mode
⚠️  Approval mode enabled - you'll be asked to approve each tool call
Type your task and press Enter. Type 'exit' or 'quit' to leave.

> List all files in current directory

⏱️ 3s

🔧 Tool call requested:
   Tool: bash
   Arguments: {
     "command": "ls -la"
   }

Approve this tool call? [y/n]: y

bash {ls -la}
Observations:
total 64
drwxr-xr-x  8 user  staff   256 Jan 13 10:30 .
drwxr-xr-x 15 user  staff   480 Jan 10 15:22 ..
-rw-r--r--  1 user  staff  5234 Jan 13 10:28 agent.py
...

✅ Successfully listed all files in the current directory

> Delete all log files

⏱️ 2s

🔧 Tool call requested:
   Tool: bash
   Arguments: {
     "command": "rm -f *.log"
   }

Approve this tool call? [y/n]: n
Optional feedback for the agent (press Enter to skip): Too dangerous, just list them first

bash {rm -f *.log}
Observations:
User rejected this tool call. User comment: Too dangerous, just list them first

⏱️ 4s

🔧 Tool call requested:
   Tool: bash
   Arguments: {
     "command": "ls -la *.log"
   }

Approve this tool call? [y/n]: y

bash {ls -la *.log}
Observations:
-rw-r--r--  1 user  staff  12345 Jan 12 14:22 app.log
-rw-r--r--  1 user  staff   4567 Jan 13 09:15 error.log

✅ Found 2 log files in the current directory
```

## Usage Examples

### Docker Operations (Primary Strength)

```bash
# Build and manage images
devops-agent "Build Docker image for Node.js application"

# Container management
devops-agent "Run Docker container with environment variables"

# Docker Compose
devops-agent "Setup Docker Compose for local development"

# Optimization
devops-agent "Optimize Docker image to reduce size"

# Debugging
devops-agent "Debug Docker container networking issues"
```

### Kubernetes Operations (Primary Strength)

```bash
# List pods
devops-agent "Get all pods in default namespace"

# Deployments
devops-agent "Scale Kubernetes deployment manually"

# Services
devops-agent "Expose Kubernetes deployment with service"

# Configuration
devops-agent "Configure liveness probe for Kubernetes pod"

# Environment
devops-agent "Configure environment variables in Kubernetes pod"
```

### File Operations

```bash
# Read a file
devops-agent "Read the contents of /etc/hosts"

# Write a file
devops-agent "Create a Dockerfile that prints Hello World"

# List files
devops-agent "List all .py files in the current directory"
```

### System Operations

```bash
# Check system resources
devops-agent "Check disk usage and available memory"

# Environment variables
devops-agent "Get the value of PATH environment variable"

# Run commands
devops-agent "Show running Docker containers"
```

### Complex Multi-Step Tasks

```bash
# Build and validate
devops-agent "Create a Dockerfile, then check if it exists"

# Deploy workflow
devops-agent "Get DOCKER_USER from environment and create a Dockerfile using it"
```

## Available Tools

The agent has access to these tools:

| Tool | Description | Example |
|------|-------------|---------|
| `read_file` | Read content from a file | Reading config files |
| `write_file` | Write content to a file | Creating Dockerfiles, scripts |
| `bash` | Execute shell commands | ls, kubectl, docker, etc. |
| `get_env` | Get environment variables | AWS credentials, PATH |
| `final_answer` | Return final result | Completing the task |

## Model Information

**Base Model**: Qwen3-1.7B
**Fine-tuning**: Custom DevOps dataset with multi-turn tool calling examples
**Format**: GGUF Q4_K_M quantization (1GB)
**Performance**: Optimized for sequential tool execution with validation

**Key Improvements over Base Model**:
- Structured reasoning with explicit planning steps
- One tool call per response (prevents calling all tools at once)
- Uses actual values from tool responses in subsequent calls
- Validates each step before proceeding
- Better error handling and retry logic

## Architecture

```
┌─────────────────┐
│   User Query    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  agent.py       │  CLI interface
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  DevOpsAgent    │  SmolAgents ToolCallingAgent
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ ollama_backend  │  Custom Ollama backend
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Ollama (Local)  │  qwen3-devops model
└─────────────────┘
```

## Configuration

### Change Model Name

Edit `agent.py` line 151:

```python
model = OllamaChat(model="qwen3-devops")
```

### Change Ollama Endpoint

Edit `agent.py` line 151:

```python
model = OllamaChat(
    model="qwen3-devops",
    endpoint="http://your-server:11434/api/chat"
)
```

### Adjust Model Parameters

Edit `Modelfile` and recreate the model:

```
PARAMETER temperature 0.7    # Lower for more deterministic (e.g., 0.3)
PARAMETER top_p 0.9          # Sampling threshold
PARAMETER num_predict 512    # Max tokens per response
```

Then recreate: `ollama create qwen3-devops -f Modelfile`

### Enable Debug Logging

```bash
SMOLAGENTS_LOG_LEVEL=DEBUG devops-agent "Your query here"
```

## Performance

- **First response**: ~up to 30 seconds (model loading)
- **Subsequent responses**: ~3-4 seconds per tool call
- **Multi-step tasks**: ~10 seconds total for 2-3 step workflows
- **Memory usage**: ~1.5GB RAM for model + inference

### Performance Tips

1. **Keep Ollama running**: Pre-load model to avoid startup delay
   ```bash
   ollama run qwen3-devops "hello"
   ```

2. **Reduce temperature**: For more deterministic outputs, lower temperature to 0.3-0.5

3. **Adjust max_steps**: Edit `agent.py` line 165 to limit steps (default: 4)

## Troubleshooting

### Error: "Cannot connect to Ollama"

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve
```

### Error: "Model not found"

```bash
# List installed models
ollama list

# If missing, recreate the model
ollama create qwen3-devops -f Modelfile
```

### Error: "No such file: qwen3-devops.gguf"

Make sure you've downloaded the GGUF file from Hugging Face and placed it in the repository directory.

### Agent gets stuck or loops

- The backend has built-in safety to prevent infinite loops (max_steps=4)
- Check output for validation warnings
- The model automatically validates each tool call before proceeding

### Slow responses

- First response is slow due to model loading (~2-3 seconds)
- Subsequent responses are faster (~1-2 seconds)
- Keep Ollama running in background for faster startup

## Security Considerations

**Important:** This tool is designed for **local DevOps automation** on trusted environments.

- ⚠️ Uses `shell=True` for command execution (convenient but potentially unsafe)
- ⚠️ No input sanitization or command whitelisting
- ⚠️ Full access to file system and shell commands

**Do NOT expose this tool to untrusted users or networks.**

**Security Enhancement - Approval Mode:**
- Use `--require-approval` or `-a` flag to enable user confirmation before tool execution
- Each tool call will require explicit approval (y/n)
- Rejections can include feedback comments that guide the agent to try alternative approaches
- Recommended for sensitive operations or when testing new workflows

For production use, consider:
- Using approval mode (`--require-approval`) for all operations
- Adding command whitelisting
- Implementing proper input validation
- Running in Docker containers with limited permissions
- Using dedicated service accounts with minimal privileges

## How It Works

1. **User Input**: Query provided via CLI
2. **SmolAgents**: Orchestrates the agent loop and tool calling
3. **Ollama Backend**: Custom backend that formats prompts and parses tool calls
4. **Sequential Execution**: Model calls one tool, waits for response, then proceeds
5. **Validation**: Each tool output is checked before next step
6. **Result**: Final answer returned to user

### Key Features of the Backend

- **Custom System Prompt**: Strict instructions to enforce one-tool-at-a-time execution
- **Tool Call Parsing**: Regex-based parsing of XML `<tool_call>` format
- **Safety Filter**: Automatically strips `final_answer` when combined with other tools
- **Tool Response Formatting**: Explicit "The value is: ..." format for better value extraction

## Development

### Project Structure

```
ollama_devops/
├── agent.py              # Main CLI and agent definition
├── ollama_backend.py     # Custom Ollama backend for SmolAgents
├── smolagents_patches.py # Output filtering patches
├── Modelfile             # Ollama model configuration
├── test_agent.py         # Unit tests
├── README.md             # This file
└── tests/                # Test scripts
```

### Testing

Run the test suite to verify functionality:

```bash
# Install pytest (included in requirements.txt)
pip install pytest

# Run all tests
pytest test_agent.py -v

# Run with coverage
pytest test_agent.py --cov=agent --cov-report=html
```

The test suite includes:
- **Tool Tests**: Unit tests for `read_file`, `write_file`, `bash`, and `get_env`
- **Agent Tests**: Initialization, verbose mode, and approval mode functionality
- **Integration Tests**: End-to-end workflows combining multiple tools

All 16 tests should pass on a properly configured system.

### Docker Image Publishing (For Maintainers)

The repository includes automated Docker image publishing via GitHub Actions:

**Setup Requirements:**
1. **GitHub Container Registry** (automatic with GITHUB_TOKEN)
2. **Docker Hub** (requires secrets):
   - `DOCKERHUB_USERNAME`: Your Docker Hub username
   - `DOCKERHUB_TOKEN`: Docker Hub access token

**Automatic Publishing:**
- **On push to main**: Creates `latest` tag
- **On version tags** (v*): Creates versioned tags (e.g., `v1.0.0`, `1.0`, `1`)
- **Multi-architecture**: Builds for `linux/amd64` and `linux/arm64`
- **Registries**: Publishes to both GitHub Container Registry and Docker Hub

**Manual Image Build:**
```bash
# Build locally
docker build -t ollama-devops .

# Test the image
docker run -it --rm ollama-devops --help
```

**Release Process:**
```bash
# Create and push a version tag
git tag v1.0.0
git push origin v1.0.0

# GitHub Actions will automatically:
# - Build multi-arch images
# - Push to ghcr.io/ubermorgenland/ollama_devops:v1.0.0
# - Push to ubermorgenai/ollama-devops:v1.0.0
# - Update latest tags
```

### Adding New Tools

```python
@tool
def my_tool(arg: str) -> str:
    """
    Tool description here.

    Args:
        arg (str): Argument description.

    Returns:
        str: Return value description.
    """
    # Your implementation
    return "result"

# Add to agent
agent = DevOpsAgent(
    tools=[read_file, write_file, bash, get_env, my_tool],
    model=model,
    instructions="..."
)
```

### Running Tests

```bash
# Run with debug logging and save output
SMOLAGENTS_LOG_LEVEL=DEBUG devops-agent "test query" 2>&1 | tee test_output.log
```

## Limitations

- **Training Focus**: Optimized for Docker and Kubernetes workflows. Limited training on:
  - Cloud CLIs (gcloud, AWS CLI, Azure CLI)
  - General system administration
  - Database operations
- **Model Size**: 1.7B parameter model may make mistakes on complex tasks
- **No Memory Between Queries**: Each query in interactive mode is independent (no conversation history)
- **Local Only**: Requires Ollama running locally
- **Max Steps**: Limited to 15 steps by default (configurable)

## Extensibility

This project uses a modular backend architecture. While it currently ships with the `ollama_backend.py` for local Ollama models, the design supports:

- **Alternative Model Backends**: Support for other inference engines (llama.cpp, API-based models, etc.) can be added based on user requests
- **Larger Models**: The codebase supports any GGUF model - you can use larger models (3B, 7B, 14B) by updating the `Modelfile`
- **Custom Tools**: Easy to add new tools using the `@tool` decorator (see CONTRIBUTING.md)

If you need support for a specific model format or backend, please open an issue describing your use case.

## Future Enhancements

- [x] Interactive mode (REPL with clean output)
- [x] Docker containerization
- [ ] Conversation history management (multi-turn context)
- [ ] Better error handling with retry logic
- [ ] Command whitelisting for security
- [ ] Web UI interface
- [ ] KV cache optimization for faster responses

## License

MIT License - Use at your own risk

## Contributing

This is a local DevOps automation tool. Feel free to fork and customize for your needs.

## Citation

If you use this model or codebase, please cite:

```
@misc{qwen3-devops,
  title={Qwen3-1.7B Fine-tuned for DevOps Automation},
  author={ApInference},
  year={2025},
  url={https://github.com/yourusername/ollama_devops}
}
```

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
- **Docker workflows (44%)**: Building images, containers, Docker Compose, optimization
- **Kubernetes operations (24%)**: Pods, deployments, services, configurations
- **General DevOps (32%)**: File operations, system commands, basic troubleshooting

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

### 1. Prerequisites

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
pip install smolagents requests
```

### 2. Download the Model

Download the fine-tuned GGUF model (1GB) from Google Drive:

**Google Drive Folder**: https://drive.google.com/drive/folders/1tbLCJFDukULHMljylGKYRWLciV78L3TP?usp=drive_link

1. Navigate to the folder and download `qwen-devops-442-q4_k_m.gguf`
2. Place the file in this repository directory (same location as `Modelfile`)

Alternatively, if you have `gdown` installed:

```bash
# Install gdown
pip install gdown

# Download directly (you may need to adjust the file ID)
gdown --folder https://drive.google.com/drive/folders/1tbLCJFDukULHMljylGKYRWLciV78L3TP
mv qwen-devops-442-q4_k_m.gguf .
```

**Note**: Make sure the GGUF file is in the same directory as the `Modelfile`.

### 3. Create Ollama Model

```bash
ollama create qwen-devops-v2 -f Modelfile
```

### 4. Run the Agent

**Single query mode:**
```bash
python agent.py "Get all pods in default namespace"
```

**Interactive mode (REPL):**
```bash
python agent.py
# OR
python agent.py --interactive
```

**Verbose mode (show detailed execution):**
```bash
python agent.py "Your query" --verbose
```

**Approval mode (require confirmation before executing tools):**
```bash
# Interactive mode with approval
python agent.py --require-approval
# OR use shorthand
python agent.py -a

# Combine with interactive mode
python agent.py -i -a

# Single query with approval
python agent.py --require-approval "List all Docker containers"

# Using environment variable
REQUIRE_APPROVAL=1 python agent.py
```

## Interactive Mode

The agent supports an interactive REPL (Read-Eval-Print Loop) for continuous task execution:

```bash
python agent.py
```

**Features:**
- Execute multiple tasks in one session
- Real-time thinking indicator with timer
- Clean output showing only tool calls and observations
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
python agent.py --verbose  # Show detailed execution steps
```

**Approval mode (with example):**
```
$ python agent.py -i -a

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
python agent.py "Build Docker image for Node.js application"

# Container management
python agent.py "Run Docker container with environment variables"

# Docker Compose
python agent.py "Setup Docker Compose for local development"

# Optimization
python agent.py "Optimize Docker image to reduce size"

# Debugging
python agent.py "Debug Docker container networking issues"
```

### Kubernetes Operations (Primary Strength)

```bash
# List pods
python agent.py "Get all pods in default namespace"

# Deployments
python agent.py "Scale Kubernetes deployment manually"

# Services
python agent.py "Expose Kubernetes deployment with service"

# Configuration
python agent.py "Configure liveness probe for Kubernetes pod"

# Environment
python agent.py "Configure environment variables in Kubernetes pod"
```

### File Operations

```bash
# Read a file
python agent.py "Read the contents of /etc/hosts"

# Write a file
python agent.py "Create a Dockerfile that prints Hello World"

# List files
python agent.py "List all .py files in the current directory"
```

### System Operations

```bash
# Check system resources
python agent.py "Check disk usage and available memory"

# Environment variables
python agent.py "Get the value of PATH environment variable"

# Run commands
python agent.py "Show running Docker containers"
```

### Complex Multi-Step Tasks

```bash
# Build and validate
python agent.py "Create a Dockerfile, then check if it exists"

# Deploy workflow
python agent.py "Get DOCKER_USER from environment and create a Dockerfile using it"
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

<!-- FOR PUBLIC RELEASE: Remove training specifics below this line -->

**Training Details** (internal):
- Dataset: 442 multi-turn DevOps conversations
  - Docker workflows: 195 examples (44%)
  - Kubernetes operations: 108 examples (24%)
  - General DevOps: 139 examples (32%)
- Method: Two-stage curriculum learning
  - Stage 1: Initial reasoning and first tool call (2 epochs)
  - Stage 2: Sequential tool execution with context (1 epoch)
- Retention: 94% of examples after validation
- Training time: ~30 minutes on NVIDIA L4 GPU
- Tool usage: bash (77%), write_file (15%), final_answer (7%), read_file (1%)

<!-- END INTERNAL SECTION -->

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
│ Ollama (Local)  │  qwen-devops-v2 model
└─────────────────┘
```

## Configuration

### Change Model Name

Edit `agent.py` line 151:

```python
model = OllamaChat(model="qwen-devops-v2")
```

### Change Ollama Endpoint

Edit `agent.py` line 151:

```python
model = OllamaChat(
    model="qwen-devops-v2",
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

Then recreate: `ollama create qwen-devops-v2 -f Modelfile`

### Enable Debug Logging

```bash
SMOLAGENTS_LOG_LEVEL=DEBUG python agent.py "Your query here"
```

## Performance

- **First response**: ~2-3 seconds (model loading)
- **Subsequent responses**: ~1-2 seconds per tool call
- **Multi-step tasks**: ~10 seconds total for 2-3 step workflows
- **Memory usage**: ~1.5GB RAM for model + inference

### Performance Tips

1. **Keep Ollama running**: Pre-load model to avoid startup delay
   ```bash
   ollama run qwen-devops-v2 "hello"
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
ollama create qwen-devops-v2 -f Modelfile
```

### Error: "No such file: qwen-devops-442-q4_k_m.gguf"

Make sure you've downloaded the GGUF file from Google Drive and placed it in the repository directory.

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
├── Modelfile             # Ollama model configuration
├── README.md             # This file
└── tests/                # Test scripts
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
SMOLAGENTS_LOG_LEVEL=DEBUG python agent.py "test query" 2>&1 | tee test_output.log
```

## Limitations

- **Training Focus**: Optimized for Docker (44%) and Kubernetes (24%) workflows. Limited training on:
  - Cloud CLIs (gcloud, AWS CLI, Azure CLI)
  - General system administration
  - Database operations
- **Model Size**: 1.7B parameter model may make mistakes on complex tasks
- **No Memory Between Queries**: Each query in interactive mode is independent (no conversation history)
- **Local Only**: Requires Ollama running locally
- **Max Steps**: Limited to 15 steps by default (configurable)

## Future Enhancements

- [x] Interactive mode (REPL with clean output)
- [ ] Conversation history management (multi-turn context)
- [ ] Better error handling with retry logic
- [ ] Command whitelisting for security
- [ ] Support for larger models (7B, 13B)
- [ ] Web UI interface
- [ ] Docker containerization
- [ ] KV cache optimization for faster responses

## License

MIT License - Use at your own risk

## Contributing

This is a local DevOps automation tool. Feel free to fork and customize for your needs.

## Citation

If you use this model or codebase, please cite:

```
@misc{qwen-devops-v2,
  title={Qwen3-1.7B Fine-tuned for DevOps Automation},
  author={ApInference},
  year={2025},
  url={https://github.com/yourusername/ollama_devops}
}
```

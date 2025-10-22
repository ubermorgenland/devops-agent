# Ollama DevOps Agent

A lightweight AI-powered DevOps automation tool using Ollama and SmolAgents. Designed for local development and automation tasks on resource-constrained environments (2 CPU, 4GB RAM).

## Features

- **Tool Calling Agent**: Execute shell commands, read/write files, and access environment variables
- **Ollama Backend**: Uses local Ollama models (no cloud API required)
- **Resource Efficient**: Optimized for small VMs with limited specs
- **CLI Interface**: Easy command-line usage for quick DevOps tasks

## Prerequisites

### 1. Install Ollama

```bash
# macOS/Linux
curl -fsSL https://ollama.com/install.sh | sh

# Or download from https://ollama.com/download
```

### 2. Pull the Model

```bash
ollama pull hf.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF:Q6_K
```

**Note:** For lower memory usage (< 4GB RAM), use the Q4_K quantization:
```bash
ollama pull hf.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF:Q4_K
```

### 3. Install Python Dependencies

```bash
pip install smolagents requests
```

## Quick Start

### Basic Usage

```bash
# Run with custom query
python agent.py "List all Python files in the current directory"

# Run with default query
python agent.py
```

### Enable Debug Logging

```bash
SMOLAGENTS_LOG_LEVEL=DEBUG python agent.py "Your query here"
```

## Usage Examples

### File Operations

```bash
# Read a file
python agent.py "Read the contents of /etc/hosts"

# Write a file
python agent.py "Create a Dockerfile that prints Hello World"

# List files
python agent.py "Use ls command to list all .py files"
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

### DevOps Tasks

```bash
# Deploy configuration
python agent.py "Copy nginx.conf to /etc/nginx/ and validate the config"

# Check service status
python agent.py "Check if nginx is running and show its status"

# Create deployment script
python agent.py "Write a bash script that deploys the app to /opt/myapp"
```

## Available Tools

The agent has access to these tools:

| Tool | Description | Example |
|------|-------------|---------|
| `read_file` | Read content from a file | Reading config files |
| `write_file` | Write content to a file | Creating Dockerfiles, scripts |
| `run_command` | Execute shell commands | ls, ps, docker, etc. |
| `get_env` | Get environment variables | AWS credentials, PATH |

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
│ Ollama (Local)  │  Running on :11434
└─────────────────┘
```

## Configuration

### Change Model

Edit `agent.py` line 76:

```python
model = OllamaChat(model="hf.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF:Q6_K")
```

Recommended models:
- `hf.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF:Q6_K` - Better quality (default)
- `hf.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF:Q4_K` - Lower memory usage
- `codellama:7b-instruct` - Alternative coder model

### Change Ollama Endpoint

Edit `agent.py` line 76:

```python
model = OllamaChat(
    model="your-model",
    endpoint="http://your-server:11434/api/chat"
)
```

## Performance Optimization

### For Low Memory (< 4GB RAM)

1. Use smaller quantization:
   ```bash
   ollama pull hf.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF:Q4_K
   ```

2. Keep Ollama running in background to avoid model loading time:
   ```bash
   ollama serve &
   ```

### For Faster Responses

1. Pre-load the model:
   ```bash
   ollama run hf.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF:Q6_K "hello"
   ```

2. Use smaller context window (future enhancement)

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

# Pull the required model
ollama pull hf.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF:Q6_K
```

### Agent gets stuck or loops

- The backend has built-in safety to prevent infinite loops
- Check the output for warnings like:
  ```
  ⚠️ WARNING: Model tried to call final_answer with other tools
  ```
- This is automatically corrected by the backend

### Slow responses

- First response is slow due to model loading (~2-5 seconds)
- Subsequent responses are faster (~0.5-1 second)
- Keep Ollama running in background for faster startup

## Security Considerations

**Important:** This tool is designed for **local DevOps automation** on trusted VMs.

- ⚠️ Uses `shell=True` for command execution (convenient but potentially unsafe)
- ⚠️ No input sanitization or command whitelisting
- ⚠️ Full access to file system and shell commands

**Do NOT expose this tool to untrusted users or networks.**

For production use, consider:
- Adding command whitelisting
- Implementing proper input validation
- Running in Docker containers with limited permissions
- Using dedicated service accounts with minimal privileges

## How It Works

1. **User Input**: Query provided via CLI
2. **SmolAgents**: Orchestrates the agent loop and tool calling
3. **Ollama Backend**: Custom backend that formats prompts and parses tool calls
4. **Tool Execution**: Agent executes tools (file ops, shell commands, etc.)
5. **Result**: Final answer returned to user

### Key Features of the Backend

- **Custom Prompt Engineering**: Strict instructions to prevent infinite loops
- **Tool Call Parsing**: Regex-based parsing of `Tool:name({"args": "value"})` format
- **Safety Filter**: Automatically strips `final_answer` when combined with other tools
- **System Context**: Includes OS, Python version, Docker availability in prompts

## Development

### Project Structure

```
ollama_devops/
├── agent.py              # Main CLI and agent definition
├── ollama_backend.py     # Custom Ollama backend for SmolAgents
├── test_output.log       # Latest test run output
├── Dockerfile            # Generated by agent (example)
└── README.md            # This file
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
    tools=[read_file, write_file, run_command, get_env, my_tool],
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

- **Model Limitations**: Small 1.5B model may hallucinate or make mistakes
- **No Memory**: Each run is independent (no conversation history between runs)
- **Local Only**: Requires Ollama running locally
- **Single Query**: Processes one query at a time (no interactive mode)

## Future Enhancements

- [ ] Interactive mode (chat-like interface)
- [ ] Conversation history management
- [ ] Better error handling with try/catch blocks
- [ ] Command whitelisting for security
- [ ] Support for larger models
- [ ] Web UI interface
- [ ] Docker containerization

## License

MIT License - Use at your own risk

## Contributing

This is a local DevOps automation tool. Feel free to fork and customize for your needs.

## Credits

- Built with [SmolAgents](https://github.com/huggingface/smolagents)
- Powered by [Ollama](https://ollama.com/)
- Uses [Qwen2.5-Coder](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF) model

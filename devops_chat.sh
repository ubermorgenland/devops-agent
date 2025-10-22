curl -s http://localhost:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "hf.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF:Q6_K",
    "messages": [
      {
        "role": "user",
        "content": "Read AWS credentials from the environment and write a Dockerfile that uses them to print DOCKER_USER."
      }
    ],
    "stream": false,
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "read_file",
          "description": "Read the content of a file",
          "parameters": {
            "type": "object",
            "required": ["path"],
            "properties": {
              "path": {"type": "string", "description": "The path of the file to read"}
            }
          }
        }
      },
      {
        "type": "function",
        "function": {
          "name": "write_file",
          "description": "Write content to a file",
          "parameters": {
            "type": "object",
            "required": ["path", "content"],
            "properties": {
              "path": {"type": "string", "description": "The path of the file"},
              "content": {"type": "string", "description": "The content to write"}
            }
          }
        }
      },
      {
        "type": "function",
        "function": {
          "name": "run_command",
          "description": "Run a shell command and return its output",
          "parameters": {
            "type": "object",
            "required": ["command"],
            "properties": {
              "command": {"type": "string", "description": "Shell command to execute"}
            }
          }
        }
      },
      {
        "type": "function",
        "function": {
          "name": "get_env",
          "description": "Get the value of an environment variable",
          "parameters": {
            "type": "object",
            "required": ["key"],
            "properties": {
              "key": {"type": "string", "description": "Name of the environment variable"}
            }
          }
        }
      }
    ]
  }' | jq


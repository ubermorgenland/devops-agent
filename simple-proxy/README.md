# Simple Proxy

A middleware proxy for Claude Code that automatically filters large log files using AI summarization.

## What It Does

- Intercepts Read tool calls when Claude tries to read large files (>1KB)
- Uses AI (OpenRouter/gpt-oss-120b) to detect if files are log files and summarize them
- Replaces large log files with filtered versions containing only errors, warnings, and important events
- Significantly reduces token usage when analyzing logs

## Setup

**1. Install dependencies:**
```bash
pip install openai
```

**2. Set OpenRouter API key:**
```bash
export OPENROUTER_API_KEY='your-api-key'
```
Get your free API key at: https://openrouter.ai/

**3. Start the proxy:**
```bash
./simple-proxy.py --log-file proxy.log
```

**4. Configure Claude Code:**
```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:3456"
claude "analyze errors in app.log"
```

The proxy will automatically:
1. Detect when Claude tries to read a large log file
2. Filter it using AI to extract only important content
3. Send the filtered version to Claude
4. Inject instructions telling Claude to use only the filtered version

## Testing

Use `generate_test_log.py` (in parent directory) to create dummy log files for testing:

```bash
python ../generate_test_log.py test.log 2  # Creates 2MB test log
```

## Disclaimer

⚠️ **Proof of Concept - Use at Your Own Risk**

This is an experimental proxy for demonstration purposes. It modifies API requests and responses in real-time. Not intended for production use.

## Requirements

- Python 3.8+
- OpenAI package: `pip install openai`
- OpenRouter API key (free tier available at https://openrouter.ai/)
# Contributing to Ollama DevOps Agent

Thank you for your interest in contributing to the Ollama DevOps Agent! This document provides guidelines for contributing to the project.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and collaborative environment for everyone.

## How to Contribute

### Reporting Bugs

If you find a bug, please create an issue with:
- A clear, descriptive title
- Steps to reproduce the issue
- Expected vs. actual behavior
- Your environment (OS, Python version, Ollama version)
- Relevant logs or error messages

### Suggesting Enhancements

Enhancement suggestions are welcome! Please create an issue with:
- A clear description of the proposed feature
- Use cases and benefits
- Possible implementation approach (optional)

### Pull Requests

1. **Fork the repository** and create a new branch from `main`
2. **Make your changes** following our coding standards
3. **Test your changes** thoroughly
4. **Update documentation** if needed (README, code comments)
5. **Submit a pull request** with a clear description of changes

#### Pull Request Guidelines

- Keep changes focused on a single issue/feature
- Write clear, descriptive commit messages
- Update tests and documentation as needed
- Ensure all tests pass
- Follow the existing code style

## Development Setup

1. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/ollama-devops.git
   cd ollama-devops
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the install script:
   ```bash
   ./install.sh
   ```

4. Test your changes:
   ```bash
   python3 agent.py "Test query here"
   ```

## Coding Standards

- Follow PEP 8 style guidelines
- Write descriptive variable and function names
- Add docstrings to all functions and classes
- Keep functions focused and modular
- Add type hints where appropriate

Example:
```python
def process_command(command: str, args: dict) -> str:
    """
    Process a command with given arguments.
    
    Args:
        command: The command to execute
        args: Dictionary of command arguments
    
    Returns:
        The command output as a string
    """
    # Implementation here
    pass
```

## Testing

- Test on multiple platforms (macOS, Linux) when possible
- Test with different Python versions (3.8+)
- Include both success and error cases
- Test edge cases and error handling

## Documentation

- Update README.md for user-facing changes
- Add inline comments for complex logic
- Update examples if behavior changes
- Keep documentation clear and concise

## Commit Messages

Use clear, descriptive commit messages:

**Good:**
- `Fix: Handle empty responses from tool calls`
- `Feature: Add approval mode for tool execution`
- `Docs: Update installation instructions for Linux`

**Avoid:**
- `fix bug`
- `update code`
- `changes`

## Project Structure

```
ollama_devops/
├── agent.py              # Main agent CLI
├── ollama_backend.py     # Ollama model backend
├── smolagents_patches.py # Output filtering patches
├── Modelfile             # Ollama model config
├── README.md             # Project documentation
├── requirements.txt      # Python dependencies
└── install.sh            # Automated setup script
```

## Adding New Tools

To add a new tool to the agent:

1. Define the tool using the `@tool` decorator:
   ```python
   @tool
   def my_new_tool(param: str) -> str:
       """
       Description of what this tool does.
       
       Args:
           param: Description of parameter
       
       Returns:
           Description of return value
       """
       # Implementation
       return result
   ```

2. Add the tool to the agent's tool list:
   ```python
   agent = DevOpsAgent(
       tools=[read_file, write_file, bash, get_env, my_new_tool],
       model=model,
       instructions="..."
   )
   ```

3. Update documentation and tests

## Questions?

If you have questions about contributing:
- Check existing issues and discussions
- Create a new issue with the `question` label
- Reach out to the maintainers

## License

By contributing to this project, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to Ollama DevOps Agent!

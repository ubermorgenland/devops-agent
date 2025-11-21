"""
Unit tests for Ollama DevOps Agent
Run with: pytest test_agent.py -v
"""

import os
import tempfile
import pytest
from unittest.mock import Mock, patch, MagicMock
from agent import read_file, write_file, bash, get_env, DevOpsAgent


class TestTools:
    """Test individual tool functions"""

    def test_read_file_success(self):
        """Test reading an existing file"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("test content")
            temp_path = f.name

        try:
            result = read_file(temp_path)
            assert "test content" in result
        finally:
            os.unlink(temp_path)

    def test_read_file_not_found(self):
        """Test reading non-existent file raises exception"""
        with pytest.raises(FileNotFoundError):
            read_file("/nonexistent/file.txt")

    def test_write_file_success(self):
        """Test writing to a file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test.txt")
            content = "Hello World"

            result = write_file(filepath, content)
            assert "wrote" in result.lower()
            assert "bytes" in result.lower()

            # Verify file was created
            assert os.path.exists(filepath)
            with open(filepath, 'r') as f:
                assert f.read() == content

    def test_write_file_invalid_path(self):
        """Test writing to invalid path raises exception"""
        with pytest.raises(FileNotFoundError):
            write_file("/invalid/path/file.txt", "content")

    def test_bash_simple_command(self):
        """Test executing a simple bash command"""
        result = bash("echo 'test'")
        assert "test" in result

    def test_bash_list_directory(self):
        """Test listing directory"""
        result = bash("ls -la /tmp")
        assert len(result) > 0

    def test_bash_invalid_command(self):
        """Test handling invalid command"""
        result = bash("nonexistent_command_xyz")
        assert "error" in result.lower() or "not found" in result.lower() or "exit code" in result.lower()

    def test_bash_empty_output_returns_exit_code(self):
        """Test that bash returns exit code when command produces no output"""
        # mkdir command typically produces no output
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = os.path.join(tmpdir, "test_subdir")
            result = bash(f"mkdir {test_dir}")
            # Should return exit code message
            assert "exit code" in result.lower()
            # Should indicate success (exit code 0)
            assert "0" in result

    def test_bash_with_output_returns_output(self):
        """Test that bash returns output when command produces output"""
        result = bash("echo 'hello world'")
        # Should return actual output, not exit code
        assert "hello world" in result.lower()
        assert "exit code" not in result.lower()

    def test_get_env_existing(self):
        """Test getting existing environment variable"""
        os.environ['TEST_VAR'] = 'test_value'
        result = get_env('TEST_VAR')
        assert 'test_value' in result
        del os.environ['TEST_VAR']

    def test_get_env_nonexistent(self):
        """Test getting non-existent environment variable"""
        result = get_env('NONEXISTENT_VAR_XYZ')
        assert 'not set' in result.lower() or 'error' in result.lower()


class TestDevOpsAgent:
    """Test DevOpsAgent class functionality"""

    @patch('agent.OllamaChat')
    def test_agent_initialization(self, mock_ollama):
        """Test agent can be initialized"""
        mock_model = Mock()
        mock_ollama.return_value = mock_model

        agent = DevOpsAgent(
            tools=[read_file, write_file, bash, get_env],
            model=mock_model,
            instructions="Test instructions"
        )

        assert agent is not None
        # Agent has 5 tools: 4 provided + final_answer
        assert len(agent.tools) == 5
        assert 'final_answer' in agent.tools

    @patch('agent.OllamaChat')
    def test_agent_verbose_mode(self, mock_ollama):
        """Test verbose mode can be enabled"""
        os.environ['VERBOSE'] = '1'
        mock_model = Mock()
        mock_ollama.return_value = mock_model

        agent = DevOpsAgent(
            tools=[read_file, write_file, bash, get_env],
            model=mock_model,
            instructions="Test instructions"
        )

        assert agent.verbose == True
        del os.environ['VERBOSE']

    @patch('agent.OllamaChat')
    def test_agent_approval_mode_enabled_by_default(self, mock_ollama):
        """Test approval mode is enabled by default"""
        # Remove REQUIRE_APPROVAL if set
        if 'REQUIRE_APPROVAL' in os.environ:
            del os.environ['REQUIRE_APPROVAL']

        mock_model = Mock()
        mock_ollama.return_value = mock_model

        agent = DevOpsAgent(
            tools=[read_file, write_file, bash, get_env],
            model=mock_model,
            instructions="Test instructions"
        )

        # Should be enabled by default
        assert agent.require_approval == True

    @patch('agent.OllamaChat')
    def test_agent_approval_mode_can_be_disabled(self, mock_ollama):
        """Test approval mode can be disabled with REQUIRE_APPROVAL=0"""
        os.environ['REQUIRE_APPROVAL'] = '0'
        mock_model = Mock()
        mock_ollama.return_value = mock_model

        agent = DevOpsAgent(
            tools=[read_file, write_file, bash, get_env],
            model=mock_model,
            instructions="Test instructions"
        )

        assert agent.require_approval == False
        del os.environ['REQUIRE_APPROVAL']

    @patch('agent.OllamaChat')
    def test_agent_approval_mode_explicit_enable(self, mock_ollama):
        """Test approval mode can be explicitly enabled"""
        os.environ['REQUIRE_APPROVAL'] = '1'
        mock_model = Mock()
        mock_ollama.return_value = mock_model

        agent = DevOpsAgent(
            tools=[read_file, write_file, bash, get_env],
            model=mock_model,
            instructions="Test instructions"
        )

        assert agent.require_approval == True
        del os.environ['REQUIRE_APPROVAL']

    @patch('agent.OllamaChat')
    @patch('builtins.input', return_value='y')
    def test_agent_approval_accepted(self, mock_input, mock_ollama):
        """Test tool call approval when user accepts"""
        os.environ['REQUIRE_APPROVAL'] = '1'
        mock_model = Mock()
        mock_ollama.return_value = mock_model

        agent = DevOpsAgent(
            tools=[read_file, write_file, bash, get_env],
            model=mock_model,
            instructions="Test instructions"
        )

        approved, comment = agent.ask_user_approval("bash", {"command": "ls"})
        assert approved == True
        assert comment == ""

        del os.environ['REQUIRE_APPROVAL']

    @patch('agent.OllamaChat')
    @patch('builtins.input', side_effect=['n', 'test feedback'])
    def test_agent_approval_rejected(self, mock_input, mock_ollama):
        """Test tool call approval when user rejects"""
        os.environ['REQUIRE_APPROVAL'] = '1'
        mock_model = Mock()
        mock_ollama.return_value = mock_model

        agent = DevOpsAgent(
            tools=[read_file, write_file, bash, get_env],
            model=mock_model,
            instructions="Test instructions"
        )

        approved, comment = agent.ask_user_approval("bash", {"command": "rm -rf /"})
        assert approved == False
        assert "test feedback" in comment

        del os.environ['REQUIRE_APPROVAL']

    @patch('agent.OllamaChat')
    def test_agent_repetition_detection(self, mock_ollama):
        """Test that agent detects repeated tool calls"""
        os.environ['REQUIRE_APPROVAL'] = '0'  # Disable approval for easier testing
        mock_model = Mock()
        mock_ollama.return_value = mock_model

        agent = DevOpsAgent(
            tools=[read_file, write_file, bash, get_env],
            model=mock_model,
            instructions="Test instructions"
        )

        # First call should succeed
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test")
            temp_path = f.name

        try:
            # First call
            result1 = agent.execute_tool_call("read_file", {"path": temp_path})
            assert result1 is not None

            # Second call with same parameters should raise ValueError
            with pytest.raises(ValueError, match="REPETITION DETECTED"):
                agent.execute_tool_call("read_file", {"path": temp_path})
        finally:
            os.unlink(temp_path)
            del os.environ['REQUIRE_APPROVAL']

    @patch('agent.OllamaChat')
    def test_agent_hallucination_prevention(self, mock_ollama):
        """Test that agent prevents final_answer without tool execution"""
        os.environ['REQUIRE_APPROVAL'] = '0'
        mock_model = Mock()
        mock_ollama.return_value = mock_model

        agent = DevOpsAgent(
            tools=[read_file, write_file, bash, get_env],
            model=mock_model,
            instructions="Test instructions"
        )

        # Calling final_answer without any prior tool calls should raise ValueError
        with pytest.raises(ValueError, match="HALLUCINATION ALERT"):
            agent.execute_tool_call("final_answer", {"answer": "fake answer"})

        del os.environ['REQUIRE_APPROVAL']


class TestIntegration:
    """Integration tests for full workflows"""

    def test_file_read_write_workflow(self):
        """Test writing and then reading a file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "integration_test.txt")
            content = "Integration test content"

            # Write file
            write_result = write_file(filepath, content)
            assert "wrote" in write_result.lower()

            # Read file back
            read_result = read_file(filepath)
            assert content in read_result

    def test_bash_and_env_workflow(self):
        """Test setting env var and reading it"""
        os.environ['INTEGRATION_TEST'] = 'success'

        # Get env var via tool
        env_result = get_env('INTEGRATION_TEST')
        assert 'success' in env_result

        # Get env var via bash
        bash_result = bash('echo $INTEGRATION_TEST')
        assert 'success' in bash_result

        del os.environ['INTEGRATION_TEST']


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

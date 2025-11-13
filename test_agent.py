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
        assert "error" in result.lower() or "not found" in result.lower()

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
    def test_agent_approval_mode(self, mock_ollama):
        """Test approval mode can be enabled"""
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

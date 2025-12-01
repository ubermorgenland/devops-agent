#!/usr/bin/env python3
"""
Test the large file fallback functionality
"""
import os
import sys
import json
import tempfile

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from agent import read_file, MAX_FILE_LINES, PREVIEW_LINES_HEAD, PREVIEW_LINES_TAIL

def test_small_file():
    """Test that small files are read normally"""
    print("=" * 60)
    print("TEST 1: Small file (should read fully)")
    print("=" * 60)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        # Write 50 lines
        for i in range(50):
            f.write(f"Line {i+1}\n")
        temp_path = f.name

    try:
        # Use the tool directly
        result = read_file.forward(temp_path)

        # Verify full content is returned
        assert "Line 1" in result
        assert "Line 50" in result
        assert "Large file detected" not in result
        assert "GUIDANCE" not in result

        print("✅ PASS: Small file read completely")
        print(f"   Content length: {len(result)} chars")
    finally:
        os.unlink(temp_path)

def test_large_text_file():
    """Test that large text files trigger fallback"""
    print("\n" + "=" * 60)
    print("TEST 2: Large text file (should use fallback)")
    print("=" * 60)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        # Write 500 lines
        for i in range(500):
            f.write(f"Line {i+1}: Some content here\n")
        temp_path = f.name

    try:
        result = read_file.forward(temp_path)

        # Verify partial content with guidance
        assert "Large file detected: 500 lines total" in result
        assert "First 50 lines" in result or "first 50" in result.lower()
        assert "Last 50 lines" in result or "last 50" in result.lower()
        assert "GUIDANCE" in result
        assert "bash grep" in result
        assert "bash head" in result
        assert "bash tail" in result
        assert "lines omitted" in result

        print("✅ PASS: Large text file triggered fallback")
        print(f"   Showing first {PREVIEW_LINES_HEAD} + last {PREVIEW_LINES_TAIL} lines")
        print(f"   Content length: {len(result)} chars (vs ~25KB full size)")
        print("\nSample output:")
        print(result[:500] + "...\n")
    finally:
        os.unlink(temp_path)

def test_large_json_file():
    """Test that large JSON files get special handling"""
    print("\n" + "=" * 60)
    print("TEST 3: Large JSON file (should show structure)")
    print("=" * 60)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        # Create a large JSON array
        data = [{"id": i, "name": f"Item {i}", "data": "x" * 100} for i in range(200)]
        json.dump(data, f, indent=2)
        temp_path = f.name

    try:
        result = read_file.forward(temp_path)

        # Verify JSON summary
        assert "Large JSON file detected" in result
        assert "JSON Array" in result or "array" in result.lower()
        assert "items" in result.lower()
        assert "GUIDANCE" in result
        assert "jq" in result

        print("✅ PASS: Large JSON file triggered JSON-specific fallback")
        print(f"   Content length: {len(result)} chars (vs full JSON size)")
        print("\nSample output:")
        print(result[:700] + "...\n")
    finally:
        os.unlink(temp_path)

def test_boundary_case():
    """Test file at exactly MAX_FILE_LINES"""
    print("\n" + "=" * 60)
    print(f"TEST 4: Boundary case ({MAX_FILE_LINES} lines exactly)")
    print("=" * 60)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        # Write exactly MAX_FILE_LINES
        for i in range(MAX_FILE_LINES):
            f.write(f"Line {i+1}\n")
        temp_path = f.name

    try:
        result = read_file.forward(temp_path)

        # At exactly MAX_FILE_LINES, should still read fully
        assert "Line 1" in result
        assert f"Line {MAX_FILE_LINES}" in result
        assert "Large file detected" not in result

        print(f"✅ PASS: File with exactly {MAX_FILE_LINES} lines read completely")
    finally:
        os.unlink(temp_path)

def test_binary_file():
    """Test that binary files are rejected with guidance"""
    print("\n" + "=" * 60)
    print("TEST 5: Binary file (should reject with guidance)")
    print("=" * 60)

    with tempfile.NamedTemporaryFile(mode='wb', suffix='.bin', delete=False) as f:
        # Write binary data (null bytes and random binary)
        f.write(b'\x00\x01\x02\x03' * 1000)
        f.write(b'\xff\xfe\xfd\xfc' * 1000)
        temp_path = f.name

    try:
        result = read_file.forward(temp_path)

        # Verify rejection with guidance
        assert "Cannot read binary file" in result or "binary" in result.lower()
        assert "bash" in result.lower()
        assert ("hexdump" in result.lower() or
                "strings" in result.lower() or
                "file" in result.lower())

        print("✅ PASS: Binary file rejected with helpful guidance")
        print(f"   Guidance provided: {len(result)} chars")
        print(f"\n   Sample output:\n{result[:300]}")
    finally:
        os.unlink(temp_path)

def test_very_long_lines():
    """Test that very long lines are truncated"""
    print("\n" + "=" * 60)
    print("TEST 6: File with very long lines (should truncate)")
    print("=" * 60)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        # Write 200 lines with some very long lines
        for i in range(200):
            if i % 20 == 0:
                # Every 20th line is very long (2000 chars)
                f.write(f"Line {i+1}: " + "x" * 2000 + "\n")
            else:
                f.write(f"Line {i+1}: normal content\n")
        temp_path = f.name

    try:
        result = read_file.forward(temp_path)

        # Verify truncation occurred
        assert "truncated" in result.lower()
        assert "chars total" in result.lower()

        # Verify we didn't get the full 2000 chars repeated many times
        assert len(result) < 20000  # Should be much smaller than if all long lines were included

        print("✅ PASS: Very long lines were truncated")
        print(f"   Output size: {len(result)} chars (kept manageable)")
    finally:
        os.unlink(temp_path)

def test_empty_file():
    """Test handling of empty files"""
    print("\n" + "=" * 60)
    print("TEST 7: Empty file")
    print("=" * 60)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        # Create empty file
        temp_path = f.name

    try:
        result = read_file.forward(temp_path)

        # Should return empty string or handle gracefully
        assert result is not None
        assert "Error" not in result or result == ""

        print("✅ PASS: Empty file handled gracefully")
        print(f"   Result: {repr(result[:100])}")
    finally:
        os.unlink(temp_path)

def test_nonexistent_file():
    """Test handling of non-existent files"""
    print("\n" + "=" * 60)
    print("TEST 8: Non-existent file")
    print("=" * 60)

    fake_path = "/tmp/this_file_definitely_does_not_exist_12345.txt"
    result = read_file.forward(fake_path)

    # Should return error message
    assert "Error" in result or "not found" in result.lower()
    assert fake_path in result

    print("✅ PASS: Non-existent file returns helpful error")
    print(f"   Error message: {result[:150]}")

def test_unicode_file():
    """Test handling of files with unicode characters"""
    print("\n" + "=" * 60)
    print("TEST 9: File with unicode content")
    print("=" * 60)

    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.txt', delete=False) as f:
        # Write unicode content
        for i in range(150):
            f.write(f"Line {i+1}: Hello 世界 🌍 café naïve résumé\n")
        temp_path = f.name

    try:
        result = read_file.forward(temp_path)

        # Verify it's handled as large file with unicode preserved
        assert "Large file detected" in result
        assert "世界" in result or "cafe" in result or "Hello" in result

        print("✅ PASS: Unicode content handled correctly in large file")
        print(f"   Unicode preserved in output")
    finally:
        os.unlink(temp_path)

if __name__ == "__main__":
    print("\n" + "🧪 Testing Large File Fallback Implementation\n")

    try:
        # Basic functionality tests
        test_small_file()
        test_large_text_file()
        test_large_json_file()
        test_boundary_case()

        # Edge case tests
        test_binary_file()
        test_very_long_lines()
        test_empty_file()
        test_nonexistent_file()
        test_unicode_file()

        print("\n" + "=" * 60)
        print("🎉 All 9 tests passed!")
        print("=" * 60)
        print(f"\nConfiguration:")
        print(f"  MAX_FILE_LINES: {MAX_FILE_LINES}")
        print(f"  PREVIEW_LINES_HEAD: {PREVIEW_LINES_HEAD}")
        print(f"  PREVIEW_LINES_TAIL: {PREVIEW_LINES_TAIL}")

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

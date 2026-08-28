from workers.llm import is_trivial_diff, truncate_diff, MAX_DIFF_CHARS


def test_is_trivial_diff_detects_comments_and_whitespace():
    comment_only = [
        {
            "filename": "auth.py",
            "content": "# update auth config\n# another comment line\n   \n",
            "changed_lines": [1, 2, 3],
        }
    ]
    assert is_trivial_diff(comment_only) is True


def test_is_trivial_diff_detects_actual_code():
    code_diff = [
        {
            "filename": "auth.py",
            "content": "# comment\ndef login(user, password):\n    return True\n",
            "changed_lines": [1, 2, 3],
        }
    ]
    assert is_trivial_diff(code_diff) is False


def test_truncate_diff_small_payload():
    parsed_files = [
        {
            "filename": "main.py",
            "content": "def main():\n    return 0\n",
            "changed_lines": [1, 2],
        }
    ]
    diff_text, was_truncated = truncate_diff(parsed_files)
    assert was_truncated is False
    assert "### main.py" in diff_text
    assert "def main():" in diff_text
    assert "[diff truncated due to size]" not in diff_text


def test_truncate_diff_large_payload_exceeding_budget():
    large_line = "x = " + ("1" * 200) + "\n"
    large_content = large_line * 50  # ~10,000 chars

    parsed_files = [
        {
            "filename": "big_file.py",
            "content": large_content,
            "changed_lines": list(range(1, 51)),
        }
    ]

    diff_text, was_truncated = truncate_diff(parsed_files)
    assert was_truncated is True
    assert "[diff truncated due to size]" in diff_text
    assert len(diff_text) <= MAX_DIFF_CHARS + 200

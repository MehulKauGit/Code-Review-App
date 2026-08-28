from workers.parser import parse_diff


SAMPLE_PYTHON_DIFF = """diff --git a/src/auth.py b/src/auth.py
--- a/src/auth.py
+++ b/src/auth.py
@@ -1,1 +1,4 @@
 import os
+import secrets
+def verify_token(token):
+    return True
"""

SAMPLE_MULTI_FILE_DIFF = """diff --git a/src/main.py b/src/main.py
--- a/src/main.py
+++ b/src/main.py
@@ -1,1 +1,3 @@
 def run():
+    print("starting")
+    return 1
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1,1 +1,2 @@
 # Title
+New docs line
diff --git a/src/deleted.py b/src/deleted.py
deleted file mode 100644
--- a/src/deleted.py
+++ /dev/null
@@ -1,2 +0,0 @@
-def old():
-    pass
"""


def test_parse_diff_single_python_file():
    parsed = parse_diff(SAMPLE_PYTHON_DIFF)
    assert len(parsed) == 1
    assert parsed[0]["filename"] == "src/auth.py"
    assert "verify_token" in parsed[0]["content"]
    assert len(parsed[0]["changed_lines"]) == 3
    assert 2 in parsed[0]["changed_lines"]
    assert 3 in parsed[0]["changed_lines"]


def test_parse_diff_filters_non_python_and_deleted_files():
    parsed = parse_diff(SAMPLE_MULTI_FILE_DIFF)
    assert len(parsed) == 1
    assert parsed[0]["filename"] == "src/main.py"
    assert "starting" in parsed[0]["content"]


def test_parse_diff_empty_and_deletions_only():
    empty_diff = ""
    assert parse_diff(empty_diff) == []

    deletions_only = """diff --git a/src/test.py b/src/test.py
--- a/src/test.py
+++ b/src/test.py
@@ -1,3 +1,1 @@
-line1
-line2
 unchanged
"""
    assert parse_diff(deletions_only) == []


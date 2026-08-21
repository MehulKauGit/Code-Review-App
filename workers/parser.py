# workers/parser.py
from unidiff import PatchSet

def parse_diff(raw_diff: str) -> list[dict]:
    patch = PatchSet(raw_diff)
    result = []

    for patched_file in patch:
        # skip deleted files — nothing to analyse
        if patched_file.is_removed_file:
            continue

        # skipping non-python files for now
        if not patched_file.path.endswith(".py"):
            continue

        changed_lines = []
        added_content = []

        for hunk in patched_file:
            for line in hunk:
                if line.line_type == "+":
                    changed_lines.append(line.target_line_no)
                    added_content.append(line.value)

        # skip if no lines were actually added
        if not changed_lines:
            continue

        result.append({
            "filename": patched_file.path,
            "content": "".join(added_content),
            "changed_lines": changed_lines,
        })

    return result
from __future__ import annotations

import re
from dataclasses import dataclass

# Matches fenced code blocks: ```lang\n...\n```
_CODE_BLOCK_RE = re.compile(
    r"```(\w+)?\s*\n(.*?)```",
    re.DOTALL,
)

# Path comment patterns: # path or // path
_PATH_COMMENT_RE = re.compile(r"^(?:#|//)\s*(.+\.\w+)\s*$")


@dataclass
class CodeFile:
    path: str
    content: str
    language: str


def parse_code_blocks(markdown: str) -> list[CodeFile]:
    """Extract file paths and code from Markdown fenced code blocks.

    Each code block's first line is checked for a path comment like:
        # src/services/my_service.py
        // src/components/MyComponent.tsx

    If found, the path is extracted and the comment line is removed
    from the content.
    """
    files: list[CodeFile] = []

    for match in _CODE_BLOCK_RE.finditer(markdown):
        language = match.group(1) or ""
        raw_content = match.group(2)

        lines = raw_content.split("\n")
        if not lines:
            continue

        # Try to extract path from first line
        first_line = lines[0].strip()
        path_match = _PATH_COMMENT_RE.match(first_line)
        if path_match:
            path = path_match.group(1).strip()
            # Remove the path comment line from content
            content = "\n".join(lines[1:]).strip()
            files.append(CodeFile(path=path, content=content, language=language))

    return files

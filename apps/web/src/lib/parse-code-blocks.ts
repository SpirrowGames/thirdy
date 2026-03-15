export interface CodeFile {
  path: string;
  content: string;
  language: string;
}

const CODE_BLOCK_RE = /```(\w+)?\s*\n([\s\S]*?)```/g;
const PATH_COMMENT_RE = /^(?:#|\/\/)\s*(.+\.\w+)\s*$/;

export function parseCodeBlocks(markdown: string): CodeFile[] {
  const files: CodeFile[] = [];

  for (const match of markdown.matchAll(CODE_BLOCK_RE)) {
    const language = match[1] ?? "";
    const rawContent = match[2];

    const lines = rawContent.split("\n");
    if (lines.length === 0) continue;

    const firstLine = lines[0].trim();
    const pathMatch = PATH_COMMENT_RE.exec(firstLine);
    if (pathMatch) {
      const path = pathMatch[1].trim();
      const content = lines.slice(1).join("\n").trim();
      files.push({ path, content, language });
    }
  }

  return files;
}

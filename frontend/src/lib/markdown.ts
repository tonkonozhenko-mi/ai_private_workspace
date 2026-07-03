// Hand-rolled, dependency-free markdown for rendering LLM answers.
//
// Why not react-markdown / remark? This is a local-first, privacy-focused app, and
// this text comes from a local model (or indexed files). Pulling remark/micromark
// into the render path of untrusted text means dozens of transitive packages and a
// larger supply-chain surface. A small hand-rolled parser that produces plain data
// (block descriptors + inline tokens) keeps that surface minimal — the rendering
// layer maps it to auto-escaped React elements, so there is no HTML injection path.
//
// The trade for owning the parser is *correctness*, which is covered by a snapshot +
// fuzz test corpus (see markdown.test.ts): the supported subset, adversarial inputs
// (unclosed code fence, ragged tables, nesting), and a fuzz check that no input can
// throw. A garbled render is acceptable; a thrown exception that blanks the chat is
// not.

export interface MarkdownBlock {
  id: string;
  type: "paragraph" | "bulletList" | "orderedList" | "heading" | "table" | "code";
  lines: string[];
  language?: string;
  level?: number;
  rows?: string[][];
  align?: ("left" | "center" | "right" | null)[];
}

export type InlineToken =
  | { kind: "text"; text: string }
  | { kind: "code"; text: string }
  | { kind: "link"; text: string; href: string | null }
  | { kind: "bold"; text: string }
  | { kind: "italic"; text: string };

export function escapeHtml(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// Only allow safe URL schemes for rendered links. React does NOT block a
// `javascript:`/`data:` href, so a link in an LLM answer (or an indexed file)
// could otherwise execute — reject anything that isn't http(s)/mailto/relative.
export function safeLinkHref(url: string): string | null {
  const trimmed = url.trim();
  if (/^(https?:|mailto:)/i.test(trimmed)) return trimmed;
  if (/^[./#?]/.test(trimmed)) return trimmed; // relative or in-page
  if (/^[a-z][a-z0-9+.-]*:/i.test(trimmed)) return null; // some other scheme → drop
  return trimmed;
}

// Split inline text into typed tokens (inline code, [links](url), **bold**, *italic*,
// in that precedence order). Pure so the classification can be unit-tested without
// React; the renderer maps each token to an auto-escaped element.
export function tokenizeInline(text: string): InlineToken[] {
  const parts = text.split(/(`[^`]+`|\[[^\]]+\]\([^)]+\)|\*\*[^*]+\*\*|\*[^*]+\*)/g);
  const tokens: InlineToken[] = [];
  for (const part of parts) {
    if (part === "") continue;
    if (part.startsWith("`") && part.endsWith("`") && part.length > 1) {
      tokens.push({ kind: "code", text: part.slice(1, -1) });
      continue;
    }
    const link = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (link) {
      tokens.push({ kind: "link", text: link[1], href: safeLinkHref(link[2]) });
      continue;
    }
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      tokens.push({ kind: "bold", text: part.slice(2, -2) });
      continue;
    }
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
      tokens.push({ kind: "italic", text: part.slice(1, -1) });
      continue;
    }
    tokens.push({ kind: "text", text: part });
  }
  return tokens;
}

export function parseMarkdownBlocks(content: string): MarkdownBlock[] {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const blocks: MarkdownBlock[] = [];
  let paragraph: string[] = [];
  let bullets: string[] = [];
  let ordered: string[] = [];
  let tableLines: string[] = [];
  let codeLines: string[] = [];
  let codeLanguage: string | undefined;
  let inCodeBlock = false;

  function nextId(type: MarkdownBlock["type"]) {
    return `${type}-${blocks.length}`;
  }

  function flushParagraph() {
    if (paragraph.length === 0) return;
    blocks.push({ id: nextId("paragraph"), type: "paragraph", lines: paragraph });
    paragraph = [];
  }

  function flushBullets() {
    if (bullets.length === 0) return;
    blocks.push({ id: nextId("bulletList"), type: "bulletList", lines: bullets });
    bullets = [];
  }

  function flushOrdered() {
    if (ordered.length === 0) return;
    blocks.push({ id: nextId("orderedList"), type: "orderedList", lines: ordered });
    ordered = [];
  }

  function splitRow(row: string): string[] {
    return row
      .trim()
      .replace(/^\||\|$/g, "")
      .split("|")
      .map((cell) => cell.trim());
  }

  function flushTable() {
    if (tableLines.length === 0) return;
    const isSeparator =
      tableLines.length >= 2 &&
      splitRow(tableLines[1]).every((cell) => /^:?-{1,}:?$/.test(cell));
    if (isSeparator) {
      const rows = [tableLines[0], ...tableLines.slice(2)].map(splitRow);
      const align = splitRow(tableLines[1]).map((cell) => {
        const left = cell.startsWith(":");
        const right = cell.endsWith(":");
        if (left && right) return "center" as const;
        if (right) return "right" as const;
        if (left) return "left" as const;
        return null;
      });
      blocks.push({ id: nextId("table"), type: "table", lines: [], rows, align });
    } else {
      // Not a real table — fall back to plain paragraph text.
      blocks.push({ id: nextId("paragraph"), type: "paragraph", lines: [...tableLines] });
    }
    tableLines = [];
  }

  function flushCode() {
    blocks.push({
      id: nextId("code"),
      type: "code",
      lines: codeLines,
      language: codeLanguage,
    });
    codeLines = [];
    codeLanguage = undefined;
  }

  for (const rawLine of lines) {
    const line = rawLine.replace(/\s+$/g, "");
    const trimmed = line.trim();

    if (trimmed.startsWith("```")) {
      if (inCodeBlock) {
        flushCode();
        inCodeBlock = false;
      } else {
        flushParagraph();
        flushBullets();
        flushOrdered();
        flushTable();
        inCodeBlock = true;
        codeLanguage = trimmed.slice(3).trim() || undefined;
        codeLines = [];
      }
      continue;
    }

    if (inCodeBlock) {
      codeLines.push(line);
      continue;
    }

    if (trimmed.length === 0) {
      flushParagraph();
      flushBullets();
      flushOrdered();
      flushTable();
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,6})\s+(.*)$/);
    if (headingMatch) {
      flushParagraph();
      flushBullets();
      flushOrdered();
      flushTable();
      blocks.push({
        id: nextId("heading"),
        type: "heading",
        lines: [headingMatch[2]],
        level: headingMatch[1].length,
      });
      continue;
    }

    const orderedMatch = trimmed.match(/^\d+[.)]\s+(.*)$/);
    if (orderedMatch) {
      flushParagraph();
      flushBullets();
      flushTable();
      ordered.push(orderedMatch[1]);
      continue;
    }

    const bulletMatch = trimmed.match(/^[-*•]\s+(.*)$/);
    if (bulletMatch) {
      flushParagraph();
      flushOrdered();
      flushTable();
      bullets.push(bulletMatch[1]);
      continue;
    }

    // A GFM table row contains a pipe; flushTable() validates the buffer (needs
    // a `---` separator row) and falls back to a paragraph if it isn't one.
    if (trimmed.includes("|")) {
      flushParagraph();
      flushBullets();
      flushOrdered();
      tableLines.push(trimmed);
      continue;
    }

    flushBullets();
    flushOrdered();
    flushTable();
    paragraph.push(trimmed);
  }

  if (inCodeBlock) {
    flushCode();
  }
  flushParagraph();
  flushBullets();
  flushOrdered();
  flushTable();

  return blocks;
}

// Snapshot + adversarial + fuzz corpus for the hand-rolled markdown parser.
//
// This is the safety net that justifies owning the parser instead of pulling in
// react-markdown (see markdown.ts header). Two guarantees are tested:
//   1. The supported subset parses into the expected block/inline structure.
//   2. No input — however malformed or hostile — can make the parser throw.
// A garbled render is acceptable; an exception that blanks the chat is not.
//
// Written in the vitest `describe/it/expect` style so it drops straight into a
// vitest runner once one is configured. The logic here is also exercised now via a
// standalone transpile harness (scripts/run-markdown-tests.mjs).

import { describe, expect, it } from "vitest";

import {
  escapeHtml,
  parseMarkdownBlocks,
  safeLinkHref,
  tokenizeInline,
} from "./markdown";

describe("parseMarkdownBlocks — supported subset", () => {
  it("parses a plain paragraph", () => {
    const blocks = parseMarkdownBlocks("Hello world");
    expect(blocks).toHaveLength(1);
    expect(blocks[0].type).toBe("paragraph");
    expect(blocks[0].lines).toEqual(["Hello world"]);
  });

  it("parses headings with their level", () => {
    const blocks = parseMarkdownBlocks("# Title\n### Sub");
    expect(blocks.map((b) => [b.type, b.level, b.lines[0]])).toEqual([
      ["heading", 1, "Title"],
      ["heading", 3, "Sub"],
    ]);
  });

  it("groups consecutive bullets into one list", () => {
    const blocks = parseMarkdownBlocks("- a\n- b\n- c");
    expect(blocks).toHaveLength(1);
    expect(blocks[0].type).toBe("bulletList");
    expect(blocks[0].lines).toEqual(["a", "b", "c"]);
  });

  it("groups ordered items into one list", () => {
    const blocks = parseMarkdownBlocks("1. first\n2) second");
    expect(blocks).toHaveLength(1);
    expect(blocks[0].type).toBe("orderedList");
    expect(blocks[0].lines).toEqual(["first", "second"]);
  });

  it("parses a fenced code block with a language", () => {
    const blocks = parseMarkdownBlocks("```py\nprint(1)\n```");
    expect(blocks).toHaveLength(1);
    expect(blocks[0].type).toBe("code");
    expect(blocks[0].language).toBe("py");
    expect(blocks[0].lines).toEqual(["print(1)"]);
  });

  it("parses a GFM table with alignment", () => {
    const md = "| A | B | C |\n| :--- | :---: | ---: |\n| 1 | 2 | 3 |";
    const blocks = parseMarkdownBlocks(md);
    expect(blocks).toHaveLength(1);
    const table = blocks[0];
    expect(table.type).toBe("table");
    expect(table.rows).toEqual([
      ["A", "B", "C"],
      ["1", "2", "3"],
    ]);
    expect(table.align).toEqual(["left", "center", "right"]);
  });

  it("separates blocks split by a blank line", () => {
    const blocks = parseMarkdownBlocks("para one\n\npara two");
    expect(blocks).toHaveLength(2);
    expect(blocks.every((b) => b.type === "paragraph")).toBe(true);
  });
});

describe("parseMarkdownBlocks — adversarial", () => {
  it("flushes an UNCLOSED code fence as a code block at EOF", () => {
    const blocks = parseMarkdownBlocks("```js\nconst x = 1;\nno closing fence");
    expect(blocks).toHaveLength(1);
    expect(blocks[0].type).toBe("code");
    expect(blocks[0].lines).toEqual(["const x = 1;", "no closing fence"]);
  });

  it("treats a pipe row without a separator as a paragraph, not a table", () => {
    const blocks = parseMarkdownBlocks("| just | pipes |\n| but no separator |");
    expect(blocks[0].type).toBe("paragraph");
    expect(blocks.some((b) => b.type === "table")).toBe(false);
  });

  it("keeps a ragged table row (missing cells) without throwing", () => {
    const md = "| A | B | C |\n| --- | --- | --- |\n| 1 | 2 |";
    const blocks = parseMarkdownBlocks(md);
    expect(blocks[0].type).toBe("table");
    // The short row is preserved as-is; the renderer tolerates missing cells.
    expect(blocks[0].rows).toEqual([
      ["A", "B", "C"],
      ["1", "2"],
    ]);
  });

  it("does not throw on a code fence that is the whole input", () => {
    expect(() => parseMarkdownBlocks("```")).not.toThrow();
  });

  it("handles CRLF line endings", () => {
    const blocks = parseMarkdownBlocks("# Title\r\n\r\nbody");
    expect(blocks.map((b) => b.type)).toEqual(["heading", "paragraph"]);
  });
});

describe("tokenizeInline", () => {
  it("splits bold, italic, code and links in precedence order", () => {
    const tokens = tokenizeInline("a **b** _c_ `d` [e](https://x.com)");
    // note: underscores are NOT italic in this dialect (only *asterisks*)
    const kinds = tokens.map((t) => t.kind);
    expect(kinds).toContain("bold");
    expect(kinds).toContain("code");
    expect(kinds).toContain("link");
  });

  it("marks a javascript: link href as null (dropped to text)", () => {
    const tokens = tokenizeInline("[click](javascript:alert(1))");
    const link = tokens.find((t) => t.kind === "link");
    expect(link).toBeTruthy();
    expect((link as { href: string | null }).href).toBeNull();
  });

  it("keeps a safe https link href", () => {
    const tokens = tokenizeInline("[ok](https://example.com/path)");
    const link = tokens.find((t) => t.kind === "link") as { href: string | null };
    expect(link.href).toBe("https://example.com/path");
  });

  it("nested emphasis inside a link label stays as one link token", () => {
    const tokens = tokenizeInline("[**bold label**](https://x.com)");
    const link = tokens.find((t) => t.kind === "link") as { text: string };
    // The regex captures the whole label; inner ** isn't re-parsed (acceptable).
    expect(link.text).toBe("**bold label**");
  });
});

describe("safeLinkHref", () => {
  it("allows http, https, mailto and relative", () => {
    expect(safeLinkHref("https://a.com")).toBe("https://a.com");
    expect(safeLinkHref("mailto:x@y.com")).toBe("mailto:x@y.com");
    expect(safeLinkHref("./rel")).toBe("./rel");
    expect(safeLinkHref("#anchor")).toBe("#anchor");
  });

  it("drops dangerous schemes", () => {
    expect(safeLinkHref("javascript:alert(1)")).toBeNull();
    expect(safeLinkHref("data:text/html;base64,x")).toBeNull();
    expect(safeLinkHref("vbscript:msgbox")).toBeNull();
  });
});

describe("escapeHtml", () => {
  it("escapes the HTML-significant characters", () => {
    expect(escapeHtml("<b> & </b>")).toBe("&lt;b&gt; &amp; &lt;/b&gt;");
  });
});

describe("fuzz — no input may throw", () => {
  // A small deterministic PRNG so the fuzz run is reproducible.
  function mulberry32(seed: number) {
    return () => {
      seed |= 0;
      seed = (seed + 0x6d2b79f5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  const alphabet = "#*-`|[](){}:_\\\n\r\t 0123456789abc>";

  it("survives 2000 random strings through both parsers", () => {
    const rand = mulberry32(42);
    for (let i = 0; i < 2000; i += 1) {
      const len = Math.floor(rand() * 120);
      let s = "";
      for (let j = 0; j < len; j += 1) {
        s += alphabet[Math.floor(rand() * alphabet.length)];
      }
      expect(() => parseMarkdownBlocks(s)).not.toThrow();
      expect(() => tokenizeInline(s)).not.toThrow();
    }
  });

  it("survives pathological repeats of fence/pipe/marker characters", () => {
    const nasty = [
      "`".repeat(500),
      "|".repeat(500),
      "```".repeat(200),
      "#".repeat(300) + " x",
      "*".repeat(400),
      "[".repeat(200) + "]".repeat(200),
      "- ".repeat(500),
      "1. ".repeat(500),
    ];
    for (const s of nasty) {
      expect(() => parseMarkdownBlocks(s)).not.toThrow();
      expect(() => tokenizeInline(s)).not.toThrow();
    }
  });
});

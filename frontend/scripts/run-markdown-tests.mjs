// Standalone runner for src/lib/markdown.test.ts, so the markdown parser's
// snapshot + fuzz corpus can be executed without a full vitest install.
//
//   node scripts/run-markdown-tests.mjs
//
// It transpiles the module + its test with the local TypeScript, provides a tiny
// vitest-compatible `describe/it/expect` shim, runs the suite, and exits non-zero
// on any failure (so CI can gate on it before a vitest runner exists). When vitest
// is added, the same markdown.test.ts runs there unchanged.

import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const libDir = join(here, "..", "src", "lib");
const ts = (await import(join(here, "..", "node_modules", "typescript", "lib", "typescript.js")))
  .default;

function transpile(tsSource) {
  return ts.transpileModule(tsSource, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
  }).outputText;
}

const work = mkdtempSync(join(tmpdir(), "md-tests-"));

// 1) Transpile the module under test.
const moduleJs = transpile(readFileSync(join(libDir, "markdown.ts"), "utf8"));
writeFileSync(join(work, "markdown.js"), moduleJs);

// 2) Transpile the test, and point its imports at the shim + transpiled module.
let testJs = transpile(readFileSync(join(libDir, "markdown.test.ts"), "utf8"));
testJs = testJs
  .replace(/from ["']vitest["']/g, `from ${JSON.stringify(join(work, "vitest-shim.js"))}`)
  .replace(/from ["']\.\/markdown["']/g, `from ${JSON.stringify(join(work, "markdown.js"))}`);
writeFileSync(join(work, "markdown.test.js"), testJs);

// 3) Minimal vitest-compatible shim (only the matchers this corpus uses).
const results = { pass: 0, fail: 0, failures: [] };
const stack = [];

function deepEqual(a, b) {
  if (a === b) return true;
  if (typeof a !== typeof b || a === null || b === null || typeof a !== "object") return false;
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  const ka = Object.keys(a);
  const kb = Object.keys(b);
  if (ka.length !== kb.length) return false;
  return ka.every((k) => deepEqual(a[k], b[k]));
}

function makeExpect(received) {
  const assert = (ok, msg) => {
    if (!ok) throw new Error(msg);
  };
  const api = {
    toBe: (e) => assert(Object.is(received, e), `expected ${fmt(received)} to be ${fmt(e)}`),
    toEqual: (e) => assert(deepEqual(received, e), `expected ${fmt(received)} to equal ${fmt(e)}`),
    toHaveLength: (n) => assert(received?.length === n, `expected length ${received?.length} to be ${n}`),
    toContain: (x) => assert(received?.includes?.(x), `expected ${fmt(received)} to contain ${fmt(x)}`),
    toBeNull: () => assert(received === null, `expected ${fmt(received)} to be null`),
    toBeTruthy: () => assert(!!received, `expected ${fmt(received)} to be truthy`),
    toThrow: () => {
      let threw = false;
      try {
        received();
      } catch {
        threw = true;
      }
      assert(threw, "expected function to throw");
    },
  };
  api.not = {
    toBe: (e) => assert(!Object.is(received, e), `expected ${fmt(received)} not to be ${fmt(e)}`),
    toThrow: () => {
      try {
        received();
      } catch (err) {
        throw new Error(`expected function not to throw, but it threw: ${err}`);
      }
    },
  };
  return api;
}

function fmt(v) {
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

globalThis.describe = (name, fn) => {
  stack.push(name);
  fn();
  stack.pop();
};
globalThis.it = (name, fn) => {
  const label = [...stack, name].join(" › ");
  try {
    fn();
    results.pass += 1;
  } catch (err) {
    results.fail += 1;
    results.failures.push(`${label}\n    ${err.message}`);
  }
};
globalThis.expect = makeExpect;

// The shim module re-exports the globals so `import { describe, it, expect }` works.
writeFileSync(
  join(work, "vitest-shim.js"),
  "export const describe = globalThis.describe;\n" +
    "export const it = globalThis.it;\n" +
    "export const expect = globalThis.expect;\n",
);

await import(pathToFileURL(join(work, "markdown.test.js")).href);

if (results.failures.length) {
  console.error(`\n✗ ${results.fail} failed, ${results.pass} passed\n`);
  for (const f of results.failures) console.error("  ✗ " + f);
  process.exit(1);
}
console.log(`✓ all ${results.pass} markdown tests passed`);

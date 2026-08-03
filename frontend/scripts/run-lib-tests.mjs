// Standalone runner for every src/lib/*.test.ts, so the pure helpers can be
// tested without a full vitest install.
//
//   node scripts/run-lib-tests.mjs
//
// It copies each test and every module in src/lib into a temp dir, provides a
// tiny vitest-compatible `describe/it/expect` shim, runs the suites, and exits
// non-zero on any failure (so CI can gate on it before a vitest runner exists).
// When vitest is added, the same *.test.ts files run there unchanged.
//
// It used to name markdown.ts in three places, which meant the second pure module
// worth testing needed the harness edited rather than a file added. It now finds
// the tests instead of being told about them.
//
// TypeScript is deliberately NOT imported here. This used to reach into
// `node_modules/typescript/lib/typescript.js` for `transpileModule` — an internal
// file path, not a documented entry point. TypeScript 7 deleted it (the package
// now exports only a version stub and an explicitly "unstable" API), so the whole
// suite died the first time anyone ran a clean install. Node strips types itself
// on `import` of a .ts file, which is a stable, documented capability of the
// runtime we already require — so the files are copied across verbatim and Node
// does the rest. Nothing in src/lib may use non-erasable syntax (enum, namespace,
// parameter properties) or import a type without the `import type` keyword; both
// are things Node cannot strip, and a test would fail loudly if they appeared.

import { mkdtempSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const libDir = join(here, "..", "src", "lib");

const work = mkdtempSync(join(tmpdir(), "lib-tests-"));
const files = readdirSync(libDir).filter((name) => name.endsWith(".ts"));
const tests = files.filter((name) => name.endsWith(".test.ts"));

// 1) Copy every module in src/lib, so a test can import any of them (and so a
//    module can import its neighbour). `import type` lines are stripped by Node
//    before it resolves anything, which is why importing ../api/types costs
//    nothing here even though that path does not exist beside the copy.
for (const name of files.filter((n) => !n.endsWith(".test.ts"))) {
  writeFileSync(join(work, name), readFileSync(join(libDir, name), "utf8"));
}

// 2) Copy each test, and point its imports at the shim + the modules beside it.
for (const name of tests) {
  let testSource = readFileSync(join(libDir, name), "utf8");
  testSource = testSource
    .replace(/from ["']vitest["']/g, `from ${JSON.stringify(join(work, "vitest-shim.js"))}`)
    .replace(/from ["']\.\/([\w-]+)["']/g, (_m, mod) =>
      `from ${JSON.stringify(join(work, `${mod}.ts`))}`,
    )
    // Dynamic imports too — a test that needs a module's top-level code to run
    // more than once (module state set up at import time) can only get that from
    // import(), and it deserves the same rewrite the static ones get. The query
    // string is kept: it is what makes the second import a second instance.
    .replace(/import\(\s*`\.\/([\w-]+)(\?[^`]*)`\s*\)/g, (_m, mod, query) =>
      `import(${JSON.stringify(join(work, `${mod}.ts`))} + \`${query}\`)`,
    )
    .replace(/import\(\s*["']\.\/([\w-]+)(\?[^"']*)?["']\s*\)/g, (_m, mod, query) =>
      `import(${JSON.stringify(join(work, `${mod}.ts`) + (query ?? ""))})`,
    );
  writeFileSync(join(work, name), testSource);
}

// 3) Minimal vitest-compatible shim (only the matchers these corpora use).
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
// Registered, then run one at a time — the way a test runner does it.
//
// This shim used to call each `it` the moment it was declared and count it passed
// as soon as the call returned. For a synchronous test that is the same thing;
// for an async one it is a lie twice over — the assertions had not run yet, and a
// rejection landed on nobody. Then, once awaited but started together, five async
// tests raced each other through the same globals.
//
// So: collect, then run in order, awaiting each. Slower by nothing that matters.
const queue = [];
globalThis.it = (name, fn) => {
  queue.push({ label: [...stack, name].join(" › "), fn });
};
globalThis.expect = makeExpect;

// The shim module re-exports the globals so `import { describe, it, expect }` works.
writeFileSync(
  join(work, "vitest-shim.js"),
  "export const describe = globalThis.describe;\n" +
    "export const it = globalThis.it;\n" +
    "export const expect = globalThis.expect;\n",
);

for (const name of tests) {
  await import(pathToFileURL(join(work, name)).href);
}

for (const { label, fn } of queue) {
  try {
    await fn();
    results.pass += 1;
  } catch (err) {
    results.fail += 1;
    results.failures.push(`${label}\n    ${err?.message ?? err}`);
  }
}

if (results.failures.length) {
  console.error(`\n✗ ${results.fail} failed, ${results.pass} passed\n`);
  for (const f of results.failures) console.error("  ✗ " + f);
  process.exit(1);
}
console.log(`✓ all ${results.pass} tests passed (${tests.length} files)`);

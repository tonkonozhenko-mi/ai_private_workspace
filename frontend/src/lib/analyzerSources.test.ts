// "read from your JavaScript" on a project with no JavaScript is a small lie
// about what the app read — and this app's whole pitch is not telling those.

import { describe, expect, it } from "vitest";

import { analyzersThatFound, readFromClause } from "./analyzerSources";

describe("analyzersThatFound", () => {
  it("lists analyzers that produced a node, not analyzers that merely ran", () => {
    // The Bicep project: the JS analyzer ran and found nothing, so no node
    // carries it, so it is not in the set.
    const nodes = [
      { analyzer: "terraform" },
      { analyzer: "terraform" },
      { analyzer: "ownership" },
    ];

    expect(analyzersThatFound(nodes).sort()).toEqual(["ownership", "terraform"]);
  });

  it("is empty when nothing was found", () => {
    expect(analyzersThatFound([])).toEqual([]);
    expect(analyzersThatFound(null)).toEqual([]);
  });
});

describe("readFromClause", () => {
  it("names the real sources", () => {
    expect(readFromClause(["terraform", "python"])).toBe("Terraform files and Python code");
  });

  it("is empty when there is nothing to attribute — so the caller drops the clause", () => {
    expect(readFromClause([])).toBe("");
  });

  it("does not repeat a source that two analyzers map to", () => {
    // javascript covers both JS and TS; two analyzers would still read as one.
    expect(readFromClause(["javascript", "javascript"])).toBe("JavaScript and TypeScript code");
  });

  it("uses commas then 'and' for three or more", () => {
    expect(readFromClause(["terraform", "python", "sql"])).toBe(
      "Terraform files, Python code and SQL files",
    );
  });
});

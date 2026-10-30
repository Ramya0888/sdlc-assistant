// Checks whether Mermaid diagrams are syntactically valid (metric M6, DRR).
// Uses the same mermaid package the React front end uses to render diagrams.
//
// Usage: node scripts/check_mermaid.mjs <diagrams.json> <output.json>
// Input:  [{ "id": "...", "kind": "class_diagram", "code": "classDiagram ..." }, ...]
// Output: same list with "valid": true/false and "error" added.

import { readFileSync, writeFileSync } from "node:fs";
import { JSDOM } from "jsdom";

const [, , inputPath, outputPath] = process.argv;

if (!inputPath || !outputPath) {
  console.error("Usage: node scripts/check_mermaid.mjs <diagrams.json> <output.json>");
  process.exit(1);
}

// Mermaid expects a browser DOM; jsdom provides one in Node.
const dom = new JSDOM("<!doctype html><html><body></body></html>");
globalThis.window = dom.window;
globalThis.document = dom.window.document;

const { default: mermaid } = await import("mermaid");
mermaid.initialize({ startOnLoad: false, securityLevel: "loose" });

// Same cleaning the MermaidDiagram component in App.jsx applies before rendering.
function clean(code) {
  return String(code || "")
    .replace(/\\n/g, "\n")
    .replace(/```mermaid/gi, "")
    .replace(/```/g, "")
    .trim();
}

const diagrams = JSON.parse(readFileSync(inputPath, "utf8"));
const results = [];

for (const diagram of diagrams) {
  const code = clean(diagram.code);
  if (!code) {
    results.push({ ...diagram, valid: false, error: "empty diagram" });
    continue;
  }
  try {
    await mermaid.parse(code);
    results.push({ ...diagram, valid: true, error: null });
  } catch (error) {
    const message = String(error?.message || error).split("\n")[0];
    results.push({ ...diagram, valid: false, error: message });
  }
}

writeFileSync(outputPath, JSON.stringify(results, null, 2));

const ok = results.filter((r) => r.valid).length;
console.log(`Mermaid check: ${ok}/${results.length} diagrams valid`);
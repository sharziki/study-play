/* Validate LaTeX expressions with the same KaTeX build the app ships.
 *
 * Reads a JSON array of expressions on stdin, prints the ones that fail.
 * Exists because "the repair produced LaTeX" and "KaTeX can render it" are
 * different claims, and only the second one is what the learner sees.
 */
const fs = require("node:fs");
const path = require("node:path");

const katexPath = path.join(__dirname, "..", "web_static", "vendor", "katex", "katex.min.js");
const shim = { exports: {} };
new Function("module", "exports", "window", "document", fs.readFileSync(katexPath, "utf8"))(
  shim, shim.exports, {}, undefined
);
const katex = shim.exports;

const expressions = JSON.parse(fs.readFileSync(0, "utf8"));
const failures = [];
for (const expression of expressions) {
  try {
    katex.renderToString(expression, { throwOnError: true });
  } catch (error) {
    failures.push({ expression, error: error.message });
  }
}
process.stdout.write(JSON.stringify(failures));
process.exit(failures.length ? 1 : 0);

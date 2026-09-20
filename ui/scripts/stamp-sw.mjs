/* Stamp the service worker with a content hash of the built bundle.
 *
 * The shell is cache-first, so an unchanged VERSION means an installed PWA
 * keeps serving the previous app.js forever. Deriving the version from the
 * build output makes a stale phone impossible to ship by forgetting a manual
 * bump, which happened twice while porting this UI.
 */
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const out = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "web_static");

const hash = createHash("sha256");
for (const file of ["app.js", "index.css", "index.html"]) {
  hash.update(readFileSync(join(out, file)));
}
const version = `intellect-${hash.digest("hex").slice(0, 12)}`;

const worker = join(out, "sw.js");
const stamped = readFileSync(worker, "utf8").replace(
  /const VERSION = "[^"]*";/,
  `const VERSION = "${version}";`
);
writeFileSync(worker, stamped);
console.log(`service worker version ${version}`);

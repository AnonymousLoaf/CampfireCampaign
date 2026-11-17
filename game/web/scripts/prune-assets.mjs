// After a build: delete old asset files that the new page doesn't use and that are more than two weeks old.
// Builds keep earlier files (emptyOutDir: false) so a page opened before an update can still load the
// pieces it asks for later (the 3D dice load on demand); this keeps the folder from growing forever.
import { readdirSync, readFileSync, statSync, unlinkSync } from "node:fs";
import { join } from "node:path";

const dist = new URL("../dist/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const assets = join(dist, "assets");
const keepDays = 14;
const index = readFileSync(join(dist, "index.html"), "utf8");
const cutoff = Date.now() - keepDays * 24 * 3600 * 1000;
let removed = 0;
for (const name of readdirSync(assets)) {
  const path = join(assets, name);
  if (index.includes(name)) continue; // the current page's own files
  if (statSync(path).mtimeMs < cutoff) {
    unlinkSync(path);
    removed++;
  }
}
console.log(`prune-assets: kept recent files, removed ${removed} older than ${keepDays} days`);

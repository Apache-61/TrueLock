/**
 * Copy allowlisted markdown from repo docs/ into frontend/content/docs
 * so Vercel/Docker builds that only see the frontend tree still work.
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.join(__dirname, "..");
const repoDocs = process.env.TRUELOCK_DOCS_ROOT
  ? path.resolve(process.env.TRUELOCK_DOCS_ROOT)
  : path.join(frontendRoot, "..", "docs");
const destRoot = path.join(frontendRoot, "content", "docs");

const FILES = [
  "challenge/README.md",
  "challenge/traceability-matrix.md",
  "demo/runbook.md",
  "demo/README.md",
  "demo-script.md",
  "contracts/api.md",
  "contracts/agent-tools.md",
  "contracts/investigation.md",
  "contracts/evidence.md",
  "contracts/case.md",
  "agent/training.md",
  "deployment.md",
  "testing.md",
  "ops/recovery-runbook.md",
  "ops/hosted-tech-domain.md",
];

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function main() {
  if (!fs.existsSync(repoDocs)) {
    console.warn(`sync-docs: repo docs not found at ${repoDocs}; keeping existing content/docs if any`);
    return;
  }
  for (const rel of FILES) {
    const src = path.join(repoDocs, rel);
    const dest = path.join(destRoot, rel);
    if (!fs.existsSync(src)) {
      console.warn(`sync-docs: missing ${rel}`);
      continue;
    }
    ensureDir(path.dirname(dest));
    fs.copyFileSync(src, dest);
  }
  console.log(`sync-docs: copied ${FILES.length} files -> content/docs`);
}

main();

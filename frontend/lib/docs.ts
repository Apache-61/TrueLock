/**
 * Allowlisted judge/docs markdown → URL slugs.
 * Source files live in repo `docs/`; synced into `frontend/content/docs` at build.
 */
import fs from "fs";
import path from "path";

export type DocEntry = {
  slug: string;
  title: string;
  /** Path relative to repo docs/ */
  relPath: string;
  group: "path" | "support" | "contracts";
};

/** Judge 5-minute path first, then supporting pages. */
export const DOC_ENTRIES: DocEntry[] = [
  { slug: "challenge", title: "Judge index", relPath: "challenge/README.md", group: "path" },
  { slug: "runbook", title: "Demo runbook", relPath: "demo/runbook.md", group: "path" },
  { slug: "demo-script", title: "Demo script", relPath: "demo-script.md", group: "path" },
  { slug: "api", title: "API contract", relPath: "contracts/api.md", group: "path" },
  { slug: "training", title: "Training overview", relPath: "agent/training.md", group: "path" },
  { slug: "traceability", title: "Traceability matrix", relPath: "challenge/traceability-matrix.md", group: "support" },
  { slug: "deployment", title: "Deployment", relPath: "deployment.md", group: "support" },
  { slug: "testing", title: "Testing", relPath: "testing.md", group: "support" },
  { slug: "recovery", title: "Recovery runbook", relPath: "ops/recovery-runbook.md", group: "support" },
  { slug: "hosted", title: "Hosted .tech domain", relPath: "ops/hosted-tech-domain.md", group: "support" },
  { slug: "demo", title: "Demo README", relPath: "demo/README.md", group: "support" },
  { slug: "agent-tools", title: "Agent tools", relPath: "contracts/agent-tools.md", group: "contracts" },
  { slug: "investigation", title: "Investigation", relPath: "contracts/investigation.md", group: "contracts" },
  { slug: "evidence", title: "Evidence", relPath: "contracts/evidence.md", group: "contracts" },
  { slug: "case", title: "Case", relPath: "contracts/case.md", group: "contracts" },
];

const REL_TO_SLUG = new Map(
  DOC_ENTRIES.flatMap((entry) => {
    const variants = [
      entry.relPath,
      `docs/${entry.relPath}`,
      `../${entry.relPath}`,
      entry.relPath.replace(/\\/g, "/"),
    ];
    // basename-style links used in markdown
    const base = path.posix.basename(entry.relPath);
    return [...variants, base, `./${base}`, `../${base}`].map((key) => [key.replace(/\\/g, "/"), entry.slug] as const);
  })
);

export function docsContentRoot(): string {
  if (process.env.TRUELOCK_DOCS_ROOT) {
    return process.env.TRUELOCK_DOCS_ROOT;
  }
  const synced = path.join(process.cwd(), "content", "docs");
  if (fs.existsSync(synced)) {
    return synced;
  }
  return path.join(process.cwd(), "..", "docs");
}

export function getDocEntry(slug: string): DocEntry | undefined {
  return DOC_ENTRIES.find((entry) => entry.slug === slug);
}

export function listDocSlugs(): string[] {
  return DOC_ENTRIES.map((entry) => entry.slug);
}

export function readDocMarkdown(slug: string): string {
  const entry = getDocEntry(slug);
  if (!entry) {
    throw new Error(`Unknown docs slug: ${slug}`);
  }
  const root = docsContentRoot();
  const filePath = path.join(root, entry.relPath);
  if (!fs.existsSync(filePath)) {
    throw new Error(`Docs file missing: ${filePath}`);
  }
  return fs.readFileSync(filePath, "utf8");
}

/** Map markdown relative links to /docs/{slug} when allowlisted. */
export function rewriteDocHref(href: string | undefined): string | undefined {
  if (!href) return href;
  if (href.startsWith("http://") || href.startsWith("https://") || href.startsWith("#") || href.startsWith("mailto:")) {
    return href;
  }
  const hash = href.includes("#") ? `#${href.split("#")[1]}` : "";
  const cleaned = href.split("#")[0].replace(/^\.\//, "").replace(/\\/g, "/");

  const manual: Record<string, string> = {
    "../demo/runbook.md": "/docs/runbook",
    "demo/runbook.md": "/docs/runbook",
    "../demo-script.md": "/docs/demo-script",
    "demo-script.md": "/docs/demo-script",
    "../contracts/api.md": "/docs/api",
    "contracts/api.md": "/docs/api",
    "../agent/training.md": "/docs/training",
    "agent/training.md": "/docs/training",
    "traceability-matrix.md": "/docs/traceability",
    "challenge/traceability-matrix.md": "/docs/traceability",
    "../deployment.md": "/docs/deployment",
    "deployment.md": "/docs/deployment",
    "../testing.md": "/docs/testing",
    "testing.md": "/docs/testing",
    "../ops/recovery-runbook.md": "/docs/recovery",
    "ops/recovery-runbook.md": "/docs/recovery",
    "../ops/hosted-tech-domain.md": "/docs/hosted",
    "ops/hosted-tech-domain.md": "/docs/hosted",
    "../demo/README.md": "/docs/demo",
    "demo/README.md": "/docs/demo",
    "contracts/agent-tools.md": "/docs/agent-tools",
    "../contracts/agent-tools.md": "/docs/agent-tools",
    "contracts/investigation.md": "/docs/investigation",
    "../contracts/investigation.md": "/docs/investigation",
    "contracts/evidence.md": "/docs/evidence",
    "../contracts/evidence.md": "/docs/evidence",
    "contracts/case.md": "/docs/case",
    "../contracts/case.md": "/docs/case",
    "challenge/README.md": "/docs",
    "../challenge/README.md": "/docs",
  };

  for (const [key, value] of Object.entries(manual)) {
    if (cleaned === key || cleaned.endsWith(`/${key}`) || cleaned.endsWith(key)) {
      return value + hash;
    }
  }

  const base = path.posix.basename(cleaned);
  const slug = REL_TO_SLUG.get(cleaned) || REL_TO_SLUG.get(base);
  if (slug) {
    return (slug === "challenge" ? "/docs" : `/docs/${slug}`) + hash;
  }
  return href;
}

/** Public site hostname for docs pack / meta (Phase 4 placeholder until DNS). */
export function publicSiteOrigin(): string {
  return process.env.NEXT_PUBLIC_SITE_URL || "https://truelockfa.tech";
}

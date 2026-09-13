import React from "react";
import Link from "next/link";
import { DOC_ENTRIES, publicSiteOrigin } from "../../lib/docs";

const GROUPS: Array<{ id: "path" | "support" | "contracts"; label: string }> = [
  { id: "path", label: "5-minute path" },
  { id: "support", label: "Supporting" },
  { id: "contracts", label: "Contracts" },
];

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  const origin = publicSiteOrigin();
  return (
    <div className="docs-shell">
      <aside className="docs-sidebar">
        <div className="docs-brand">
          <Link href="/docs">TrueLock Docs</Link>
          <p className="docs-muted">Judge & operator guide</p>
        </div>
        <nav className="docs-nav">
          {GROUPS.map((group) => (
            <div key={group.id} className="docs-nav-group">
              <div className="docs-nav-label">{group.label}</div>
              {DOC_ENTRIES.filter((entry) => entry.group === group.id).map((entry) => (
                <Link
                  key={entry.slug}
                  href={entry.slug === "challenge" ? "/docs" : `/docs/${entry.slug}`}
                  className="docs-nav-link"
                >
                  {entry.title}
                </Link>
              ))}
            </div>
          ))}
        </nav>
        <div className="docs-ports">
          <strong>Hosted</strong>
          <div>{origin}</div>
          <div className="docs-muted">API: api host via NEXT_PUBLIC_API_URL</div>
          <div className="docs-muted">Local Postgres: :5433 (dev only)</div>
        </div>
        <Link href="/" className="docs-back">
          Back to auditor
        </Link>
      </aside>
      <main className="docs-main">{children}</main>
    </div>
  );
}

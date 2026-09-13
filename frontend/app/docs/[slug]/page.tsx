import React from "react";
import { notFound } from "next/navigation";
import { MarkdownDoc } from "../../../components/MarkdownDoc";
import { getDocEntry, listDocSlugs, readDocMarkdown } from "../../../lib/docs";

export function generateStaticParams() {
  return listDocSlugs()
    .filter((slug) => slug !== "challenge")
    .map((slug) => ({ slug }));
}

export function generateMetadata({ params }: { params: { slug: string } }) {
  const entry = getDocEntry(params.slug);
  return {
    title: entry ? `TrueLock Docs | ${entry.title}` : "TrueLock Docs",
  };
}

export default function DocsSlugPage({ params }: { params: { slug: string } }) {
  if (params.slug === "challenge") {
    notFound();
  }
  const entry = getDocEntry(params.slug);
  if (!entry) {
    notFound();
  }
  const source = readDocMarkdown(params.slug);
  return <MarkdownDoc source={source} />;
}

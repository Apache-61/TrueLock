import React from "react";
import { MarkdownDoc } from "../../components/MarkdownDoc";
import { readDocMarkdown } from "../../lib/docs";

export const metadata = {
  title: "TrueLock Docs | Judge index",
  description: "Five-minute path for TrueLock hackathon judges and reviewers.",
};

export default function DocsHomePage() {
  const source = readDocMarkdown("challenge");
  return <MarkdownDoc source={source} />;
}

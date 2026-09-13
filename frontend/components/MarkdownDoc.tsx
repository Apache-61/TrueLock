import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { rewriteDocHref } from "../lib/docs";

export function MarkdownDoc({ source }: { source: string }) {
  return (
    <article className="docs-markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children, ...props }) => (
            <a href={rewriteDocHref(href) ?? href} {...props}>
              {children}
            </a>
          ),
        }}
      >
        {source}
      </ReactMarkdown>
    </article>
  );
}

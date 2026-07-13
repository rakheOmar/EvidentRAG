"use client";

import "streamdown/styles.css";
import "katex/dist/katex.min.css";

import { TextMessagePartProvider } from "@assistant-ui/react";
import {
  type CodeHeaderProps,
  escapeCurrencyDollars,
  normalizeMathDelimiters,
  StreamdownTextPrimitive,
  type StreamdownTextComponents,
} from "@assistant-ui/react-streamdown";
import { code } from "@streamdown/code";
import { createMathPlugin } from "@streamdown/math";
import { mermaid } from "@streamdown/mermaid";
import { DownloadIcon, FilesIcon } from "lucide-react";
import { type FC, memo } from "react";
import {
  CodeBlockCopyButton,
  CodeBlockDownloadButton,
} from "streamdown";

import { SyntaxHighlighter } from "@/components/assistant-ui/shiki-highlighter";
import { cn } from "@/lib/utils";

type MarkdownTextProps = {
  className?: string;
  content?: string;
};

const plugins = {
  code,
  math: createMathPlugin({ singleDollarTextMath: true }),
  mermaid,
};

const preprocessMarkdown = (text: string) =>
  escapeCurrencyDollars(normalizeMathDelimiters(text));

const CodeHeader: FC<CodeHeaderProps> = ({ code: codeText, language }) => (
  <div
    className="flex h-9 items-center justify-between rounded-t-xl border border-border/50 bg-muted/30 px-2.5"
    style={{ marginBlockEnd: 0 }}
  >
    <span className="px-1 font-mono text-[11px] text-muted-foreground">
      {language || "text"}
    </span>
    <div className="flex items-center gap-0.5">
      <CodeBlockDownloadButton
        aria-label="Download code"
        className="flex size-8 items-center justify-center rounded-md text-muted-foreground transition-[background-color,color,transform] duration-150 hover:bg-muted hover:text-foreground active:scale-[0.96]"
        code={codeText}
        language={language}
      >
        <DownloadIcon className="size-3.5" />
      </CodeBlockDownloadButton>
      <CodeBlockCopyButton
        aria-label="Copy code"
        className="flex size-8 items-center justify-center rounded-md text-muted-foreground transition-[background-color,color,transform] duration-150 hover:bg-muted hover:text-foreground active:scale-[0.96]"
        code={codeText}
      >
        <FilesIcon className="size-3.5" />
      </CodeBlockCopyButton>
    </div>
  </div>
);

const components: StreamdownTextComponents = {
  CodeHeader,
  SyntaxHighlighter,
  h1: ({ className, ...props }) => (
    <h1
      className={cn(
        "aui-md-h1 mt-5 mb-2 scroll-m-20 font-semibold text-xl first:mt-0 last:mb-0",
        className,
      )}
      {...props}
    />
  ),
  h2: ({ className, ...props }) => (
    <h2
      className={cn(
        "aui-md-h2 mt-5 mb-2 scroll-m-20 font-semibold text-lg first:mt-0 last:mb-0",
        className,
      )}
      {...props}
    />
  ),
  h3: ({ className, ...props }) => (
    <h3
      className={cn(
        "aui-md-h3 mt-4 mb-1.5 scroll-m-20 font-semibold text-base first:mt-0 last:mb-0",
        className,
      )}
      {...props}
    />
  ),
  p: ({ className, ...props }) => (
    <p
      className={cn(
        "aui-md-p my-3 leading-relaxed first:mt-0 last:mb-0",
        className,
      )}
      {...props}
    />
  ),
  a: ({ className, ...props }) => (
    <a
      className={cn(
        "aui-md-a text-primary underline underline-offset-2 hover:text-primary/80",
        className,
      )}
      {...props}
    />
  ),
  blockquote: ({ className, ...props }) => (
    <blockquote
      className={cn(
        "aui-md-blockquote my-3 border-muted-foreground/30 border-s-2 ps-4 text-muted-foreground",
        className,
      )}
      {...props}
    />
  ),
  ul: ({ className, ...props }) => (
    <ul
      className={cn(
        "aui-md-ul my-3 ms-5 list-disc marker:text-muted-foreground [&>li]:mt-1",
        className,
      )}
      {...props}
    />
  ),
  ol: ({ className, ...props }) => (
    <ol
      className={cn(
        "aui-md-ol my-3 ms-5 list-decimal marker:text-muted-foreground [&>li]:mt-1",
        className,
      )}
      {...props}
    />
  ),
  li: ({ className, ...props }) => (
    <li className={cn("aui-md-li leading-relaxed", className)} {...props} />
  ),
  strong: ({ className, ...props }) => (
    <strong
      className={cn("aui-md-strong font-semibold", className)}
      {...props}
    />
  ),
  table: ({ className, ...props }) => (
    <table
      className={cn(
        "aui-md-table my-3 w-full border-separate border-spacing-0",
        className,
      )}
      {...props}
    />
  ),
  th: ({ className, ...props }) => (
    <th
      className={cn(
        "aui-md-th bg-muted px-3 py-1.5 text-start font-medium first:rounded-ss-lg last:rounded-se-lg",
        className,
      )}
      {...props}
    />
  ),
  td: ({ className, ...props }) => (
    <td
      className={cn(
        "aui-md-td border-muted-foreground/20 border-s border-b px-3 py-1.5 text-start last:border-e",
        className,
      )}
      {...props}
    />
  ),
  tr: ({ className, ...props }) => (
    <tr
      className={cn(
        "aui-md-tr m-0 border-b p-0 first:border-t [&:last-child>td:first-child]:rounded-es-lg [&:last-child>td:last-child]:rounded-ee-lg",
        className,
      )}
      {...props}
    />
  ),
};

const sharedStreamdownProps = {
  components,
  controls: { code: false, table: true, mermaid: true },
  plugins,
};

const MarkdownTextImpl: FC<MarkdownTextProps> = ({ className, content }) =>
  content === undefined ? (
    <StreamdownTextPrimitive
      {...sharedStreamdownProps}
      containerClassName={cn("aui-md", className)}
      defer
      preprocess={preprocessMarkdown}
    />
  ) : (
    <TextMessagePartProvider isRunning={false} text={content}>
      <StreamdownTextPrimitive
        {...sharedStreamdownProps}
        containerClassName={cn("aui-md", className)}
        mode="static"
        preprocess={preprocessMarkdown}
      />
    </TextMessagePartProvider>
  );

export const MarkdownText = memo(MarkdownTextImpl);

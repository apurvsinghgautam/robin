"use client";

import { useMemo } from "react";

interface MarkdownProps {
  content: string;
  className?: string;
}

/**
 * Enhanced Markdown renderer for dark theme with clean typography
 * Supports: headers, bold, italic, code, lists, tables, links, blockquotes
 */
export function Markdown({ content, className = "" }: MarkdownProps) {
  const renderedContent = useMemo(() => {
    if (!content) return null;

    let html = content;

    // Escape HTML to prevent XSS
    html = html
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // Code blocks (``` ... ```) - must be processed first to protect content
    const codeBlocks: string[] = [];
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
      const placeholder = `__CODE_BLOCK_${codeBlocks.length}__`;
      codeBlocks.push(`<pre class="md-code-block"><code class="md-code">${code.trim()}</code></pre>`);
      return placeholder;
    });

    // Inline code (`...`) - protect from other processing
    const inlineCodes: string[] = [];
    html = html.replace(/`([^`]+)`/g, (_, code) => {
      const placeholder = `__INLINE_CODE_${inlineCodes.length}__`;
      inlineCodes.push(`<code class="md-inline-code">${code}</code>`);
      return placeholder;
    });

    // Headers - process from h4 to h1 to avoid conflicts
    html = html.replace(/^#### (.+)$/gm, '<h4 class="md-h4">$1</h4>');
    html = html.replace(/^### (.+)$/gm, '<h3 class="md-h3">$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2 class="md-h2">$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1 class="md-h1">$1</h1>');

    // Bold and Italic - process combined first, then bold, then italic
    // Use simpler patterns without lookbehind (for browser compatibility)
    html = html.replace(/\*\*\*([^*]+)\*\*\*/g, '<strong class="md-bold"><em>$1</em></strong>');
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong class="md-bold">$1</strong>');
    html = html.replace(/\*([^*]+)\*/g, '<em class="md-italic">$1</em>');
    html = html.replace(/__([^_]+)__/g, '<strong class="md-bold">$1</strong>');
    html = html.replace(/_([^_]+)_/g, '<em class="md-italic">$1</em>');

    // Links
    html = html.replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer" class="md-link">$1</a>'
    );

    // Horizontal rules
    html = html.replace(/^---$/gm, '<hr class="md-hr" />');

    // Blockquotes - process before paragraphs
    html = html.replace(
      /^&gt; (.+)$/gm,
      '<blockquote class="md-blockquote">$1</blockquote>'
    );

    // Tables - process before lists
    const tableLines = html.split('\n');
    let inTable = false;
    let tableHtml = '';
    const processedLines: string[] = [];

    for (let i = 0; i < tableLines.length; i++) {
      const line = tableLines[i];
      const isTableRow = /^\|(.+)\|$/.test(line.trim());
      const isSeparator = /^\|[\s\-:|]+\|$/.test(line.trim());

      if (isTableRow && !isSeparator) {
        if (!inTable) {
          inTable = true;
          tableHtml = '<div class="md-table-wrapper"><table class="md-table"><tbody>';
        }
        const cells = line.trim().slice(1, -1).split('|').map(c => c.trim());
        tableHtml += '<tr class="md-tr">' + cells.map(c => `<td class="md-td">${c}</td>`).join('') + '</tr>';
      } else if (isSeparator) {
        // Skip separator rows
        continue;
      } else {
        if (inTable) {
          tableHtml += '</tbody></table></div>';
          processedLines.push(tableHtml);
          tableHtml = '';
          inTable = false;
        }
        processedLines.push(line);
      }
    }
    if (inTable) {
      tableHtml += '</tbody></table></div>';
      processedLines.push(tableHtml);
    }
    html = processedLines.join('\n');

    // Unordered lists
    html = html.replace(/^[\t ]*[-*+] (.+)$/gm, '<li class="md-ul-item">$1</li>');

    // Ordered lists
    html = html.replace(/^[\t ]*(\d+)\. (.+)$/gm, '<li class="md-ol-item" value="$1">$2</li>');

    // Wrap consecutive list items
    html = html.replace(
      /(<li class="md-ul-item">[^]*?<\/li>\n?)+/g,
      match => `<ul class="md-ul">${match}</ul>`
    );
    html = html.replace(
      /(<li class="md-ol-item"[^]*?<\/li>\n?)+/g,
      match => `<ol class="md-ol">${match}</ol>`
    );

    // Process paragraphs - split by double newlines
    const blocks = html.split(/\n\n+/);
    html = blocks.map(block => {
      const trimmed = block.trim();
      if (!trimmed) return '';
      // Don't wrap if already an HTML element
      if (/^<[a-zA-Z]/.test(trimmed)) {
        return trimmed;
      }
      // Handle single newlines within a paragraph as line breaks
      const processed = trimmed.replace(/\n/g, '<br />');
      return `<p class="md-p">${processed}</p>`;
    }).filter(Boolean).join('\n');

    // Clean up newlines between block elements
    html = html.replace(/>\s*\n\s*</g, '><');

    // Restore code blocks
    codeBlocks.forEach((code, i) => {
      html = html.replace(`__CODE_BLOCK_${i}__`, code);
    });

    // Restore inline code
    inlineCodes.forEach((code, i) => {
      html = html.replace(`__INLINE_CODE_${i}__`, code);
    });

    return html;
  }, [content]);

  if (!renderedContent) return null;

  return (
    <div
      className={`markdown-content leading-relaxed ${className}`}
      dangerouslySetInnerHTML={{ __html: renderedContent }}
    />
  );
}

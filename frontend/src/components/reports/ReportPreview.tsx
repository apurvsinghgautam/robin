'use client';

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Report, IOCEntry } from '@/types';
import IOCTable from './IOCTable';
import { formatDateTime } from '@/lib/utils';

interface ReportPreviewProps {
  report: Report;
}

// Mock IOC data for development
const MOCK_IOCS: IOCEntry[] = [
  { type: 'ip', value: '192.168.1.100', context: 'C2 server', confidence: 'high' },
  { type: 'domain', value: 'malware-c2.example.com', context: 'Primary C2 domain', confidence: 'high' },
  { type: 'hash', value: 'abc123def456789012345678901234567890abcdef', context: 'X-Agent payload', confidence: 'high' },
  { type: 'email', value: 'attacker@evil.com', context: 'Phishing sender', confidence: 'medium' },
  { type: 'ip', value: '10.0.0.50', context: 'Backup C2', confidence: 'medium' },
  { type: 'domain', value: 'backup-c2.example.net', context: 'Backup domain', confidence: 'low' },
];

export default function ReportPreview({ report }: ReportPreviewProps) {
  const sortedSections = [...report.sections].sort((a, b) => a.order - b.order);

  return (
    <div className="prose prose-invert prose-slate max-w-none">
      {/* Report Header */}
      <div className="mb-8 pb-6 border-b border-slate-700">
        <h1 className="text-3xl font-bold text-slate-100 mb-2">{report.title}</h1>
        <div className="flex items-center gap-4 text-sm text-slate-400">
          <span>Created: {formatDateTime(report.created_at)}</span>
          <span>Last updated: {formatDateTime(report.updated_at)}</span>
        </div>
      </div>

      {/* Table of Contents */}
      {sortedSections.length > 1 && (
        <div className="mb-8 p-4 bg-slate-800/50 rounded-lg border border-slate-700">
          <h2 className="text-lg font-semibold text-slate-200 mb-3 mt-0">Table of Contents</h2>
          <nav>
            <ol className="list-decimal list-inside space-y-1 m-0">
              {sortedSections.map((section, index) => (
                <li key={section.id}>
                  <a
                    href={`#section-${section.id}`}
                    className="text-blue-400 hover:text-blue-300 no-underline"
                  >
                    {section.title}
                  </a>
                </li>
              ))}
            </ol>
          </nav>
        </div>
      )}

      {/* Sections */}
      {sortedSections.map((section) => (
        <section
          key={section.id}
          id={`section-${section.id}`}
          className="mb-8 pb-6 border-b border-slate-700/50 last:border-0"
        >
          <h2 className="text-2xl font-semibold text-slate-100 mb-4">{section.title}</h2>

          {section.type === 'entities' ? (
            <IOCTable iocs={MOCK_IOCS} editable={false} />
          ) : (
            <div className="text-slate-300">
              {section.content ? (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    h1: ({ node, ...props }) => (
                      <h3 className="text-xl font-semibold text-slate-200 mt-6 mb-3" {...props} />
                    ),
                    h2: ({ node, ...props }) => (
                      <h4 className="text-lg font-semibold text-slate-200 mt-5 mb-2" {...props} />
                    ),
                    h3: ({ node, ...props }) => (
                      <h5 className="text-base font-semibold text-slate-200 mt-4 mb-2" {...props} />
                    ),
                    p: ({ node, ...props }) => (
                      <p className="text-slate-300 mb-4 leading-relaxed" {...props} />
                    ),
                    ul: ({ node, ...props }) => (
                      <ul className="list-disc list-inside space-y-1 mb-4 text-slate-300" {...props} />
                    ),
                    ol: ({ node, ...props }) => (
                      <ol className="list-decimal list-inside space-y-1 mb-4 text-slate-300" {...props} />
                    ),
                    li: ({ node, ...props }) => (
                      <li className="text-slate-300" {...props} />
                    ),
                    strong: ({ node, ...props }) => (
                      <strong className="font-semibold text-slate-200" {...props} />
                    ),
                    code: ({ node, className, children, ...props }) => {
                      const isInline = !className;
                      if (isInline) {
                        return (
                          <code
                            className="bg-slate-700 text-blue-300 px-1.5 py-0.5 rounded text-sm"
                            {...props}
                          >
                            {children}
                          </code>
                        );
                      }
                      return (
                        <code
                          className={`block bg-slate-800 p-4 rounded-lg overflow-x-auto text-sm ${className}`}
                          {...props}
                        >
                          {children}
                        </code>
                      );
                    },
                    pre: ({ node, ...props }) => (
                      <pre className="bg-slate-800 p-4 rounded-lg overflow-x-auto mb-4" {...props} />
                    ),
                    blockquote: ({ node, ...props }) => (
                      <blockquote
                        className="border-l-4 border-blue-500 pl-4 italic text-slate-400 my-4"
                        {...props}
                      />
                    ),
                    table: ({ node, ...props }) => (
                      <div className="overflow-x-auto mb-4">
                        <table className="min-w-full divide-y divide-slate-700" {...props} />
                      </div>
                    ),
                    th: ({ node, ...props }) => (
                      <th
                        className="px-4 py-2 text-left text-sm font-semibold text-slate-200 bg-slate-800"
                        {...props}
                      />
                    ),
                    td: ({ node, ...props }) => (
                      <td
                        className="px-4 py-2 text-sm text-slate-300 border-t border-slate-700"
                        {...props}
                      />
                    ),
                    a: ({ node, ...props }) => (
                      <a
                        className="text-blue-400 hover:text-blue-300 underline"
                        target="_blank"
                        rel="noopener noreferrer"
                        {...props}
                      />
                    ),
                  }}
                >
                  {section.content}
                </ReactMarkdown>
              ) : (
                <p className="text-slate-500 italic">No content</p>
              )}
            </div>
          )}
        </section>
      ))}

      {sortedSections.length === 0 && (
        <div className="text-center py-12 text-slate-500">
          <p>No sections in this report</p>
        </div>
      )}
    </div>
  );
}

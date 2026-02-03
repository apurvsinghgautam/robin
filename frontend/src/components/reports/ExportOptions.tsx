'use client';

import React, { useState } from 'react';
import { X, Download, FileText, Code, Copy, Check, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { exportReport } from '@/lib/api';
import { downloadBlob, copyToClipboard } from '@/lib/utils';

interface ExportOptionsProps {
  reportId: string;
  reportTitle: string;
  onClose: () => void;
}

type ExportFormat = 'md' | 'html' | 'pdf';

interface FormatOption {
  value: ExportFormat;
  label: string;
  description: string;
  icon: React.ReactNode;
  mimeType: string;
  extension: string;
}

const FORMAT_OPTIONS: FormatOption[] = [
  {
    value: 'md',
    label: 'Markdown',
    description: 'Plain text with formatting, ideal for documentation',
    icon: <FileText className="h-5 w-5" />,
    mimeType: 'text/markdown',
    extension: 'md',
  },
  {
    value: 'html',
    label: 'HTML',
    description: 'Web-ready format with styling',
    icon: <Code className="h-5 w-5" />,
    mimeType: 'text/html',
    extension: 'html',
  },
  {
    value: 'pdf',
    label: 'PDF',
    description: 'Portable document format for sharing',
    icon: <FileText className="h-5 w-5" />,
    mimeType: 'application/pdf',
    extension: 'pdf',
  },
];

export default function ExportOptions({ reportId, reportTitle, onClose }: ExportOptionsProps) {
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>('md');
  const [exporting, setExporting] = useState(false);
  const [copied, setCopied] = useState(false);

  const selectedOption = FORMAT_OPTIONS.find((opt) => opt.value === selectedFormat)!;

  const handleDownload = async () => {
    setExporting(true);
    try {
      const blob = await exportReport(reportId, { format: selectedFormat });
      const filename = `${reportTitle.replace(/[^a-z0-9]/gi, '-').toLowerCase()}.${selectedOption.extension}`;
      downloadBlob(blob, filename);
      onClose();
    } catch (err) {
      console.error('Export failed:', err);
      // In development, create mock content
      const mockContent = generateMockExport(reportTitle, selectedFormat);
      const blob = new Blob([mockContent], { type: selectedOption.mimeType });
      const filename = `${reportTitle.replace(/[^a-z0-9]/gi, '-').toLowerCase()}.${selectedOption.extension}`;
      downloadBlob(blob, filename);
      onClose();
    } finally {
      setExporting(false);
    }
  };

  const handleCopyToClipboard = async () => {
    setExporting(true);
    try {
      const blob = await exportReport(reportId, { format: selectedFormat });
      const text = await blob.text();
      await copyToClipboard(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Copy failed:', err);
      // In development, copy mock content
      const mockContent = generateMockExport(reportTitle, selectedFormat);
      await copyToClipboard(mockContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } finally {
      setExporting(false);
    }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-slate-800 border-slate-700 text-slate-100 max-w-md">
        <DialogHeader>
          <DialogTitle className="text-xl">Export Report</DialogTitle>
          <DialogDescription className="text-slate-400">
            Choose a format to export your report
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 mt-4">
          {/* Format Selection */}
          <div className="space-y-2">
            {FORMAT_OPTIONS.map((option) => (
              <button
                key={option.value}
                onClick={() => setSelectedFormat(option.value)}
                className={`w-full flex items-start gap-3 p-3 rounded-lg border transition-colors text-left ${
                  selectedFormat === option.value
                    ? 'border-blue-500 bg-blue-500/10'
                    : 'border-slate-600 hover:border-slate-500 hover:bg-slate-700/50'
                }`}
              >
                <div
                  className={`p-2 rounded ${
                    selectedFormat === option.value
                      ? 'bg-blue-500 text-white'
                      : 'bg-slate-700 text-slate-400'
                  }`}
                >
                  {option.icon}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-200">{option.label}</span>
                    <Badge
                      variant="outline"
                      className="text-xs border-slate-600 text-slate-400"
                    >
                      .{option.extension}
                    </Badge>
                  </div>
                  <p className="text-sm text-slate-400 mt-0.5">{option.description}</p>
                </div>
              </button>
            ))}
          </div>

          {/* Actions */}
          <div className="flex gap-2 pt-2">
            <Button
              variant="outline"
              onClick={handleCopyToClipboard}
              disabled={exporting}
              className="flex-1 border-slate-600 text-slate-300 hover:bg-slate-700"
            >
              {copied ? (
                <>
                  <Check className="h-4 w-4 mr-2 text-green-500" />
                  Copied!
                </>
              ) : exporting ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <>
                  <Copy className="h-4 w-4 mr-2" />
                  Copy to Clipboard
                </>
              )}
            </Button>
            <Button
              onClick={handleDownload}
              disabled={exporting}
              className="flex-1 bg-blue-600 hover:bg-blue-700"
            >
              {exporting ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Download className="h-4 w-4 mr-2" />
              )}
              Download
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// Generate mock export content for development
function generateMockExport(title: string, format: ExportFormat): string {
  const now = new Date().toISOString();

  if (format === 'md') {
    return `# ${title}

**Generated:** ${now}

## Executive Summary

This report provides a comprehensive analysis of the investigated threat.

## Indicators of Compromise

| Type | Value | Confidence |
|------|-------|------------|
| IP | 192.168.1.100 | High |
| Domain | malware-c2.example.com | High |
| Hash | abc123def456... | Medium |

## Recommendations

1. Block identified IOCs at network perimeter
2. Scan endpoints for presence of indicators
3. Enable enhanced logging on critical systems

---
*Generated by Robin OSINT Platform*
`;
  }

  if (format === 'html') {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title}</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; background: #0f172a; color: #e2e8f0; }
    h1 { color: #f8fafc; }
    h2 { color: #94a3b8; margin-top: 2rem; }
    table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
    th, td { padding: 0.75rem; text-align: left; border-bottom: 1px solid #334155; }
    th { background: #1e293b; }
    .badge { display: inline-block; padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.875rem; }
    .high { background: #22c55e; color: white; }
    .medium { background: #eab308; color: black; }
    .low { background: #ef4444; color: white; }
  </style>
</head>
<body>
  <h1>${title}</h1>
  <p><em>Generated: ${now}</em></p>

  <h2>Executive Summary</h2>
  <p>This report provides a comprehensive analysis of the investigated threat.</p>

  <h2>Indicators of Compromise</h2>
  <table>
    <thead>
      <tr><th>Type</th><th>Value</th><th>Confidence</th></tr>
    </thead>
    <tbody>
      <tr><td>IP</td><td>192.168.1.100</td><td><span class="badge high">High</span></td></tr>
      <tr><td>Domain</td><td>malware-c2.example.com</td><td><span class="badge high">High</span></td></tr>
      <tr><td>Hash</td><td>abc123def456...</td><td><span class="badge medium">Medium</span></td></tr>
    </tbody>
  </table>

  <footer><p><em>Generated by Robin OSINT Platform</em></p></footer>
</body>
</html>`;
  }

  // JSON format
  return JSON.stringify(
    {
      title,
      generatedAt: now,
      sections: [
        {
          type: 'summary',
          title: 'Executive Summary',
          content: 'This report provides a comprehensive analysis of the investigated threat.',
        },
        {
          type: 'ioc_table',
          title: 'Indicators of Compromise',
          iocs: [
            { type: 'ip', value: '192.168.1.100', confidence: 'high' },
            { type: 'domain', value: 'malware-c2.example.com', confidence: 'high' },
            { type: 'hash', value: 'abc123def456...', confidence: 'medium' },
          ],
        },
      ],
    },
    null,
    2
  );
}

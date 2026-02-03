'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, Download, Edit, FileText, Share2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import ReportPreview from '@/components/reports/ReportPreview';
import ExportOptions from '@/components/reports/ExportOptions';
import { Report } from '@/types';
import { getReport } from '@/lib/api';
import { formatDateTime } from '@/lib/utils';

export default function ReportDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeSection, setActiveSection] = useState<string | null>(null);
  const [showExportOptions, setShowExportOptions] = useState(false);

  useEffect(() => {
    async function loadReport() {
      if (!params.id) return;

      try {
        const data = await getReport(params.id as string);
        setReport(data);
        if (data.sections.length > 0) {
          setActiveSection(data.sections[0].id);
        }
      } catch (err) {
        console.error('Failed to load report:', err);
        // Mock data for development
        setReport({
          id: params.id as string,
          title: 'APT28 Ransomware Campaign Analysis',
          investigation_id: 'inv-1',
          sections: [
            {
              id: 's1',
              type: 'summary',
              title: 'Executive Summary',
              content: `## Overview

This investigation analyzed a ransomware campaign attributed to APT28 (also known as Fancy Bear). The campaign targeted multiple organizations across the financial sector.

### Key Findings

- **Threat Actor**: APT28 / Fancy Bear
- **Campaign Duration**: September 2024 - December 2024
- **Primary Target**: Financial institutions
- **Attack Vector**: Spear-phishing with malicious attachments

### Impact Assessment

The campaign has resulted in significant data exfiltration and operational disruption for affected organizations.`,
              order: 0,
            },
            {
              id: 's2',
              type: 'entities',
              title: 'Indicators of Compromise',
              content: '',
              order: 1,
            },
            {
              id: 's3',
              type: 'findings',
              title: 'Technical Analysis',
              content: `## Malware Analysis

The primary payload identified is X-Agent, a modular backdoor with the following capabilities:

- Remote command execution
- Keylogging
- Screen capture
- File exfiltration

### C2 Infrastructure

The malware communicates with command and control servers using encrypted HTTPS traffic. Multiple domains have been identified as part of the C2 infrastructure.

### Persistence Mechanism

The malware establishes persistence through:
1. Registry run keys
2. Scheduled tasks
3. WMI event subscriptions`,
              order: 2,
            },
            {
              id: 's4',
              type: 'recommendations',
              title: 'Recommendations',
              content: `## Mitigation Recommendations

### Immediate Actions

1. Block identified IOCs at network perimeter
2. Scan endpoints for presence of X-Agent indicators
3. Reset credentials for potentially compromised accounts
4. Enable enhanced logging on critical systems

### Long-term Improvements

- Implement application whitelisting
- Deploy endpoint detection and response (EDR) solutions
- Conduct regular security awareness training
- Establish threat intelligence sharing partnerships`,
              order: 3,
            },
          ],
          created_at: new Date(Date.now() - 86400000).toISOString(),
          updated_at: new Date().toISOString(),
          status: 'published',
        });
        setActiveSection('s1');
      } finally {
        setLoading(false);
      }
    }
    loadReport();
  }, [params.id]);

  const handleSectionClick = (sectionId: string) => {
    setActiveSection(sectionId);
    // Scroll to section in preview
    const element = document.getElementById(`section-${sectionId}`);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="animate-pulse text-slate-400">Loading report...</div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="text-center">
          <FileText className="h-12 w-12 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400 mb-4">Report not found</p>
          <Button onClick={() => router.push('/reports')} variant="outline" className="border-slate-700">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Reports
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-slate-900 border-b border-slate-800 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => router.push('/reports')}
              className="text-slate-400 hover:text-white"
            >
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-xl font-semibold text-slate-100">{report.title}</h1>
                <Badge
                  variant={report.status === 'published' ? 'default' : 'secondary'}
                  className={
                    report.status === 'published'
                      ? 'bg-green-600 text-white'
                      : 'bg-slate-600 text-slate-200'
                  }
                >
                  {report.status}
                </Badge>
              </div>
              <p className="text-sm text-slate-400">
                Last updated {formatDateTime(report.updated_at)}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              className="border-slate-700 text-slate-300 hover:bg-slate-800"
              onClick={() => setShowExportOptions(true)}
            >
              <Download className="h-4 w-4 mr-2" />
              Export
            </Button>
            <Button
              variant="outline"
              className="border-slate-700 text-slate-300 hover:bg-slate-800"
            >
              <Share2 className="h-4 w-4 mr-2" />
              Share
            </Button>
            <Button
              onClick={() => router.push(`/reports/builder?id=${report.id}`)}
              className="bg-blue-600 hover:bg-blue-700"
            >
              <Edit className="h-4 w-4 mr-2" />
              Edit
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto flex">
        {/* Section Navigation */}
        <aside className="w-64 border-r border-slate-800 p-4 sticky top-[73px] h-[calc(100vh-73px)]">
          <h3 className="text-sm font-medium text-slate-400 mb-3 uppercase tracking-wider">
            Sections
          </h3>
          <nav className="space-y-1">
            {report.sections
              .sort((a, b) => a.order - b.order)
              .map((section) => (
                <button
                  key={section.id}
                  onClick={() => handleSectionClick(section.id)}
                  className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                    activeSection === section.id
                      ? 'bg-blue-600/20 text-blue-400 border-l-2 border-blue-500'
                      : 'text-slate-300 hover:bg-slate-800'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <Badge
                      variant="outline"
                      className="text-xs border-slate-600 text-slate-400 capitalize"
                    >
                      {section.type.replace('_', ' ')}
                    </Badge>
                  </div>
                  <span className="block mt-1">{section.title}</span>
                </button>
              ))}
          </nav>
        </aside>

        {/* Report Preview */}
        <main className="flex-1 p-6">
          <ScrollArea className="h-[calc(100vh-120px)]">
            <ReportPreview report={report} />
          </ScrollArea>
        </main>
      </div>

      {/* Export Options Modal */}
      {showExportOptions && (
        <ExportOptions
          reportId={report.id}
          reportTitle={report.title}
          onClose={() => setShowExportOptions(false)}
        />
      )}
    </div>
  );
}

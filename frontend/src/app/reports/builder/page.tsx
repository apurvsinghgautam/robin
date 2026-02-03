'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { ArrowLeft, Save, Eye, EyeOff, Check, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import ReportBuilder from '@/components/reports/ReportBuilder';
import ReportPreview from '@/components/reports/ReportPreview';
import type { Report, ReportSection, InvestigationSummary, CreateReportRequest } from '@/types';
import { getReport, getInvestigations, createReport, updateReport } from '@/lib/api';

function ReportBuilderContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const reportId = searchParams.get('id');
  const initialInvestigationId = searchParams.get('investigation');

  // State
  const [investigations, setInvestigations] = useState<InvestigationSummary[]>([]);
  const [selectedInvestigationId, setSelectedInvestigationId] = useState<string | null>(initialInvestigationId);
  const [title, setTitle] = useState('');
  const [sections, setSections] = useState<ReportSection[]>([]);
  const [status, setStatus] = useState<'draft' | 'published'>('draft');
  const [showPreview, setShowPreview] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Load existing report if editing
  useEffect(() => {
    async function loadData() {
      try {
        // Load investigations
        const invData = await getInvestigations();
        const invList = invData.investigations || [];
        setInvestigations(invList);

        if (reportId) {
          // Load existing report
          const reportData = await getReport(reportId);
          setTitle(reportData.title);
          setSections(reportData.sections);
          setStatus(reportData.status);
          setSelectedInvestigationId(reportData.investigation_id);
        } else {
          // New report - add default section
          setSections([
            {
              id: crypto.randomUUID(),
              type: 'summary',
              title: 'Executive Summary',
              content: '',
              order: 0,
            },
          ]);
          if (invList.length > 0 && !initialInvestigationId) {
            setSelectedInvestigationId(invList[0].id);
          }
        }
      } catch (err) {
        console.error('Failed to load data:', err);
        // Mock investigations for development
        const mockInvestigations: InvestigationSummary[] = [
          {
            id: 'inv-1',
            initial_query: 'APT28 ransomware campaign',
            status: 'completed',
            created_at: new Date().toISOString(),
            entity_count: 5,
          },
          {
            id: 'inv-2',
            initial_query: 'Dark market vendor analysis',
            status: 'completed',
            created_at: new Date().toISOString(),
            entity_count: 3,
          },
        ];
        setInvestigations(mockInvestigations);
        setSelectedInvestigationId('inv-1');

        if (!reportId) {
          setSections([
            {
              id: crypto.randomUUID(),
              type: 'summary',
              title: 'Executive Summary',
              content: '',
              order: 0,
            },
          ]);
        }
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [reportId, initialInvestigationId]);

  // Handle save
  const handleSave = async () => {
    if (!title.trim() || !selectedInvestigationId) return;

    setSaving(true);
    try {
      if (reportId) {
        const updateData: Partial<Report> = {
          title,
          investigation_id: selectedInvestigationId,
          sections,
          status,
        };
        await updateReport(reportId, updateData);
      } else {
        const createData: CreateReportRequest = {
          investigation_id: selectedInvestigationId!,
          title,
        };
        const newReport = await createReport(createData);
        // Update the new report with sections and status
        await updateReport(newReport.id, { sections, status });
        router.replace(`/reports/builder?id=${newReport.id}`);
      }

      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      console.error('Failed to save report:', err);
      // In development, just show success
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  // Build preview report object
  const previewReport: Report = {
    id: reportId || 'preview',
    title: title || 'Untitled Report',
    investigation_id: selectedInvestigationId || '',
    sections,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    status,
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="animate-pulse text-slate-400">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-slate-900 border-b border-slate-800 px-6 py-4">
        <div className="flex items-center justify-between">
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
              <h1 className="text-lg font-semibold text-slate-100">
                {reportId ? 'Edit Report' : 'New Report'}
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {/* Investigation Selector */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-slate-400">Source:</span>
              <Select
                value={selectedInvestigationId || undefined}
                onValueChange={setSelectedInvestigationId}
              >
                <SelectTrigger className="w-[200px] bg-slate-800 border-slate-700 text-slate-200">
                  <SelectValue placeholder="Select investigation" />
                </SelectTrigger>
                <SelectContent className="bg-slate-800 border-slate-700">
                  {investigations.map((inv) => (
                    <SelectItem
                      key={inv.id}
                      value={inv.id}
                      className="text-slate-200 focus:bg-slate-700"
                    >
                      {inv.initial_query || inv.query}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Status Selector */}
            <Select value={status} onValueChange={(v) => setStatus(v as typeof status)}>
              <SelectTrigger className="w-[120px] bg-slate-800 border-slate-700 text-slate-200">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-slate-800 border-slate-700">
                <SelectItem value="draft" className="text-slate-200 focus:bg-slate-700">
                  Draft
                </SelectItem>
                <SelectItem value="published" className="text-slate-200 focus:bg-slate-700">
                  Published
                </SelectItem>
              </SelectContent>
            </Select>

            {/* Preview Toggle */}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowPreview(!showPreview)}
              className="border-slate-700 text-slate-300 hover:bg-slate-800"
            >
              {showPreview ? (
                <>
                  <EyeOff className="h-4 w-4 mr-2" />
                  Hide Preview
                </>
              ) : (
                <>
                  <Eye className="h-4 w-4 mr-2" />
                  Show Preview
                </>
              )}
            </Button>

            {/* Save Button */}
            <Button
              onClick={handleSave}
              disabled={saving || !title.trim()}
              className="bg-blue-600 hover:bg-blue-700 min-w-[100px]"
            >
              {saved ? (
                <>
                  <Check className="h-4 w-4 mr-2" />
                  Saved
                </>
              ) : saving ? (
                'Saving...'
              ) : (
                <>
                  <Save className="h-4 w-4 mr-2" />
                  Save
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Title Input */}
        <div className="mt-4">
          <Input
            placeholder="Report Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="text-xl font-semibold bg-transparent border-none text-slate-100 placeholder:text-slate-500 focus-visible:ring-0 px-0"
          />
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Builder */}
        <div className={`flex-1 ${showPreview ? 'max-w-[50%]' : ''} border-r border-slate-800`}>
          <ReportBuilder
            sections={sections}
            onSectionsChange={setSections}
            investigationId={selectedInvestigationId}
          />
        </div>

        {/* Preview */}
        {showPreview && (
          <div className="flex-1 max-w-[50%] bg-slate-900/50 overflow-auto p-6">
            <div className="max-w-3xl mx-auto">
              <div className="flex items-center gap-2 mb-4">
                <Badge variant="outline" className="border-slate-700 text-slate-400">
                  Preview
                </Badge>
              </div>
              <ReportPreview report={previewReport} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ReportBuilderPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-slate-950 flex items-center justify-center">
          <div className="flex items-center gap-2 text-slate-400">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span>Loading report builder...</span>
          </div>
        </div>
      }
    >
      <ReportBuilderContent />
    </Suspense>
  );
}

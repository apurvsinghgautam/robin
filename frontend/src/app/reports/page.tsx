'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Plus, Search, FileText, Clock, Filter } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Report } from '@/types';
import { getReports } from '@/lib/api';
import { formatRelativeTime, truncate } from '@/lib/utils';

export default function ReportsPage() {
  const router = useRouter();
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'draft' | 'published'>('all');

  useEffect(() => {
    async function loadReports() {
      try {
        const data = await getReports();
        setReports(data.reports);
      } catch (err) {
        console.error('Failed to load reports:', err);
        // Mock data for development
        setReports([
          {
            id: '1',
            title: 'APT28 Ransomware Campaign Analysis',
            investigation_id: 'inv-1',
            sections: [
              { id: 's1', type: 'summary', title: 'Executive Summary', content: 'This report analyzes...', order: 0 },
              { id: 's2', type: 'entities', title: 'Indicators of Compromise', content: '', order: 1 },
            ],
            created_at: new Date(Date.now() - 86400000).toISOString(),
            updated_at: new Date().toISOString(),
            status: 'published',
          },
          {
            id: '2',
            title: 'Dark Market Vendor Investigation',
            investigation_id: 'inv-2',
            sections: [
              { id: 's3', type: 'summary', title: 'Summary', content: 'Investigation of...', order: 0 },
            ],
            created_at: new Date(Date.now() - 172800000).toISOString(),
            updated_at: new Date(Date.now() - 3600000).toISOString(),
            status: 'draft',
          },
          {
            id: '3',
            title: 'Critical CVE Exploitation Report',
            investigation_id: 'inv-3',
            sections: [
              { id: 's4', type: 'summary', title: 'Overview', content: 'Critical vulnerability...', order: 0 },
              { id: 's5', type: 'findings', title: 'Technical Analysis', content: 'Detailed analysis...', order: 1 },
              { id: 's6', type: 'entities', title: 'IOCs', content: '', order: 2 },
            ],
            created_at: new Date(Date.now() - 604800000).toISOString(),
            updated_at: new Date(Date.now() - 86400000).toISOString(),
            status: 'published',
          },
        ]);
      } finally {
        setLoading(false);
      }
    }
    loadReports();
  }, []);

  const filteredReports = reports.filter((report) => {
    const matchesSearch = report.title.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || report.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="min-h-screen bg-slate-950 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-slate-100">Reports</h1>
            <p className="text-slate-400 mt-1">Create and manage investigation reports</p>
          </div>
          <Button
            onClick={() => router.push('/reports/builder')}
            className="bg-blue-600 hover:bg-blue-700"
          >
            <Plus className="h-4 w-4 mr-2" />
            New Report
          </Button>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-4 mb-6">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <Input
              placeholder="Search reports..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 bg-slate-800 border-slate-700 text-slate-200 placeholder:text-slate-400"
            />
          </div>
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-slate-400" />
            <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as typeof statusFilter)}>
              <SelectTrigger className="w-[140px] bg-slate-800 border-slate-700 text-slate-200">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-slate-800 border-slate-700">
                <SelectItem value="all" className="text-slate-200 focus:bg-slate-700">All Status</SelectItem>
                <SelectItem value="draft" className="text-slate-200 focus:bg-slate-700">Draft</SelectItem>
                <SelectItem value="published" className="text-slate-200 focus:bg-slate-700">Published</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Reports Grid */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <Card key={i} className="bg-slate-800 border-slate-700 animate-pulse">
                <CardHeader>
                  <div className="h-5 bg-slate-700 rounded w-3/4" />
                  <div className="h-4 bg-slate-700 rounded w-1/2 mt-2" />
                </CardHeader>
                <CardContent>
                  <div className="h-4 bg-slate-700 rounded w-full mb-2" />
                  <div className="h-4 bg-slate-700 rounded w-2/3" />
                </CardContent>
              </Card>
            ))}
          </div>
        ) : filteredReports.length === 0 ? (
          <div className="text-center py-12">
            <FileText className="h-12 w-12 text-slate-600 mx-auto mb-3" />
            <p className="text-slate-400 mb-2">
              {searchQuery || statusFilter !== 'all' ? 'No reports match your filters' : 'No reports yet'}
            </p>
            <p className="text-sm text-slate-500">
              {searchQuery || statusFilter !== 'all' ? 'Try adjusting your filters' : 'Create your first report to get started'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredReports.map((report) => (
              <Card
                key={report.id}
                className="bg-slate-800 border-slate-700 hover:border-slate-600 transition-colors cursor-pointer group"
                onClick={() => router.push(`/reports/${report.id}`)}
              >
                <CardHeader>
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle className="text-lg text-slate-100 group-hover:text-blue-400 transition-colors">
                      {truncate(report.title, 50)}
                    </CardTitle>
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
                  <CardDescription className="text-slate-400">
                    {report.sections.length} section{report.sections.length !== 1 ? 's' : ''}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {/* Section Preview */}
                  <div className="flex flex-wrap gap-1.5 mb-4">
                    {report.sections.slice(0, 3).map((section) => (
                      <Badge
                        key={section.id}
                        variant="outline"
                        className="text-xs border-slate-600 text-slate-400"
                      >
                        {section.title}
                      </Badge>
                    ))}
                    {report.sections.length > 3 && (
                      <Badge
                        variant="outline"
                        className="text-xs border-slate-600 text-slate-400"
                      >
                        +{report.sections.length - 3} more
                      </Badge>
                    )}
                  </div>

                  {/* Timestamps */}
                  <div className="flex items-center gap-4 text-xs text-slate-500">
                    <div className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      <span>Created {formatRelativeTime(report.created_at)}</span>
                    </div>
                    {report.updated_at !== report.created_at && (
                      <span>Updated {formatRelativeTime(report.updated_at)}</span>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

'use client';

import React, { useState, useMemo } from 'react';
import { Copy, Check, ArrowUpDown, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { IOCEntry } from '@/types';
import { copyToClipboard } from '@/lib/utils';

interface IOCTableProps {
  iocs: IOCEntry[];
  editable?: boolean;
  onIOCsChange?: (iocs: IOCEntry[]) => void;
}

type SortField = 'type' | 'value' | 'context' | 'confidence';
type SortDirection = 'asc' | 'desc';

const CONFIDENCE_COLORS: Record<IOCEntry['confidence'], string> = {
  high: '#22c55e',
  medium: '#eab308',
  low: '#ef4444',
};

const IOC_TYPE_COLORS: Record<IOCEntry['type'], string> = {
  ip: 'bg-blue-600',
  domain: 'bg-purple-600',
  hash: 'bg-orange-600',
  email: 'bg-green-600',
  url: 'bg-cyan-600',
};

export default function IOCTable({ iocs, editable = false, onIOCsChange }: IOCTableProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState<IOCEntry['type'] | 'all'>('all');
  const [confidenceFilter, setConfidenceFilter] = useState<IOCEntry['confidence'] | 'all'>('all');
  const [sortField, setSortField] = useState<SortField>('type');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [copiedValue, setCopiedValue] = useState<string | null>(null);

  // Filter and sort IOCs
  const filteredIOCs = useMemo(() => {
    let result = [...iocs];

    // Apply search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(
        (ioc) =>
          ioc.value.toLowerCase().includes(query) ||
          ioc.context.toLowerCase().includes(query)
      );
    }

    // Apply type filter
    if (typeFilter !== 'all') {
      result = result.filter((ioc) => ioc.type === typeFilter);
    }

    // Apply confidence filter
    if (confidenceFilter !== 'all') {
      result = result.filter((ioc) => ioc.confidence === confidenceFilter);
    }

    // Apply sorting
    result.sort((a, b) => {
      let comparison = 0;
      if (sortField === 'type') {
        comparison = a.type.localeCompare(b.type);
      } else if (sortField === 'value') {
        comparison = a.value.localeCompare(b.value);
      } else if (sortField === 'context') {
        comparison = a.context.localeCompare(b.context);
      } else if (sortField === 'confidence') {
        const order = { high: 0, medium: 1, low: 2 };
        comparison = order[a.confidence] - order[b.confidence];
      }
      return sortDirection === 'asc' ? comparison : -comparison;
    });

    return result;
  }, [iocs, searchQuery, typeFilter, confidenceFilter, sortField, sortDirection]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const handleCopy = async (value: string) => {
    await copyToClipboard(value);
    setCopiedValue(value);
    setTimeout(() => setCopiedValue(null), 2000);
  };

  const handleCopyAll = async () => {
    const values = filteredIOCs.map((ioc) => ioc.value).join('\n');
    await copyToClipboard(values);
    setCopiedValue('all');
    setTimeout(() => setCopiedValue(null), 2000);
  };

  // Get unique types for filter
  const uniqueTypes = Array.from(new Set(iocs.map((ioc) => ioc.type)));

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <Input
            placeholder="Search IOCs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10 bg-slate-700 border-slate-600 text-slate-200 placeholder:text-slate-400"
          />
        </div>

        <Select value={typeFilter} onValueChange={(v) => setTypeFilter(v as typeof typeFilter)}>
          <SelectTrigger className="w-[130px] bg-slate-700 border-slate-600 text-slate-200">
            <SelectValue placeholder="Type" />
          </SelectTrigger>
          <SelectContent className="bg-slate-800 border-slate-700">
            <SelectItem value="all" className="text-slate-200 focus:bg-slate-700">All Types</SelectItem>
            {uniqueTypes.map((type) => (
              <SelectItem
                key={type}
                value={type}
                className="text-slate-200 focus:bg-slate-700 capitalize"
              >
                {type}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={confidenceFilter}
          onValueChange={(v) => setConfidenceFilter(v as typeof confidenceFilter)}
        >
          <SelectTrigger className="w-[140px] bg-slate-700 border-slate-600 text-slate-200">
            <SelectValue placeholder="Confidence" />
          </SelectTrigger>
          <SelectContent className="bg-slate-800 border-slate-700">
            <SelectItem value="all" className="text-slate-200 focus:bg-slate-700">All Confidence</SelectItem>
            <SelectItem value="high" className="text-slate-200 focus:bg-slate-700">High</SelectItem>
            <SelectItem value="medium" className="text-slate-200 focus:bg-slate-700">Medium</SelectItem>
            <SelectItem value="low" className="text-slate-200 focus:bg-slate-700">Low</SelectItem>
          </SelectContent>
        </Select>

        <Button
          variant="outline"
          size="sm"
          onClick={handleCopyAll}
          className="border-slate-600 text-slate-300 hover:bg-slate-700"
        >
          {copiedValue === 'all' ? (
            <>
              <Check className="h-4 w-4 mr-2" />
              Copied!
            </>
          ) : (
            <>
              <Copy className="h-4 w-4 mr-2" />
              Copy All
            </>
          )}
        </Button>
      </div>

      {/* Table */}
      <div className="rounded-lg border border-slate-700 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-slate-700 hover:bg-transparent">
              <TableHead className="bg-slate-800 text-slate-300">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSort('type')}
                  className="h-auto p-0 font-semibold text-slate-300 hover:text-white"
                >
                  Type
                  <ArrowUpDown className="ml-1 h-3 w-3" />
                </Button>
              </TableHead>
              <TableHead className="bg-slate-800 text-slate-300">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSort('value')}
                  className="h-auto p-0 font-semibold text-slate-300 hover:text-white"
                >
                  Value
                  <ArrowUpDown className="ml-1 h-3 w-3" />
                </Button>
              </TableHead>
              <TableHead className="bg-slate-800 text-slate-300">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSort('context')}
                  className="h-auto p-0 font-semibold text-slate-300 hover:text-white"
                >
                  Context
                  <ArrowUpDown className="ml-1 h-3 w-3" />
                </Button>
              </TableHead>
              <TableHead className="bg-slate-800 text-slate-300">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSort('confidence')}
                  className="h-auto p-0 font-semibold text-slate-300 hover:text-white"
                >
                  Confidence
                  <ArrowUpDown className="ml-1 h-3 w-3" />
                </Button>
              </TableHead>
              <TableHead className="bg-slate-800 text-slate-300 w-[80px]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredIOCs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-slate-500 py-8">
                  No IOCs found
                </TableCell>
              </TableRow>
            ) : (
              filteredIOCs.map((ioc, index) => (
                <TableRow
                  key={`${ioc.type}-${ioc.value}-${index}`}
                  className="border-slate-700 hover:bg-slate-800/50"
                >
                  <TableCell>
                    <Badge
                      className={`${IOC_TYPE_COLORS[ioc.type]} text-white capitalize`}
                    >
                      {ioc.type}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-sm text-slate-200">
                    {ioc.value}
                  </TableCell>
                  <TableCell className="text-slate-300">{ioc.context}</TableCell>
                  <TableCell>
                    <Badge
                      className="capitalize"
                      style={{
                        backgroundColor: CONFIDENCE_COLORS[ioc.confidence],
                        color: ioc.confidence === 'medium' ? '#1e293b' : 'white',
                      }}
                    >
                      {ioc.confidence}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleCopy(ioc.value)}
                      className="h-8 w-8 text-slate-400 hover:text-white"
                    >
                      {copiedValue === ioc.value ? (
                        <Check className="h-4 w-4 text-green-500" />
                      ) : (
                        <Copy className="h-4 w-4" />
                      )}
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Summary */}
      <div className="text-sm text-slate-400">
        Showing {filteredIOCs.length} of {iocs.length} IOCs
      </div>
    </div>
  );
}

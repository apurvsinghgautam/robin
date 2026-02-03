'use client';

import React from 'react';
import { Search, X, Calendar } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';

type StatusType = 'completed' | 'error' | 'streaming' | 'pending';

interface HistoryFiltersProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  selectedStatuses: StatusType[];
  onStatusChange: (statuses: StatusType[]) => void;
  startDate: string;
  onStartDateChange: (date: string) => void;
  endDate: string;
  onEndDateChange: (date: string) => void;
  onClearFilters: () => void;
  hasActiveFilters: boolean;
}

const STATUS_OPTIONS: { value: StatusType; label: string; color: string }[] = [
  { value: 'completed', label: 'Completed', color: 'bg-green-600' },
  { value: 'error', label: 'Error', color: 'bg-red-600' },
  { value: 'streaming', label: 'Running', color: 'bg-blue-600' },
  { value: 'pending', label: 'Pending', color: 'bg-yellow-600' },
];

export default function HistoryFilters({
  searchQuery,
  onSearchChange,
  selectedStatuses,
  onStatusChange,
  startDate,
  onStartDateChange,
  endDate,
  onEndDateChange,
  onClearFilters,
  hasActiveFilters,
}: HistoryFiltersProps) {
  const handleStatusToggle = (status: StatusType) => {
    if (selectedStatuses.includes(status)) {
      onStatusChange(selectedStatuses.filter((s) => s !== status));
    } else {
      onStatusChange([...selectedStatuses, status]);
    }
  };

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700 p-4 mb-6">
      <div className="flex flex-wrap items-center gap-4">
        {/* Search */}
        <div className="relative flex-1 min-w-[240px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <Input
            placeholder="Search by query..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-10 pr-8 bg-slate-700 border-slate-600 text-slate-200 placeholder:text-slate-400"
          />
          {searchQuery && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onSearchChange('')}
              className="absolute right-1 top-1/2 -translate-y-1/2 h-6 w-6 text-slate-400 hover:text-slate-200"
            >
              <X className="h-3 w-3" />
            </Button>
          )}
        </div>

        {/* Status Filters */}
        <div className="flex items-center gap-4">
          <span className="text-sm text-slate-400">Status:</span>
          <div className="flex items-center gap-3">
            {STATUS_OPTIONS.map((option) => (
              <div key={option.value} className="flex items-center gap-1.5">
                <Checkbox
                  id={`status-${option.value}`}
                  checked={selectedStatuses.includes(option.value)}
                  onCheckedChange={() => handleStatusToggle(option.value)}
                  className="border-slate-500 data-[state=checked]:bg-blue-600 data-[state=checked]:border-blue-600"
                />
                <Label
                  htmlFor={`status-${option.value}`}
                  className="text-sm text-slate-300 cursor-pointer flex items-center gap-1.5"
                >
                  <div className={`w-2 h-2 rounded-full ${option.color}`} />
                  {option.label}
                </Label>
              </div>
            ))}
          </div>
        </div>

        {/* Date Range */}
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-slate-400" />
          <Input
            type="date"
            value={startDate}
            onChange={(e) => onStartDateChange(e.target.value)}
            className="w-[140px] bg-slate-700 border-slate-600 text-slate-200"
            placeholder="Start date"
          />
          <span className="text-slate-500">to</span>
          <Input
            type="date"
            value={endDate}
            onChange={(e) => onEndDateChange(e.target.value)}
            className="w-[140px] bg-slate-700 border-slate-600 text-slate-200"
            placeholder="End date"
          />
        </div>

        {/* Clear Filters */}
        {hasActiveFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onClearFilters}
            className="text-slate-400 hover:text-slate-200"
          >
            <X className="h-4 w-4 mr-1" />
            Clear Filters
          </Button>
        )}
      </div>

      {/* Active Filters Summary */}
      {hasActiveFilters && (
        <div className="flex items-center gap-2 mt-3 pt-3 border-t border-slate-700">
          <span className="text-sm text-slate-400">Active filters:</span>
          <div className="flex items-center gap-2">
            {searchQuery && (
              <Badge
                variant="secondary"
                className="bg-slate-700 text-slate-300 hover:bg-slate-600 cursor-pointer"
                onClick={() => onSearchChange('')}
              >
                Search: "{searchQuery}"
                <X className="h-3 w-3 ml-1" />
              </Badge>
            )}
            {selectedStatuses.map((status) => (
              <Badge
                key={status}
                variant="secondary"
                className="bg-slate-700 text-slate-300 hover:bg-slate-600 cursor-pointer capitalize"
                onClick={() => handleStatusToggle(status)}
              >
                {status}
                <X className="h-3 w-3 ml-1" />
              </Badge>
            ))}
            {startDate && (
              <Badge
                variant="secondary"
                className="bg-slate-700 text-slate-300 hover:bg-slate-600 cursor-pointer"
                onClick={() => onStartDateChange('')}
              >
                From: {startDate}
                <X className="h-3 w-3 ml-1" />
              </Badge>
            )}
            {endDate && (
              <Badge
                variant="secondary"
                className="bg-slate-700 text-slate-300 hover:bg-slate-600 cursor-pointer"
                onClick={() => onEndDateChange('')}
              >
                To: {endDate}
                <X className="h-3 w-3 ml-1" />
              </Badge>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

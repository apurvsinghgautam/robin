'use client';

import React, { useState } from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical, Trash2, ChevronDown, ChevronUp, Table } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import IOCTable from './IOCTable';
import { ReportSection, IOCEntry } from '@/types';

interface SectionEditorProps {
  section: ReportSection;
  onUpdate: (updates: Partial<ReportSection>) => void;
  onDelete: () => void;
  investigationId: string | null;
}

const SECTION_TYPES: { value: ReportSection['type']; label: string }[] = [
  { value: 'summary', label: 'Summary' },
  { value: 'findings', label: 'Findings' },
  { value: 'entities', label: 'Entities' },
  { value: 'timeline', label: 'Timeline' },
  { value: 'recommendations', label: 'Recommendations' },
  { value: 'custom', label: 'Custom' },
];

// Mock IOC data for development
const MOCK_IOCS: IOCEntry[] = [
  { type: 'ip', value: '192.168.1.100', context: 'C2 server', confidence: 'high' },
  { type: 'domain', value: 'malware-c2.example.com', context: 'Primary C2 domain', confidence: 'high' },
  { type: 'hash', value: 'abc123def456789...', context: 'X-Agent payload', confidence: 'high' },
  { type: 'email', value: 'attacker@evil.com', context: 'Phishing sender', confidence: 'medium' },
  { type: 'ip', value: '10.0.0.50', context: 'Backup C2', confidence: 'medium' },
  { type: 'domain', value: 'backup-c2.example.net', context: 'Backup domain', confidence: 'low' },
];

export default function SectionEditor({
  section,
  onUpdate,
  onDelete,
  investigationId,
}: SectionEditorProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [iocs] = useState<IOCEntry[]>(MOCK_IOCS);

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: section.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`bg-slate-800 rounded-lg border border-slate-700 ${
        isDragging ? 'shadow-lg' : ''
      }`}
    >
      {/* Section Header */}
      <div className="flex items-center gap-2 p-3 border-b border-slate-700">
        {/* Drag Handle */}
        <button
          {...attributes}
          {...listeners}
          className="cursor-grab p-1 text-slate-500 hover:text-slate-300 touch-none"
        >
          <GripVertical className="h-4 w-4" />
        </button>

        {/* Section Type Badge */}
        <Badge
          variant="outline"
          className="text-xs border-slate-600 text-slate-400 capitalize"
        >
          {section.type.replace('_', ' ')}
        </Badge>

        {/* Title Input */}
        <Input
          value={section.title}
          onChange={(e) => onUpdate({ title: e.target.value })}
          className="flex-1 bg-transparent border-none text-slate-200 font-medium focus-visible:ring-0 px-0"
          placeholder="Section Title"
        />

        {/* Collapse Toggle */}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="h-8 w-8 text-slate-400 hover:text-slate-200"
        >
          {isCollapsed ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronUp className="h-4 w-4" />
          )}
        </Button>

        {/* Delete Button */}
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-slate-400 hover:text-red-400"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent className="bg-slate-800 border-slate-700">
            <AlertDialogHeader>
              <AlertDialogTitle className="text-slate-100">Delete Section</AlertDialogTitle>
              <AlertDialogDescription className="text-slate-400">
                Are you sure you want to delete "{section.title}"? This action cannot be undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel className="border-slate-600 text-slate-300 hover:bg-slate-700">
                Cancel
              </AlertDialogCancel>
              <AlertDialogAction
                onClick={onDelete}
                className="bg-red-600 hover:bg-red-700"
              >
                Delete
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>

      {/* Section Content */}
      {!isCollapsed && (
        <div className="p-4">
          {section.type === 'entities' ? (
            <div>
              <div className="flex items-center gap-2 mb-4">
                <Table className="h-4 w-4 text-slate-400" />
                <span className="text-sm text-slate-400">
                  IOC data is automatically populated from the investigation
                </span>
              </div>
              <IOCTable iocs={iocs} editable={false} />
            </div>
          ) : (
            <div className="space-y-3">
              {/* Type Selector */}
              <div className="flex items-center gap-2">
                <span className="text-sm text-slate-400">Type:</span>
                <Select
                  value={section.type}
                  onValueChange={(v) => onUpdate({ type: v as ReportSection['type'] })}
                >
                  <SelectTrigger className="w-[140px] h-8 bg-slate-700 border-slate-600 text-slate-200">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-800 border-slate-700">
                    {SECTION_TYPES.map((type) => (
                      <SelectItem
                        key={type.value}
                        value={type.value}
                        className="text-slate-200 focus:bg-slate-700"
                      >
                        {type.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Content Textarea */}
              <Textarea
                value={section.content}
                onChange={(e) => onUpdate({ content: e.target.value })}
                placeholder="Write your content here... (Markdown supported)"
                className="min-h-[200px] bg-slate-700/50 border-slate-600 text-slate-200 placeholder:text-slate-500 resize-y"
              />

              <p className="text-xs text-slate-500">
                Tip: Use Markdown formatting for headings, lists, and emphasis
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

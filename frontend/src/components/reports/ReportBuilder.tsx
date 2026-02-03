'use client';

import React, { useCallback } from 'react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import SectionEditor from './SectionEditor';
import { ReportSection } from '@/types';

interface ReportBuilderProps {
  sections: ReportSection[];
  onSectionsChange: (sections: ReportSection[]) => void;
  investigationId: string | null;
}

const SECTION_TYPES: { value: ReportSection['type']; label: string; description: string }[] = [
  { value: 'summary', label: 'Summary', description: 'Executive summary or overview' },
  { value: 'findings', label: 'Findings', description: 'Key findings and analysis' },
  { value: 'entities', label: 'Entities', description: 'Extracted entities and IOCs' },
  { value: 'timeline', label: 'Timeline', description: 'Chronological event timeline' },
  { value: 'recommendations', label: 'Recommendations', description: 'Recommended actions' },
  { value: 'custom', label: 'Custom', description: 'Free-form custom content' },
];

export default function ReportBuilder({
  sections,
  onSectionsChange,
  investigationId,
}: ReportBuilderProps) {
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;

      if (over && active.id !== over.id) {
        const oldIndex = sections.findIndex((s) => s.id === active.id);
        const newIndex = sections.findIndex((s) => s.id === over.id);

        const newSections = arrayMove(sections, oldIndex, newIndex).map((section, index) => ({
          ...section,
          order: index,
        }));

        onSectionsChange(newSections);
      }
    },
    [sections, onSectionsChange]
  );

  const handleAddSection = useCallback(
    (type: ReportSection['type']) => {
      const typeConfig = SECTION_TYPES.find((t) => t.value === type);
      const newSection: ReportSection = {
        id: crypto.randomUUID(),
        type,
        title: typeConfig?.label || 'New Section',
        content: '',
        order: sections.length,
      };
      onSectionsChange([...sections, newSection]);
    },
    [sections, onSectionsChange]
  );

  const handleUpdateSection = useCallback(
    (sectionId: string, updates: Partial<ReportSection>) => {
      const newSections = sections.map((section) =>
        section.id === sectionId ? { ...section, ...updates } : section
      );
      onSectionsChange(newSections);
    },
    [sections, onSectionsChange]
  );

  const handleDeleteSection = useCallback(
    (sectionId: string) => {
      const newSections = sections
        .filter((section) => section.id !== sectionId)
        .map((section, index) => ({ ...section, order: index }));
      onSectionsChange(newSections);
    },
    [sections, onSectionsChange]
  );

  const sortedSections = [...sections].sort((a, b) => a.order - b.order);

  return (
    <div className="h-full overflow-auto p-6">
      <div className="max-w-3xl mx-auto space-y-4">
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={sortedSections.map((s) => s.id)}
            strategy={verticalListSortingStrategy}
          >
            {sortedSections.map((section) => (
              <SectionEditor
                key={section.id}
                section={section}
                onUpdate={(updates) => handleUpdateSection(section.id, updates)}
                onDelete={() => handleDeleteSection(section.id)}
                investigationId={investigationId}
              />
            ))}
          </SortableContext>
        </DndContext>

        {/* Add Section Button */}
        <div className="flex justify-center pt-4">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                className="border-dashed border-slate-600 text-slate-400 hover:text-slate-200 hover:bg-slate-800"
              >
                <Plus className="h-4 w-4 mr-2" />
                Add Section
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="bg-slate-800 border-slate-700">
              {SECTION_TYPES.map((type) => (
                <DropdownMenuItem
                  key={type.value}
                  onClick={() => handleAddSection(type.value)}
                  className="text-slate-200 focus:bg-slate-700 focus:text-white cursor-pointer"
                >
                  <div>
                    <div className="font-medium">{type.label}</div>
                    <div className="text-xs text-slate-400">{type.description}</div>
                  </div>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {sections.length === 0 && (
          <div className="text-center py-12 text-slate-500">
            <p className="mb-2">No sections yet</p>
            <p className="text-sm">Click "Add Section" to get started</p>
          </div>
        )}
      </div>
    </div>
  );
}

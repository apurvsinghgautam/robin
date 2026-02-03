'use client';

import { useState } from 'react';
import { Menu, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Sidebar } from './Sidebar';
import {
  Sheet,
  SheetContent,
  SheetTrigger,
} from '@/components/ui/sheet';

// ============================================
// Types
// ============================================

interface MainLayoutProps {
  children: React.ReactNode;
}

// ============================================
// Mobile Sidebar
// ============================================

function MobileSidebar() {
  const [open, setOpen] = useState(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden fixed top-4 left-4 z-50 h-10 w-10 bg-card/80 backdrop-blur-sm"
        >
          <Menu className="h-5 w-5" />
          <span className="sr-only">Toggle menu</span>
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="p-0 w-64">
        <Sidebar isCollapsed={false} onToggle={() => setOpen(false)} />
      </SheetContent>
    </Sheet>
  );
}

// ============================================
// MainLayout Component
// ============================================

export function MainLayout({ children }: MainLayoutProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      {/* Desktop Sidebar */}
      <div className="hidden md:flex">
        <Sidebar
          isCollapsed={isCollapsed}
          onToggle={() => setIsCollapsed(!isCollapsed)}
        />
      </div>

      {/* Mobile Sidebar */}
      <MobileSidebar />

      {/* Main Content */}
      <main
        className={cn(
          'flex-1 overflow-auto',
          'transition-all duration-300'
        )}
      >
        {children}
      </main>
    </div>
  );
}

export default MainLayout;

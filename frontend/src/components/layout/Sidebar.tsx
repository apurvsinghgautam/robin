'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Search,
  Network,
  FileText,
  History,
  Settings,
  Plus,
  ChevronLeft,
  ChevronRight,
  Shield,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

// ============================================
// Types
// ============================================

interface SidebarProps {
  isCollapsed: boolean;
  onToggle: () => void;
}

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: number;
}

// ============================================
// Navigation Items
// ============================================

const navItems: NavItem[] = [
  {
    name: 'Investigations',
    href: '/investigations',
    icon: Search,
  },
  {
    name: 'Graph',
    href: '/graph',
    icon: Network,
  },
  {
    name: 'Reports',
    href: '/reports',
    icon: FileText,
  },
  {
    name: 'History',
    href: '/history',
    icon: History,
  },
];

const bottomNavItems: NavItem[] = [
  {
    name: 'Settings',
    href: '/settings',
    icon: Settings,
  },
];

// ============================================
// Sidebar Component
// ============================================

export function Sidebar({ isCollapsed, onToggle }: SidebarProps) {
  const pathname = usePathname();

  return (
    <TooltipProvider delayDuration={0}>
      <aside
        className={cn(
          'flex flex-col h-full bg-card border-r border-border transition-all duration-300',
          isCollapsed ? 'w-16' : 'w-64'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between h-16 px-4 border-b border-border">
          <Link
            href="/"
            className={cn(
              'flex items-center gap-2 transition-opacity',
              isCollapsed && 'opacity-0 pointer-events-none'
            )}
          >
            <Shield className="h-8 w-8 text-primary" />
            <span className="font-bold text-xl gradient-text">Robin</span>
          </Link>

          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={onToggle}
          >
            {isCollapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <ChevronLeft className="h-4 w-4" />
            )}
          </Button>
        </div>

        {/* New Investigation Button */}
        <div className="p-4">
          <Tooltip>
            <TooltipTrigger asChild>
              <Link href="/investigations/new">
                <Button
                  className={cn(
                    'w-full bg-primary hover:bg-primary/90 text-primary-foreground',
                    isCollapsed && 'px-2'
                  )}
                >
                  <Plus className="h-4 w-4" />
                  {!isCollapsed && <span className="ml-2">New Investigation</span>}
                </Button>
              </Link>
            </TooltipTrigger>
            {isCollapsed && (
              <TooltipContent side="right">
                New Investigation
              </TooltipContent>
            )}
          </Tooltip>
        </div>

        {/* Main Navigation */}
        <nav className="flex-1 px-2 py-2 space-y-1 overflow-y-auto">
          {navItems.map((item) => {
            const isActive =
              pathname === item.href || pathname.startsWith(`${item.href}/`);

            return (
              <Tooltip key={item.href}>
                <TooltipTrigger asChild>
                  <Link
                    href={item.href}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2 rounded-md transition-colors',
                      'hover:bg-accent hover:text-accent-foreground',
                      isActive
                        ? 'bg-accent text-accent-foreground'
                        : 'text-muted-foreground',
                      isCollapsed && 'justify-center px-2'
                    )}
                  >
                    <item.icon className="h-5 w-5 flex-shrink-0" />
                    {!isCollapsed && (
                      <>
                        <span className="flex-1">{item.name}</span>
                        {item.badge !== undefined && item.badge > 0 && (
                          <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1.5 text-xs font-medium text-primary-foreground">
                            {item.badge > 99 ? '99+' : item.badge}
                          </span>
                        )}
                      </>
                    )}
                  </Link>
                </TooltipTrigger>
                {isCollapsed && (
                  <TooltipContent side="right" className="flex items-center gap-2">
                    {item.name}
                    {item.badge !== undefined && item.badge > 0 && (
                      <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1.5 text-xs font-medium text-primary-foreground">
                        {item.badge}
                      </span>
                    )}
                  </TooltipContent>
                )}
              </Tooltip>
            );
          })}
        </nav>

        {/* Bottom Navigation */}
        <div className="px-2 py-2 border-t border-border">
          {bottomNavItems.map((item) => {
            const isActive = pathname === item.href;

            return (
              <Tooltip key={item.href}>
                <TooltipTrigger asChild>
                  <Link
                    href={item.href}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2 rounded-md transition-colors',
                      'hover:bg-accent hover:text-accent-foreground',
                      isActive
                        ? 'bg-accent text-accent-foreground'
                        : 'text-muted-foreground',
                      isCollapsed && 'justify-center px-2'
                    )}
                  >
                    <item.icon className="h-5 w-5 flex-shrink-0" />
                    {!isCollapsed && <span>{item.name}</span>}
                  </Link>
                </TooltipTrigger>
                {isCollapsed && (
                  <TooltipContent side="right">{item.name}</TooltipContent>
                )}
              </Tooltip>
            );
          })}
        </div>
      </aside>
    </TooltipProvider>
  );
}

export default Sidebar;

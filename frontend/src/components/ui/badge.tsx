import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
  {
    variants: {
      variant: {
        default:
          'border-transparent bg-primary text-primary-foreground hover:bg-primary/80',
        secondary:
          'border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80',
        destructive:
          'border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80',
        outline: 'text-foreground',
        // Threat type variants
        threat_actor:
          'border-red-500/20 bg-red-500/10 text-red-400',
        ioc:
          'border-blue-500/20 bg-blue-500/10 text-blue-400',
        malware:
          'border-orange-500/20 bg-orange-500/10 text-orange-400',
        marketplace:
          'border-violet-500/20 bg-violet-500/10 text-violet-400',
        vulnerability:
          'border-yellow-500/20 bg-yellow-500/10 text-yellow-400',
        infrastructure:
          'border-cyan-500/20 bg-cyan-500/10 text-cyan-400',
        success:
          'border-emerald-500/20 bg-emerald-500/10 text-emerald-400',
        warning:
          'border-amber-500/20 bg-amber-500/10 text-amber-400',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };

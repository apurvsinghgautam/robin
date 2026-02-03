'use client';

import { QueryProvider } from './QueryProvider';
import { ThemeProvider } from './ThemeProvider';

interface ProvidersProps {
  children: React.ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  return (
    <ThemeProvider
      defaultTheme="dark"
      storageKey="robin-theme"
      attribute="class"
      enableSystem={false}
    >
      <QueryProvider>{children}</QueryProvider>
    </ThemeProvider>
  );
}

export { QueryProvider } from './QueryProvider';
export { ThemeProvider, useTheme } from './ThemeProvider';
export default Providers;

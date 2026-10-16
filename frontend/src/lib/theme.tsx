import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';

type Theme = 'light' | 'dark';
const KEY = 'mm-theme';

function initialTheme(): Theme {
  return document.documentElement.classList.contains('dark') ? 'dark' : 'light';
}

const ThemeContext = createContext<{ theme: Theme; toggle: () => void }>({ theme: 'light', toggle: () => {} });

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    try {
      localStorage.setItem(KEY, theme);
    } catch {
      /* ignore */
    }
  }, [theme]);

  const toggle = useCallback(() => setTheme((t) => (t === 'dark' ? 'light' : 'dark')), []);
  return <ThemeContext.Provider value={{ theme, toggle }}>{children}</ThemeContext.Provider>;
}

export const useTheme = () => useContext(ThemeContext);

// Chart colours: status palette for verdicts (always paired with icon + label), categorical slot 1 for trends.
const CHART = {
  light: {
    grid: '#e2e8f0', axis: '#64748b', text: '#0f172a', surface: '#ffffff',
    series1: '#2a78d6', series2: '#eb6834',
    good: '#0ca30c', warning: '#fab219', serious: '#ec835a', critical: '#d03b3b', neutral: '#94a3b8',
  },
  dark: {
    grid: '#1e293b', axis: '#94a3b8', text: '#f1f5f9', surface: '#0f172a',
    series1: '#3987e5', series2: '#d95926',
    good: '#0ca30c', warning: '#fab219', serious: '#ec835a', critical: '#d03b3b', neutral: '#64748b',
  },
};

export function useChartColors() {
  return CHART[useTheme().theme];
}

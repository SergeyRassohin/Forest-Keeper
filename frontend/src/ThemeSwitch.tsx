import { useEffect, useRef, useState } from 'react';

type Theme = 'light' | 'dark';
function savedTheme(): Theme | null {
  try {
    const value = localStorage.getItem('fk-theme');
    return value === 'light' || value === 'dark' ? value : null;
  } catch { return null; }
}
function systemTheme(): Theme {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function ThemeSwitch() {
  const manual = useRef(savedTheme() !== null || document.documentElement.dataset.themePreference === 'manual');
  const [theme, setTheme] = useState<Theme>(() => {
    const applied = document.documentElement.dataset.theme;
    return applied === 'light' || applied === 'dark' ? applied : savedTheme() ?? systemTheme();
  });
  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);
  useEffect(() => {
    const media = window.matchMedia?.('(prefers-color-scheme: dark)');
    const followSystem = () => { if (!manual.current) setTheme(systemTheme()); };
    const sync = (event: StorageEvent) => {
      if (event.key !== 'fk-theme' && event.key !== null) return;
      const saved = savedTheme();
      manual.current = saved !== null;
      document.documentElement.dataset.themePreference = saved ? 'manual' : 'system';
      setTheme(saved ?? systemTheme());
    };
    media?.addEventListener('change', followSystem);
    window.addEventListener('storage', sync);
    return () => { media?.removeEventListener('change', followSystem); window.removeEventListener('storage', sync); };
  }, []);
  function choose(value: Theme) {
    manual.current = true;
    document.documentElement.dataset.themePreference = 'manual';
    document.documentElement.dataset.theme = value;
    setTheme(value);
    try { localStorage.setItem('fk-theme', value); } catch { /* Session preference still works. */ }
  }
  return <div className="theme-switch" role="group" aria-label="Тема оформления">
    <button type="button" aria-label="Светлая тема" aria-pressed={theme === 'light'} onClick={() => choose('light')}>Светлая</button>
    <button type="button" aria-label="Тёмная тема" aria-pressed={theme === 'dark'} onClick={() => choose('dark')}>Тёмная</button>
  </div>;
}

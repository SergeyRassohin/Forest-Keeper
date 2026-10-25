import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ThemeSwitch } from './ThemeSwitch';

afterEach(() => {
  vi.restoreAllMocks(); vi.unstubAllGlobals(); localStorage.clear();
  delete document.documentElement.dataset.theme;
  delete document.documentElement.dataset.themePreference;
});
function system(dark: boolean) {
  const listeners = new Set<() => void>();
  const media = { matches: dark, addEventListener: (_: string, fn: () => void) => listeners.add(fn), removeEventListener: (_: string, fn: () => void) => listeners.delete(fn) };
  vi.stubGlobal('matchMedia', () => media);
  return (value: boolean) => { media.matches = value; listeners.forEach(fn => fn()); };
}
describe('shared presentation theme', () => {
  it('follows the system on first visit and exposes the selected state', () => {
    system(true); render(<ThemeSwitch />);
    expect(screen.getByRole('button', { name: 'Тёмная тема', pressed: true })).toBeInTheDocument();
    expect(document.documentElement.dataset.theme).toBe('dark');
  });
  it('uses saved explicit preference before the system preference', () => {
    localStorage.setItem('fk-theme', 'light'); system(true); render(<ThemeSwitch />);
    expect(screen.getByRole('button', { name: 'Светлая тема', pressed: true })).toBeInTheDocument();
  });
  it('switches both directions without remounting or losing an entered form value', () => {
    system(false); render(<><ThemeSwitch /><input aria-label="Черновик" defaultValue="Несохранённое решение" /></>);
    const draft = screen.getByLabelText('Черновик');
    fireEvent.click(screen.getByRole('button', { name: 'Тёмная тема' }));
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(localStorage.getItem('fk-theme')).toBe('dark');
    expect(screen.getByLabelText('Черновик')).toBe(draft);
    expect(draft).toHaveValue('Несохранённое решение');
    fireEvent.click(screen.getByRole('button', { name: 'Светлая тема' }));
    expect(document.documentElement.dataset.theme).toBe('light');
  });
  it('restores the selected preference when the shared control remounts', () => {
    system(false); const view = render(<ThemeSwitch />);
    fireEvent.click(screen.getByRole('button', { name: 'Тёмная тема' })); view.unmount();
    render(<ThemeSwitch />);
    expect(screen.getByRole('button', { name: 'Тёмная тема', pressed: true })).toBeInTheDocument();
  });
  it('ignores invalid saved values and supports a blocked browser store for the session', () => {
    system(false);
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked'); });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked'); });
    const view = render(<ThemeSwitch />);
    fireEvent.click(screen.getByRole('button', { name: 'Тёмная тема' })); view.unmount();
    render(<ThemeSwitch />);
    expect(screen.getByRole('button', { name: 'Тёмная тема', pressed: true })).toBeInTheDocument();
  });
  it('rejects invalid stored theme values', () => {
    system(false); localStorage.setItem('fk-theme', '<script>dark</script>'); render(<ThemeSwitch />);
    expect(document.documentElement.dataset.theme).toBe('light');
  });
});

import { afterEach, expect, it } from 'vitest';
import { readLocation, writeLocation } from './navigation';
afterEach(() => window.history.replaceState(null, '', '/'));
it('restores the page and current conflict IDs after refresh without storing business values', () => {
  const id = '6e75c000-0ffe-48aa-a313-3fc6f73fae26';
  writeLocation({ page: 'conflicts', matching: id, conflict: id, decision: '' });
  expect(readLocation()).toEqual({ page: 'conflicts', matching: id, conflict: id, decision: '' });
});
it('ignores unknown pages and malformed identifiers in untrusted URL state', () => {
  window.history.replaceState(null, '', '#<script>?conflict=other&decision=../../secrets');
  expect(readLocation()).toEqual({ page: 'dashboard', matching: '', conflict: '', decision: '' });
});

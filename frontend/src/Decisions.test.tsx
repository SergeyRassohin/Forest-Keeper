import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { Decisions } from './Decisions';
import type { Decision } from './decisionTypes';
const row: Decision = { id: 'decision-1', conflict_id: 'case', entity_id: 'entity', business_key: 'MAT-1', attribute_code: 'mass', domain: 'materials', decision_type: 'ENTER_VALUE', status: 'ACTIVE', selected_value: '13.25', unit: 'kg', selected_source_id: null, reason: '<script>literal</script>', user_id: 'actor', actor_display_name: 'Эксперт', actor_roles: ['DATA_OWNER'], decided_at: '2026-10-23T00:00:00Z', supersedes_decision_id: 'old-decision', superseded_by: null, context_snapshot: { evidence: 'historical' } };
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const expired = vi.fn();
it('shows immutable history author, explanation and predecessor without executing hostile text', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (path) => new Response(JSON.stringify(String(path).endsWith('/decisions/decision-1') ? row : [row])));
  render(<Decisions onSessionExpired={expired} initialId="decision-1" />);
  const history = await screen.findByRole('region', { name: 'История решений' });
  expect(history).toHaveTextContent('Эксперт'); expect(history).toHaveTextContent('old-decision'); expect(history).toHaveTextContent('<script>literal</script>');
  expect(document.querySelector('script')).toBeNull();
  expect(screen.queryByRole('button', { name: /Удалить|Редактировать/ })).not.toBeInTheDocument();
});
it('clears a card when changing filters so a prior decision cannot masquerade as a new selection', async () => {
  const mock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (path) => new Response(JSON.stringify(String(path).endsWith('/decisions/decision-1') ? row : [row])));
  render(<Decisions onSessionExpired={expired} initialId="decision-1" />);
  await screen.findByRole('article', { name: 'Карточка решения' });
  fireEvent.change(screen.getByLabelText('Результат решения'), { target: { value: 'DEFERRED' } });
  expect(screen.queryByRole('article', { name: 'Карточка решения' })).not.toBeInTheDocument();
  await vi.waitFor(() => expect(mock).toHaveBeenCalledWith(expect.stringContaining('decision_type=DEFERRED'), expect.anything()));
});
it('drops the old card when reading a different historical decision is denied', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (path) => {
    const url = String(path);
    if (url.endsWith('/decisions/old-decision')) return new Response(JSON.stringify({ error: { message: 'Недоступно' } }), { status: 404 });
    return new Response(JSON.stringify(url.endsWith('/decisions/decision-1') ? row : url.includes('/conflicts/') ? [{ ...row, id: 'old-decision' }] : [row]));
  });
  render(<Decisions onSessionExpired={expired} initialId="decision-1" />);
  fireEvent.click(await screen.findByRole('button', { name: 'Историческое решение old-decision' }));
  await screen.findByRole('alert'); expect(screen.queryByRole('article', { name: 'Карточка решения' })).not.toBeInTheDocument();
});

// URL contains identifiers only. Authentication and data scope always come from the server.
const pages = new Set(['dashboard', 'imports', 'matching', 'conflicts', 'decisions', 'users']);
const identifier = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;
export type Location = { page: string; matching: string; conflict: string; decision: string };
export function readLocation(): Location {
  const fragment = window.location.hash.slice(1, 512);
  const [page, query] = fragment.split('?', 2);
  const params = new URLSearchParams(query);
  const valid = (key: string) => { const value = params.get(key) ?? ''; return identifier.test(value) ? value : ''; };
  return { page: pages.has(page) ? page : 'dashboard', matching: valid('matching'), conflict: valid('conflict'), decision: valid('decision') };
}
export function writeLocation(route: Location) {
  const params = new URLSearchParams();
  for (const [key, value] of [['matching', route.matching], ['conflict', route.conflict], ['decision', route.decision]]) {
    if (identifier.test(value)) params.set(key, value);
  }
  const fragment = '#' + route.page + (params.size ? '?' + params.toString() : '');
  window.history.replaceState(null, '', fragment);
}

export interface Route {
  path: string;
  method: 'GET' | 'POST';
}

export function routes(): Route[] {
  return [{ path: '/entities', method: 'GET' }];
}

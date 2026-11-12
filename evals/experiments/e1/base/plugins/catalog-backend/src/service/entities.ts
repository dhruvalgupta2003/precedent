import { ResponseError } from '@backstage/errors';

export async function fetchEntities(baseUrl: string): Promise<unknown[]> {
  const response = await fetch(`${baseUrl}/entities`);
  if (!response.ok) {
    throw await ResponseError.fromResponse(response);
  }
  return response.json();
}

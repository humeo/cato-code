export interface Config {
  apiUrl: string;
  timeout: number;
}

export function createConfig(url: string): Config {
  return { apiUrl: url, timeout: 5000 };
}

export function formatUrl(base: string, path: string): string {
  return `${base}/${path}`;
}

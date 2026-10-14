export interface RunbookHit {
  runbookId: string;
  title: string;
  section: string;
  snippet: string;
  score: number;
  faultType: string;
}

export interface RunbookSearchResponse {
  query: string;
  mode: 'vector' | 'bm25' | 'hybrid';
  embedder: string;
  results: RunbookHit[];
}

export interface RunbookDoc {
  id: string;
  title: string;
  faultType: string;
  tags: string[];
  markdown: string;
}

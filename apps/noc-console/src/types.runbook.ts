export interface RunbookHit {
  runbookId: string;
  title: string;
  section: string;
  snippet: string;
  score: number;
  faultType: string;
  /** Step 15 Graph RAG: topology nodes (sites / links / cells) behind this hit. */
  nodeIds?: string[];
  matchedFacets?: string[];
}

export interface GraphContext {
  entities: { id: string; type: string; mention: string; via: string }[];
  nodes: string[];
  facets: string[];
  summary: string;
  source: string;
  plan?: { query: string; params: Record<string, string>; planner: string } | null;
  reranker: string;
  elapsedMs: number;
}

export interface RunbookSearchResponse {
  query: string;
  mode: 'vector' | 'bm25' | 'hybrid' | 'rerank' | 'graph';
  embedder: string;
  results: RunbookHit[];
  graph?: GraphContext | null;
}

export interface RunbookDoc {
  id: string;
  title: string;
  faultType: string;
  tags: string[];
  markdown: string;
}

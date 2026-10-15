export function buildRunbookQuery(
  alarm: {
    siteId?: string | null;
    specificProblem?: string | null;
    probableCause?: string | null;
    alarmType?: string | null;
    enrichment?: {
      nodeTypes?: string[];
      siteKind?: string | null;
    };
  },
  faultType?: string | null,
): string {
  const parts: string[] = [];

  // Step 15: the site id is the entity Graph RAG links to the topology
  if (alarm.siteId) {
    parts.push(alarm.siteId);
  }

  if (alarm.specificProblem) {
    parts.push(alarm.specificProblem);
  }

  if (alarm.probableCause) {
    parts.push(splitCamelCase(alarm.probableCause));
  }

  if (alarm.alarmType) {
    parts.push(splitCamelCase(alarm.alarmType));
  }

  if (faultType) {
    parts.push(faultType.replace(/_/g, ' '));
  }

  if (alarm.enrichment?.nodeTypes?.length) {
    parts.push(alarm.enrichment.nodeTypes.join(' '));
  }

  if (alarm.enrichment?.siteKind) {
    parts.push(alarm.enrichment.siteKind);
  }

  const query = parts.join(' ').replace(/\s+/g, ' ').trim();
  return query.slice(0, 300);
}

function splitCamelCase(str: string): string {
  return str
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2')
    .toLowerCase();
}

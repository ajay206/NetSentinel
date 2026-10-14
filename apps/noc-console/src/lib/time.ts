const istFormatter = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Asia/Kolkata',
  year: 'numeric',
  month: 'short',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
});

export const IST_LABEL = 'IST';

export function formatIST(
  iso: string | Date,
  opts?: { date?: boolean }
): string {
  const date = typeof iso === 'string' ? new Date(iso) : iso;
  if (isNaN(date.getTime())) {
    return '—';
  }
  const parts = istFormatter.formatToParts(date);
  const timePart = `${parts.find(p => p.type === 'hour')?.value}:${parts.find(p => p.type === 'minute')?.value}:${parts.find(p => p.type === 'second')?.value} ${IST_LABEL}`;
  if (opts?.date === false) {
    return timePart;
  }
  const day = parts.find(p => p.type === 'day')?.value;
  const month = parts.find(p => p.type === 'month')?.value;
  const year = parts.find(p => p.type === 'year')?.value;
  return `${day} ${month} ${year}, ${timePart}`;
}

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { RunbooksPanel } from './RunbooksPanel';
import { MarkdownPreview } from '../components/MarkdownPreview';
import type { RunbookHit, RunbookDoc } from '../types.runbook';

const mockHits: RunbookHit[] = [
  {
    runbookId: 'rb-001',
    title: 'Link Failure Recovery',
    section: 'Troubleshooting',
    snippet: 'Check physical connections and verify SFP modules are seated correctly.',
    score: 0.9234,
    faultType: 'link_failure',
  },
  {
    runbookId: 'rb-002',
    title: 'Power Supply Replacement',
    section: 'Hardware',
    snippet: 'Replace failed PSU module following hot-swap procedure.',
    score: 0.8765,
    faultType: 'power_failure',
  },
  {
    runbookId: 'rb-003',
    title: 'BGP Session Reset',
    section: 'Routing',
    snippet: 'Clear BGP sessions and verify route advertisement.',
    score: 0.8123,
    faultType: 'bgp_issue',
  },
];

const mockDoc: RunbookDoc = {
  id: 'rb-001',
  title: 'Link Failure Recovery',
  faultType: 'link_failure',
  tags: ['layer1', 'troubleshooting'],
  markdown: '# Overview\n## Steps\n> Check cables\n- Step 1\n- Step 2\n\nParagraph text.',
};

describe('RunbooksPanel', () => {
  it('renders empty state when no alarmLabel', () => {
    render(<RunbooksPanel alarmLabel={null} />);
    expect(screen.getByText('Click an enriched alarm to see runbooks.')).toBeInTheDocument();
  });

  it('renders loading state', () => {
    render(<RunbooksPanel alarmLabel="Test Alarm" isLoading={true} />);
    expect(screen.getByText('Searching runbooks…')).toBeInTheDocument();
  });

  it('renders error state', () => {
    render(<RunbooksPanel alarmLabel="Test Alarm" isError={true} />);
    expect(screen.getByText('rag-service unavailable')).toBeInTheDocument();
  });

  it('renders empty hits state', () => {
    render(<RunbooksPanel alarmLabel="Test Alarm" hits={[]} />);
    expect(screen.getByText('No matching runbooks')).toBeInTheDocument();
  });

  it('renders up to 3 hits with scores and calls onSelect on click', () => {
    const onSelect = vi.fn();
    render(<RunbooksPanel alarmLabel="Test Alarm" hits={mockHits} onSelect={onSelect} />);

    const buttons = screen.getAllByTestId('runbook-hit');
    expect(buttons).toHaveLength(3);

    expect(screen.getByText('Link Failure Recovery')).toBeInTheDocument();
    expect(screen.getByText('rb-001')).toBeInTheDocument();
    expect(screen.getByText('0.923')).toBeInTheDocument();
    expect(screen.getByText('link failure')).toBeInTheDocument();

    fireEvent.click(buttons[0]);
    expect(onSelect).toHaveBeenCalledWith('rb-001');
  });

  it('renders preview with markdown and close calls onClosePreview', () => {
    const onClosePreview = vi.fn();
    render(
      <RunbooksPanel
        alarmLabel="Test Alarm"
        hits={mockHits}
        selectedId="rb-001"
        doc={mockDoc}
        docLoading={false}
        onClosePreview={onClosePreview}
      />
    );

    expect(screen.getByRole('heading', { name: 'Link Failure Recovery' })).toBeInTheDocument();
    expect(screen.getByText('Overview')).toBeInTheDocument();
    expect(screen.getByText('Steps')).toBeInTheDocument();
    expect(screen.getByText('Check cables')).toBeInTheDocument();
    expect(screen.getByText('Step 1')).toBeInTheDocument();
    expect(screen.getByText('Step 2')).toBeInTheDocument();
    expect(screen.getByText('Paragraph text.')).toBeInTheDocument();

    const closeButton = screen.getByLabelText('Close preview');
    fireEvent.click(closeButton);
    expect(onClosePreview).toHaveBeenCalled();
  });

  it('shows loading in preview when docLoading', () => {
    render(
      <RunbooksPanel
        alarmLabel="Test Alarm"
        hits={mockHits}
        selectedId="rb-001"
        doc={mockDoc}
        docLoading={true}
      />
    );
    expect(screen.getByText('Loading runbook…')).toBeInTheDocument();
  });
});

describe('MarkdownPreview', () => {
  it('does not render raw HTML - script tag appears as text', () => {
    const maliciousMarkdown = '# Title\n<script>alert("xss")</script>\n- Item';
    render(<MarkdownPreview markdown={maliciousMarkdown} />);

    expect(screen.getByText('<script>alert("xss")</script>')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(document.querySelector('script')).toBeNull();
  });

  it('renders headings, blockquotes, lists, and paragraphs', () => {
    const markdown = '# Heading 3\n## Heading 4\n> Quote\n- Item 1\n- Item 2\n\nParagraph text.';
    render(<MarkdownPreview markdown={markdown} />);

    expect(screen.getByText('Heading 3')).toBeInTheDocument();
    expect(screen.getByText('Heading 4')).toBeInTheDocument();
    expect(screen.getByText('Quote')).toBeInTheDocument();
    expect(screen.getByText('Item 1')).toBeInTheDocument();
    expect(screen.getByText('Item 2')).toBeInTheDocument();
    expect(screen.getByText('Paragraph text.')).toBeInTheDocument();
  });
});

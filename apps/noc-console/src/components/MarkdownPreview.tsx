import React from 'react';

interface MarkdownPreviewProps {
  markdown: string;
}

export const MarkdownPreview: React.FC<MarkdownPreviewProps> = ({ markdown }) => {
  const lines = markdown.split('\n');
  const elements: React.ReactNode[] = [];
  let currentParagraph: string[] = [];
  let inList = false;
  let listItems: string[] = [];

  const flushParagraph = () => {
    if (currentParagraph.length > 0) {
      elements.push(
        <p key={`p-${elements.length}`} className="text-slate-600 whitespace-pre-wrap">
          {currentParagraph.join('\n')}
        </p>
      );
      currentParagraph = [];
    }
  };

  const flushList = () => {
    if (listItems.length > 0) {
      elements.push(
        <ul key={`ul-${elements.length}`} className="list-disc list-inside text-slate-600 space-y-1 ml-4">
          {listItems.map((item, idx) => (
            <li key={`li-${idx}`}>{item}</li>
          ))}
        </ul>
      );
      listItems = [];
      inList = false;
    }
  };

  for (const line of lines) {
    const trimmed = line.trimStart();

    if (trimmed.startsWith('# ')) {
      flushParagraph();
      flushList();
      elements.push(
        <h3 key={`h3-${elements.length}`} className="text-lg font-semibold text-navy mt-4 mb-2">
          {trimmed.slice(2)}
        </h3>
      );
    } else if (trimmed.startsWith('## ')) {
      flushParagraph();
      flushList();
      elements.push(
        <h4 key={`h4-${elements.length}`} className="text-base font-semibold text-navy mt-3 mb-1">
          {trimmed.slice(3)}
        </h4>
      );
    } else if (trimmed.startsWith('> ')) {
      flushParagraph();
      flushList();
      elements.push(
        <blockquote key={`bq-${elements.length}`} className="border-l-4 border-bento-border pl-4 italic text-bento-muted my-2">
          {trimmed.slice(2)}
        </blockquote>
      );
    } else if (trimmed.startsWith('- ')) {
      flushParagraph();
      inList = true;
      listItems.push(trimmed.slice(2));
    } else if (trimmed === '') {
      flushParagraph();
      flushList();
    } else {
      if (inList) {
        flushList();
      }
      currentParagraph.push(line);
    }
  }

  flushParagraph();
  flushList();

  return (
    <div data-testid="markdown-preview" className="prose prose-invert max-w-none">
      {elements}
    </div>
  );
};

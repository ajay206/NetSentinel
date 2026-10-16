import React from 'react';
import { InfoIcon } from './Tooltip';
import { card, severityChip, severityHex, severityLabel } from '../../theme';

type CardProps = {
  title: string;
  subtitle?: string;
  info?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  testId?: string;
};

export const Card: React.FC<CardProps> = ({
  title,
  subtitle,
  info,
  actions,
  children,
  className = '',
  testId,
}) => (
  <section className={`${card} flex flex-col h-full min-h-0 ${className}`} data-testid={testId}>
    <header className="mb-1 flex items-start justify-between gap-3 border-b border-bento-border/80 pb-2">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <h2 className="text-[15px] font-extrabold font-display text-navy tracking-tight">{title}</h2>
          {info && <InfoTip text={info} label={title} />}
        </div>
        {subtitle && <p className="text-xs text-bento-muted mt-0.5">{subtitle}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-1.5">{actions}</div>}
    </header>
    {/* flex column + min-h-0 so an inner .ns-scroll can shrink and scroll instead of spilling */}
    <div className="flex flex-1 min-h-0 flex-col overflow-hidden pt-1">{children}</div>
  </section>
);

type InfoTipProps = {
  text: React.ReactNode;
  label?: string;
};

/** The (i) next to a panel title; see ./Tooltip for the accessible behaviour. */
export const InfoTip: React.FC<InfoTipProps> = ({ text, label }) => (
  <InfoIcon text={text} label={label} />
);

type StateMessageProps = {
  kind: 'loading' | 'empty' | 'error';
  children: React.ReactNode;
};

export const StateMessage: React.FC<StateMessageProps> = ({ kind, children }) => {
  const base = 'flex flex-col items-center justify-center min-h-[8rem] text-sm text-bento-muted font-medium';
  let content: React.ReactNode;

  if (kind === 'loading') {
    content = (
      <>
        <div className="animate-spin border-2 border-slate-300 border-t-navy rounded-full w-4 h-4 mb-2" />
        {children}
      </>
    );
  } else if (kind === 'error') {
    content = (
      <>
        <div className="text-red-500 mb-2 font-bold">❗</div>
        {children}
      </>
    );
  } else {
    content = <>{children}</>;
  }

  return (
    <div className={base} data-testid={`state-${kind}`}>
      {content}
    </div>
  );
};

type SeverityChipProps = {
  severity: string;
};

export const SeverityChip: React.FC<SeverityChipProps> = ({ severity }) => {
  const chipClass = severityChip[severity] ?? severityChip.indeterminate;
  const dotColor = (severityHex as Record<string, string>)[severity] ?? '#6B7280';
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-extrabold uppercase tracking-wider ${chipClass}`}
    >
      <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ backgroundColor: dotColor }} />
      {severityLabel(severity)}
    </span>
  );
};

type CardHeaderProps = {
  title: React.ReactNode;
  subtitle?: string;
  info?: React.ReactNode;
  actions?: React.ReactNode;
  as?: 'h2' | 'h3';
};

/** Header row for panels that keep their own body markup: same look as <Card>'s header. */
export const CardHeader: React.FC<CardHeaderProps> = ({
  title,
  subtitle,
  info,
  actions,
  as: Tag = 'h2',
}) => (
  <div className="mb-2 flex items-start justify-between gap-3 border-b border-bento-border/80 pb-2">
    <div className="min-w-0">
      <div className="flex items-center gap-2">
        <Tag className="text-[15px] font-extrabold font-display text-navy tracking-tight">{title}</Tag>
        {info && <InfoTip text={info} label={typeof title === 'string' ? title : undefined} />}
      </div>
      {subtitle && <p className="mt-0.5 text-xs text-bento-muted">{subtitle}</p>}
    </div>
    {actions && <div className="flex shrink-0 flex-wrap items-center gap-1.5">{actions}</div>}
  </div>
);

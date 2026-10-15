import React, {
  cloneElement,
  isValidElement,
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';
import { createPortal } from 'react-dom';

/**
 * UI polish: the one accessible tooltip for the console.
 *
 * - Opens on hover and on keyboard focus; Escape or blur closes it.
 * - The trigger gets `aria-describedby` pointing at the `role="tooltip"` node, so screen
 *   readers announce the copy. Non-focusable triggers (text, chips) get `tabIndex=0`.
 * - Rendered in a portal with fixed positioning, so scroll containers and table cells never
 *   clip it; it flips below when there is no room above and is clamped to the viewport.
 */
export type TooltipProps = {
  content: React.ReactNode;
  children: React.ReactElement;
  side?: 'top' | 'bottom';
  /** ms before showing on hover (focus shows immediately) */
  delay?: number;
};

const FOCUSABLE = new Set(['button', 'a', 'input', 'select', 'textarea', 'summary']);
const GAP = 8;
const MARGIN = 8;

export function Tooltip({ content, children, side = 'top', delay = 150 }: TooltipProps) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{
    top: number;
    left: number;
    side: 'top' | 'bottom';
  } | null>(null);
  const triggerRef = useRef<HTMLElement | null>(null);
  const tipRef = useRef<HTMLDivElement | null>(null);
  const timer = useRef<number | undefined>(undefined);

  const show = useCallback(
    (immediate: boolean) => {
      window.clearTimeout(timer.current);
      if (immediate || delay <= 0) setOpen(true);
      else timer.current = window.setTimeout(() => setOpen(true), delay);
    },
    [delay],
  );
  const hide = useCallback(() => {
    window.clearTimeout(timer.current);
    setOpen(false);
  }, []);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && hide();
    const onScroll = () => hide();
    document.addEventListener('keydown', onKey);
    window.addEventListener('scroll', onScroll, true);
    return () => {
      document.removeEventListener('keydown', onKey);
      window.removeEventListener('scroll', onScroll, true);
    };
  }, [open, hide]);

  useLayoutEffect(() => {
    if (!open || !triggerRef.current) return;
    const t = triggerRef.current.getBoundingClientRect();
    const tip = tipRef.current?.getBoundingClientRect();
    const w = tip?.width ?? 0;
    const h = tip?.height ?? 0;
    const vw = window.innerWidth || document.documentElement.clientWidth;
    let s: 'top' | 'bottom' = side;
    if (s === 'top' && t.top - h - GAP < MARGIN) s = 'bottom';
    const top = s === 'top' ? t.top - h - GAP : t.bottom + GAP;
    const left = Math.min(
      Math.max(t.left + t.width / 2 - w / 2, MARGIN),
      Math.max(MARGIN, vw - w - MARGIN),
    );
    setPos({ top, left, side: s });
  }, [open, side, content]);

  if (!isValidElement(children)) return children;
  const child = children as React.ReactElement<Record<string, unknown>>;
  const tag = typeof child.type === 'string' ? child.type : '';
  const needsTab = !FOCUSABLE.has(tag) && child.props.tabIndex === undefined;
  const call = (name: string, e: unknown) => {
    const fn = child.props[name];
    if (typeof fn === 'function') fn(e);
  };

  const trigger = cloneElement(child, {
    ref: (node: HTMLElement | null) => {
      triggerRef.current = node;
    },
    'aria-describedby': [child.props['aria-describedby'], id].filter(Boolean).join(' '),
    ...(needsTab ? { tabIndex: 0 } : {}),
    onMouseEnter: (e: unknown) => {
      call('onMouseEnter', e);
      show(false);
    },
    onMouseLeave: (e: unknown) => {
      call('onMouseLeave', e);
      hide();
    },
    onFocus: (e: unknown) => {
      call('onFocus', e);
      show(true);
    },
    onBlur: (e: unknown) => {
      call('onBlur', e);
      hide();
    },
  });

  const tip = (
    <div
      ref={tipRef}
      id={id}
      role="tooltip"
      hidden={!open}
      data-side={pos?.side ?? side}
      style={{
        position: 'fixed',
        top: pos?.top ?? -9999,
        left: pos?.left ?? -9999,
      }}
      className="pointer-events-none z-[100] max-w-xs whitespace-normal rounded-md border border-slate-700 bg-slate-800 px-2.5 py-1.5 text-left text-xs font-normal normal-case leading-snug tracking-normal text-slate-100 shadow-lg"
    >
      {content}
    </div>
  );

  return (
    <>
      {trigger}
      {typeof document !== 'undefined' ? createPortal(tip, document.body) : tip}
    </>
  );
}

/** A text label with a tooltip (column headers, KPI labels): dotted underline, help cursor. */
export function Tip({
  tip,
  children,
  className = '',
  side,
}: {
  tip: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  side?: 'top' | 'bottom';
}) {
  return (
    <Tooltip content={tip} side={side}>
      <span
        className={`cursor-help underline decoration-slate-600 decoration-dotted underline-offset-4 outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ${className}`}
      >
        {children}
      </span>
    </Tooltip>
  );
}

/** The (i) icon next to panel titles. */
export function InfoIcon({ text, label }: { text: React.ReactNode; label?: string }) {
  return (
    <Tooltip content={text} side="bottom">
      <button
        type="button"
        aria-label={label ? `About ${label}` : 'More info'}
        data-testid="info-tip"
        className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-slate-600 text-[10px] font-semibold leading-none text-slate-400 hover:border-sky-500 hover:text-sky-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
      >
        i
      </button>
    </Tooltip>
  );
}

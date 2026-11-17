import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState, type PointerEvent as RPointerEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import type { Ruleset } from "../api/types";
import { entryText, glossaryEntry, splitTerms, type GlossaryEntry } from "../rules/glossary";

/** Which rules the surrounding character or game uses (some terms read differently in 2024). */
export const RulesetContext = createContext<Ruleset | undefined>(undefined);

type Placement = "below" | "side";

/**
 * Hover (mouse) or tap (touch) popover anchored to an element, rendered in a portal so it
 * isn't clipped by scrolling panels. It stays open while the pointer is over the popover,
 * so terms inside it can be hovered too.
 */
export function useHoverPop<T extends HTMLElement>({ openDelay = 120, placement = "below" as Placement } = {}) {
  const anchor = useRef<T | null>(null);
  const [open, setOpen] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  const lastPointer = useRef<string>("mouse");

  const clear = () => window.clearTimeout(timer.current);
  const show = useCallback(
    (delay = openDelay) => {
      clear();
      timer.current = window.setTimeout(() => setOpen(true), delay);
    },
    [openDelay],
  );
  const hide = useCallback((delay = 140) => {
    clear();
    timer.current = window.setTimeout(() => setOpen(false), delay);
  }, []);
  useEffect(() => clear, []);

  // Close on outside tap, Escape, or when the page scrolls the anchor away.
  useEffect(() => {
    if (!open) return;
    const down = (e: PointerEvent) => {
      const t = e.target as Node;
      if (anchor.current?.contains(t) || (t instanceof Element && t.closest(".rules-pop"))) return;
      setOpen(false);
    };
    const key = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    const scroll = (e: Event) => {
      if (e.target instanceof Element && e.target.closest(".rules-pop")) return;
      setOpen(false);
    };
    document.addEventListener("pointerdown", down, true);
    document.addEventListener("keydown", key);
    window.addEventListener("scroll", scroll, true);
    return () => {
      document.removeEventListener("pointerdown", down, true);
      document.removeEventListener("keydown", key);
      window.removeEventListener("scroll", scroll, true);
    };
  }, [open]);

  const anchorProps = {
    ref: (el: T | null) => {
      anchor.current = el;
    },
    onPointerDown: (e: RPointerEvent) => {
      lastPointer.current = e.pointerType;
    },
    onPointerEnter: (e: RPointerEvent) => {
      if (e.pointerType === "mouse") show();
    },
    onPointerLeave: (e: RPointerEvent) => {
      if (e.pointerType === "mouse") hide();
    },
  };

  const popProps = {
    onPointerEnter: () => clear(),
    onPointerLeave: (e: RPointerEvent) => {
      if (e.pointerType === "mouse") hide();
    },
  };

  const render = (content: ReactNode, className = "") =>
    open && anchor.current ? (
      <PopLayer anchor={anchor.current} placement={placement} className={className} {...popProps}>
        {content}
      </PopLayer>
    ) : null;

  return { open, setOpen, show, hide, anchorProps, render, wasTouch: () => lastPointer.current !== "mouse" };
}

function PopLayer({
  anchor,
  placement,
  className,
  children,
  onPointerEnter,
  onPointerLeave,
}: {
  anchor: HTMLElement;
  placement: Placement;
  className: string;
  children: ReactNode;
  onPointerEnter: () => void;
  onPointerLeave: (e: RPointerEvent) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const a = anchor.getBoundingClientRect();
    const w = el.offsetWidth;
    const h = el.offsetHeight;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const pad = 8;
    let left: number;
    let top: number;
    if (placement === "side" && vw > 640) {
      left = a.right + 8 + w <= vw - pad ? a.right + 8 : a.left - 8 - w;
      top = a.top;
    } else {
      left = a.left + a.width / 2 - w / 2;
      top = a.bottom + 6 + h <= vh - pad ? a.bottom + 6 : a.top - 6 - h;
    }
    left = Math.max(pad, Math.min(left, vw - pad - w));
    top = Math.max(pad, Math.min(top, vh - pad - h));
    setPos({ left, top });
  }, [anchor, placement]);

  return createPortal(
    <div
      ref={ref}
      className={`rules-pop ${className}`}
      role="tooltip"
      style={{ left: pos?.left ?? -9999, top: pos?.top ?? -9999, visibility: pos ? "visible" : "hidden" }}
      onPointerEnter={onPointerEnter}
      onPointerLeave={onPointerLeave}
      onClick={(e) => e.stopPropagation()}
    >
      {children}
    </div>,
    document.body,
  );
}

/** A rules keyword with a dotted underline; hover (or tap) explains it. */
export function Term({ entry, k, children }: { entry?: GlossaryEntry; k?: string; children: ReactNode }) {
  const ruleset = useContext(RulesetContext);
  const e = entry ?? (k ? glossaryEntry(k) : undefined);
  const pop = useHoverPop<HTMLSpanElement>();
  if (!e) return <>{children}</>;
  return (
    <>
      <span
        {...pop.anchorProps}
        className="rules-term"
        tabIndex={0}
        onFocus={() => pop.show(0)}
        onBlur={() => pop.hide()}
        onClick={(ev) => {
          // A tap shows the explanation instead of also selecting the card it sits in;
          // a mouse click goes through (the explanation is already showing on hover).
          if (!pop.wasTouch()) return;
          ev.stopPropagation();
          ev.preventDefault();
          pop.setOpen(!pop.open);
        }}
      >
        {children}
      </span>
      {pop.render(
        <>
          <div className="rules-pop-title">{e.title}</div>
          <div>{entryText(e, ruleset)}</div>
        </>,
      )}
    </>
  );
}

/** Any inline element that explains itself on hover (or tap): a feature chip, a spell name. */
export function HoverInfo({ className = "", info, wide, children }: { className?: string; info: ReactNode; wide?: boolean; children: ReactNode }) {
  const pop = useHoverPop<HTMLSpanElement>({ openDelay: 200 });
  return (
    <>
      <span
        {...pop.anchorProps}
        className={`hover-info ${className}`}
        tabIndex={0}
        onFocus={() => pop.show(0)}
        onBlur={() => pop.hide()}
        onClick={() => pop.wasTouch() && pop.setOpen(!pop.open)}
      >
        {children}
      </span>
      {pop.render(info, wide ? "wide" : "")}
    </>
  );
}

/** Rules text with every known keyword (first mention each) turned into a hover explanation. */
export function RulesText({ text, skip }: { text: string | null | undefined; skip?: string[] }) {
  if (!text) return null;
  const pieces = splitTerms(text, skip ? new Set(skip) : undefined);
  return (
    <>
      {pieces.map((p, i) =>
        typeof p === "string" ? (
          p
        ) : (
          <Term key={i} entry={p.entry}>
            {p.text}
          </Term>
        ),
      )}
    </>
  );
}

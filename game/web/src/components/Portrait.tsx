import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { CharacterView } from "../api/types";
import { initials } from "../util/format";

/** Class emblem glyphs (24×24, stroked). */
const GLYPH: Record<string, string> = {
  sword: "M12 2 L14 5 L14 15 L10 15 L10 5 Z M7 15 L17 15 M12 15 L12 20 M10.5 21 L13.5 21",
  shield: "M12 2 L20 5 L19 13 C18 17 15 20 12 22 C9 20 6 17 5 13 L4 5 Z M12 6 L12 18 M8 10 L16 10",
  staff: "M7 22 L15 6 M15 6 m-3 -2 a3 3 0 1 0 6 0 a3 3 0 1 0 -6 0 M14 2 L14 1",
  leaf: "M5 19 C5 9 11 4 20 4 C20 13 15 19 5 19 Z M5 19 L14 10",
  fist: "M7 10 L7 6 C7 5 9 5 9 6 L9 9 M9 9 L9 5 C9 4 11 4 11 5 L11 9 M11 9 L11 5 C11 4 13 4 13 5 L13 9 M13 9 L13 6 C13 5 15 5 15 6 L15 12 C15 16 13 19 10 19 C7 19 6 16 6 13 L6 11 C6 10 7 10 7 10",
  bow: "M6 3 C16 6 16 18 6 21 M6 3 L6 21 M3 12 L19 12 M19 12 L16 10 M19 12 L16 14",
  dagger: "M12 2 L13.5 6 L13.5 14 L10.5 14 L10.5 6 Z M8 14 L16 14 M12 14 L12 19 M11 21 L13 21",
  flame: "M12 22 C7 22 5 18 6 14 C7 11 9 10 9 7 C11 9 12 10 12 12 C13 10 14 7 13 3 C17 6 19 10 18 15 C17 19 15 22 12 22 Z",
  eye: "M2 12 C6 6 18 6 22 12 C18 18 6 18 2 12 Z M12 12 m-3 0 a3 3 0 1 0 6 0 a3 3 0 1 0 -6 0",
  book: "M4 5 C7 4 10 4 12 6 C14 4 17 4 20 5 L20 19 C17 18 14 18 12 20 C10 18 7 18 4 19 Z M12 6 L12 20",
  lute: "M10 14 m-5 0 a5 5 0 1 0 10 0 a5 5 0 1 0 -10 0 M13 10 L20 3 M18 2 L21 5 M8 14 L12 14",
  sun: "M12 12 m-4 0 a4 4 0 1 0 8 0 a4 4 0 1 0 -8 0 M12 2 L12 5 M12 19 L12 22 M2 12 L5 12 M19 12 L22 12 M5 5 L7 7 M17 17 L19 19 M19 5 L17 7 M7 17 L5 19",
  axe: "M12 3 L12 22 M12 4 C17 4 20 7 20 11 C17 11 14 10 12 8 M12 4 C7 4 4 7 4 11 C7 11 10 10 12 8",
};

const CLASS_GLYPH: Record<string, string> = {
  fighter: "sword",
  paladin: "shield",
  barbarian: "axe",
  druid: "leaf",
  monk: "fist",
  ranger: "bow",
  rogue: "dagger",
  sorcerer: "flame",
  warlock: "eye",
  wizard: "book",
  bard: "lute",
  cleric: "sun",
  artificer: "staff",
};

export function glyphFor(cls?: string): string {
  const k = (cls || "").toLowerCase().split(/[\s/]+/)[0];
  return GLYPH[CLASS_GLYPH[k] ?? "staff"];
}

/** Generated crest: class emblem on the character's colour, with initials. */
export function Crest({ name, cls, color, size = 40 }: { name: string; cls?: string; color?: string; size?: number }) {
  const fill = color || "#6b5a3a";
  return (
    <svg className="crest" width={size} height={size} viewBox="0 0 40 40" aria-hidden>
      <defs>
        <radialGradient id={`cg-${fill.replace(/[^a-z0-9]/gi, "")}`} cx="35%" cy="30%" r="80%">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.28" />
          <stop offset="100%" stopColor="#000000" stopOpacity="0.25" />
        </radialGradient>
      </defs>
      <circle cx="20" cy="20" r="20" fill={fill} />
      <circle cx="20" cy="20" r="20" fill={`url(#cg-${fill.replace(/[^a-z0-9]/gi, "")})`} />
      <circle cx="20" cy="20" r="17.5" fill="none" stroke="rgba(255,240,210,0.45)" strokeWidth="1" />
      <g transform="translate(9 4) scale(0.92)" fill="none" stroke="rgba(255,248,230,0.92)" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        <path d={glyphFor(cls)} />
      </g>
      <text x="20" y="34.5" textAnchor="middle" fontSize="8" fontWeight="800" fill="#fff" stroke="rgba(0,0,0,0.45)" strokeWidth="0.6" paintOrder="stroke" letterSpacing="0.5">
        {initials(name)}
      </text>
    </svg>
  );
}

type Size = "tiny" | "small" | "" | "big" | "huge";
const PX: Record<Size, number> = { tiny: 22, small: 32, "": 44, big: 72, huge: 112 };

/** A character's portrait image, or its generated crest. */
export default function Portrait({
  c,
  size = "",
  className = "",
  zoomable = false,
}: {
  c: Pick<CharacterView, "name" | "class" | "color"> & { portrait_url?: string | null };
  size?: Size;
  className?: string;
  /** Click to see the portrait full size (only when there is an uploaded image). */
  zoomable?: boolean;
}) {
  const [broken, setBroken] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const url = c.portrait_url && broken !== c.portrait_url ? c.portrait_url : null;
  const canZoom = zoomable && !!url;
  return (
    <>
      <span
        className={`char-avatar portrait ${size} ${className} ${canZoom ? "zoomable" : ""}`}
        style={{ background: c.color || "#777" }}
        title={canZoom ? `${c.name}: click to enlarge` : c.name}
        onClick={
          canZoom
            ? (e) => {
                e.stopPropagation();
                setOpen(true);
              }
            : undefined
        }
      >
        {url ? <img src={url} alt="" loading="lazy" onError={() => setBroken(url)} /> : <Crest name={c.name} cls={c.class} color={c.color} size={PX[size]} />}
      </span>
      {open && url && <PortraitLightbox url={url} name={c.name} onClose={() => setOpen(false)} />}
    </>
  );
}

/** A portrait shown large over the page; click anywhere or press Escape to close. */
function PortraitLightbox({ url, name, onClose }: { url: string; name: string; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return createPortal(
    <div
      className="portrait-lightbox"
      role="dialog"
      aria-label={`${name} portrait`}
      onClick={(e) => {
        e.stopPropagation();
        onClose();
      }}
    >
      <figure>
        <img src={url} alt={`${name} portrait`} />
        <figcaption>{name}</figcaption>
      </figure>
    </div>,
    document.body,
  );
}

const MAX_BYTES = 3 * 1024 * 1024;
const TYPES = ["image/png", "image/jpeg", "image/webp"];

/** Portrait with Upload / Remove controls (the server re-encodes to 256×256). */
export function PortraitEditor({
  c,
  upload,
  remove,
  generate,
  size = "big",
}: {
  c: CharacterView;
  upload: (f: File) => Promise<unknown>;
  remove: () => Promise<unknown>;
  /** Paint one with Grok from a short description (needs a Grok key in Settings). */
  generate?: (notes: string) => Promise<unknown>;
  size?: Size;
}) {
  const input = useRef<HTMLInputElement | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [painting, setPainting] = useState<string | null>(null); // the description being written, when open
  const paint = async () => {
    if (!generate || painting === null) return;
    setBusy(true);
    setErr(null);
    try {
      await generate(painting.trim());
      setPainting(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const pick = async (f: File | undefined) => {
    if (!f) return;
    setErr(null);
    if (!TYPES.includes(f.type)) return setErr("Use a PNG, JPEG or WebP image.");
    if (f.size > MAX_BYTES) return setErr("That image is over 3 MB.");
    setBusy(true);
    try {
      await upload(f);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  };

  return (
    <div className="portrait-editor">
      <Portrait c={c} size={size} zoomable />
      <div className="portrait-actions">
        <input ref={input} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={(e) => void pick(e.target.files?.[0])} />
        <button className="btn tiny" disabled={busy} onClick={() => input.current?.click()}>
          {busy ? "Uploading…" : c.portrait_url ? "Change portrait" : "Upload portrait"}
        </button>
        {c.portrait_url && (
          <button
            className="btn tiny ghost"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setErr(null);
              try {
                await remove();
              } catch (e) {
                setErr(e instanceof Error ? e.message : String(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            Remove
          </button>
        )}
        {generate && painting === null && (
          <button className="btn tiny ghost" disabled={busy} onClick={() => setPainting("")} title="Paint a portrait with your Grok key">
            ✨ Paint with Grok
          </button>
        )}
        {err && <span className="error-text small">{err}</span>}
      </div>
      {generate && painting !== null && (
        <div className="paint-portrait">
          <textarea
            rows={2}
            maxLength={600}
            autoFocus
            value={painting}
            placeholder="What do they look like? e.g. bronze scales, a scarred snout, battered plate armour"
            onChange={(e) => setPainting(e.target.value)}
          />
          <div className="row gap">
            <button className="btn tiny ghost" disabled={busy} onClick={() => setPainting(null)}>
              Cancel
            </button>
            <button className="btn tiny primary" disabled={busy} onClick={() => void paint()}>
              {busy ? "Painting… (about 10 s)" : "Paint portrait (about $0.02)"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

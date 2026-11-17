"""Campaign plots: a host-written story outline (custom content kind "plot") that steers the DM.

The plot is snapshotted into the game's state when the host picks it, so later edits or deletion of the
library entry don't change a running game. Only the DM and the host ever see it — players get surprised.
"""

PLOT_DATA_MAX = 16000
TEXT_FIELDS = {  # key: (label for the DM, max length)
    "premise": ("Premise", 2000),
    "opening": ("Opening scene", 1500),
    "villain": ("Villain / main threat", 1500),
    "goal": ("What the villain wants and how it plays out if nobody stops them", 1500),
    "ending": ("Intended climax / possible endings", 1500),
    "themes": ("Themes and mood", 500),
}
LIST_FIELDS = {  # key: (label, max items, max length per item)
    "acts": ("Story beats, in rough order", 10, 600),
    "secrets": ("Secrets and clues to reveal", 12, 400),
    "twists": ("Twists", 6, 400),
}
NPC_MAX = 10


def _text(v, n: int) -> str:
    return str(v or "").strip()[:n]


def _list(v, items: int, n: int) -> list[str]:
    if isinstance(v, str):
        v = v.splitlines()
    if not isinstance(v, list):
        return []
    return [s for s in (_text(x, n) for x in v) if s][:items]


def clean(data: dict) -> dict:
    """Normalise a plot entry's `data`; raises ValueError with a friendly message."""
    out: dict = {}
    for k, (_, n) in TEXT_FIELDS.items():
        if t := _text(data.get(k), n):
            out[k] = t
    for k, (_, items, n) in LIST_FIELDS.items():
        if lst := _list(data.get(k), items, n):
            out[k] = lst
    npcs = []
    for x in (data.get("npcs") or [])[:NPC_MAX] if isinstance(data.get("npcs"), list) else []:
        if not isinstance(x, dict):
            continue
        name = _text(x.get("name"), 60)
        if not name:
            continue
        npc = {"name": name}
        for k, n in (("role", 300), ("secret", 400)):
            if t := _text(x.get(k), n):
                npc[k] = t
        npcs.append(npc)
    if npcs:
        out["npcs"] = npcs
    if not out.get("premise"):
        raise ValueError("a campaign plot needs a premise")
    return out


def snapshot(entry: dict) -> dict:
    """What gets stored on the game: the library entry frozen at pick time."""
    data = clean(entry.get("data") or {})
    return {"entry_id": entry.get("id"), "name": _text(entry.get("name"), 80) or "Campaign plot",
            "notes": _text(entry.get("description"), 3000), **data}


def prompt_block(plot: dict) -> str:
    """The plot as written for the DM's system prompt."""
    lines = [f"CAMPAIGN PLOT — \"{plot.get('name', '')}\", written by the host. Follow it as the spine of the campaign: "
             "steer toward its beats and ending, but let the players' choices bend it — never railroad, and adapt "
             "when they go off-script. It is SECRET: never reveal it or quote it; reveal secrets and twists only "
             "through play, when earned."]
    for k, (label, _) in TEXT_FIELDS.items():
        if plot.get(k):
            lines.append(f"- {label}: {plot[k]}")
    for k, (label, _, _) in LIST_FIELDS.items():
        if plot.get(k):
            lines.append(f"- {label}:")
            lines += [f"  {i}. {s}" for i, s in enumerate(plot[k], 1)]
    if plot.get("npcs"):
        lines.append("- Key NPCs:")
        for n in plot["npcs"]:
            lines.append(f"  • {n['name']}" + (f" — {n['role']}" if n.get("role") else "")
                         + (f" (secret: {n['secret']})" if n.get("secret") else ""))
    if plot.get("notes"):
        lines.append(f"- Host's notes: {plot['notes']}")
    return "\n".join(lines)

import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { CustomEntry } from "../../api/types";
import { useGame } from "./gameContext";

/** Host, in the lobby: choose or change the campaign plot from My content before the game starts. */
export default function PlotPicker() {
  const { view, gameId, run } = useGame();
  const [plots, setPlots] = useState<CustomEntry[] | null>(null);
  useEffect(() => {
    api
      .customList()
      .then((l) => setPlots(l.filter((e) => e.kind === "plot")))
      .catch(() => setPlots([]));
  }, []);
  const cur = view.plot?.entry_id ?? "";
  // nothing to pick and nothing picked: stay out of the way
  if (!plots || (!plots.length && !view.plot)) return null;
  const known = plots.some((p) => p.id === cur);
  return (
    <label className="plot-picker small" title="Your story outline for the DM. Players never see it.">
      <span className="muted">📜 Plot</span>{" "}
      <select value={cur} onChange={(e) => void run(() => api.setPlot(gameId, e.target.value || null))}>
        <option value="">None: the DM invents it</option>
        {view.plot && !known && <option value={cur}>{view.plot.name} (deleted from My content)</option>}
        {plots.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>
    </label>
  );
}

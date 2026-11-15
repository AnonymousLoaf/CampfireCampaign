import { useMemo, useState } from "react";
import { api } from "../../api/client";
import { formatMoney } from "../../util/format";
import Modal from "../Modal";
import CharacterSwitcher from "./CharacterSwitcher";
import { ReadyList } from "./Composer";
import { useGame } from "./gameContext";

const SHOP_TYPE_LABEL: Record<string, string> = {
  general: "General store",
  blacksmith: "Blacksmith",
  alchemist: "Alchemist",
  magic: "Magic shop",
  temple: "Temple",
  inn: "Inn",
};

export default function ShopModal({ onClose }: { onClose: () => void }) {
  const { view, gameId, run, acting, charParam } = useGame();
  const shop = view.shop;
  const [cat, setCat] = useState("All");
  const [qty, setQty] = useState<Record<string, number>>({});
  const [q, setQ] = useState("");
  const meReady = view.members.find((m) => m.user_id === view.me.user_id)?.ready ?? false;
  const canTrade = view.phase.type === "shop";

  const cats = useMemo(() => ["All", ...Array.from(new Set((shop?.stock ?? []).map((s) => s.category))).sort()], [shop]);

  if (!shop) {
    return (
      <Modal title="Shop" onClose={onClose}>
        <div className="muted">The shop is closed.</div>
      </Modal>
    );
  }

  const stock = shop.stock.filter((s) => (cat === "All" || s.category === cat) && (!q || s.name.toLowerCase().includes(q.toLowerCase())));
  const gold = acting?.gold_cp ?? 0;
  const discount = acting ? shop.discounts?.[acting.id] ?? 0 : 0;
  const haggled = !!acting && (shop.haggled ?? []).includes(acting.id);
  // Always offer haggling; an older server simply answers with an error toast.
  const supportsHaggle = true;
  const buyPrice = (p: number) => Math.max(0, Math.round(p * (1 + discount)));
  const typeLabel = SHOP_TYPE_LABEL[shop.type] ?? shop.type;

  return (
    <Modal
      title={shop.name}
      wide
      onClose={onClose}
      footer={
        <>
          <ReadyList />
          <div className="grow" />
          <label className="toggle">
            <input type="checkbox" checked={meReady} disabled={!canTrade} onChange={(e) => void run(() => api.ready(gameId, e.target.checked))} />
            <span>I'm done shopping</span>
          </label>
          <button className="btn" onClick={onClose}>
            Close
          </button>
        </>
      }
    >
      <div className="shop-head">
        <div className="muted">
          {typeLabel && <span className="badge">{typeLabel}</span>} {shop.keeper ? `${shop.keeper} watches you browse.` : ""} Buys at{" "}
          {Math.round(shop.sell_rate * 100)}% of value.
        </div>
        <div className="row gap">
          {supportsHaggle && acting && (
            haggled ? (
              <span className={`badge ${discount < 0 ? "green" : discount > 0 ? "red" : ""}`} title="Haggling result for this character">
                {discount < 0 ? `${Math.round(-discount * 100)}% off` : discount > 0 ? `${Math.round(discount * 100)}% dearer` : "No deal"}
              </span>
            ) : (
              <button
                className="btn small"
                disabled={!canTrade}
                title="One Persuasion check per character at this shop — a good roll gets a discount, a bad one annoys the keeper"
                onClick={() => void run(() => api.haggle(gameId, charParam))}
              >
                🤝 Haggle
              </button>
            )
          )}
          <CharacterSwitcher label="Shopping for" />
        </div>
      </div>
      <div className="shop-grid">
        <div className="shop-col">
          <div className="shop-col-head">
            <h3>For sale</h3>
            <input placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} className="small-input" />
          </div>
          <div className="cat-tabs">
            {cats.map((c) => (
              <button key={c} className={`chip ${cat === c ? "selected" : ""}`} onClick={() => setCat(c)}>
                {c}
              </button>
            ))}
          </div>
          <div className="shop-list">
            {stock.length === 0 && <div className="muted small">Nothing here.</div>}
            {stock.map((s) => {
              const service = !!s.service || s.category === "Service";
              const n = service ? 1 : Math.max(1, Math.min(s.qty || 99, qty[s.key] ?? 1));
              const unit = buyPrice(s.price_cp);
              const total = unit * n;
              const afford = total <= gold;
              return (
                <div key={s.key} className={`shop-item ${service ? "service" : ""}`}>
                  <div className="inv-main">
                    <div>
                      <strong>{s.name}</strong> {s.rarity && <span className={`badge rarity rarity-${s.rarity.toLowerCase().replace(/\s+/g, "-")}`}>{s.rarity}</span>}{" "}
                      {service ? <span className="badge blue">service</span> : <span className="muted small">{s.qty > 0 ? `${s.qty} in stock` : ""}</span>}
                    </div>
                    <div className="muted small">
                      {s.category}
                      {s.damage && ` · ${s.damage}`}
                      {s.ac && ` · ${s.ac}`}
                      {s.properties.length > 0 && ` · ${s.properties.join(", ")}`}
                      {s.weight ? ` · ${s.weight} lb` : ""}
                    </div>
                    {s.description && <div className="small clamp">{s.description}</div>}
                  </div>
                  <div className="shop-buy">
                    <span className="price">
                      {discount !== 0 && <s className="muted small">{formatMoney(s.price_cp)}</s>} {formatMoney(unit)}
                    </span>
                    {!service && (
                      <input
                        type="number"
                        min={1}
                        max={s.qty || 99}
                        value={n}
                        className="qty"
                        onChange={(e) => setQty({ ...qty, [s.key]: Math.max(1, Number(e.target.value) || 1) })}
                      />
                    )}
                    <button
                      className="btn small primary"
                      disabled={!canTrade || !afford || (!service && s.qty === 0)}
                      title={!afford ? "Not enough gold" : ""}
                      onClick={() => void run(() => api.buy(gameId, s.key, n, charParam))}
                    >
                      {service ? "Pay" : "Buy"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        <div className="shop-col">
          <div className="shop-col-head">
            <h3>{acting ? `${acting.name}'s pack` : "Your pack"}</h3>
            <span className="gold">💰 {formatMoney(gold)}</span>
          </div>
          <div className="shop-list">
            {(acting?.inventory ?? []).length === 0 && <div className="muted small">Nothing to sell.</div>}
            {(acting?.inventory ?? []).map((it) => {
              const offer = Math.floor(it.value_cp * shop.sell_rate);
              return (
                <div key={it.id} className="shop-item">
                  <div className="inv-main">
                    <div>
                      <strong>{it.name}</strong>
                      {it.qty > 1 && <span className="muted"> ×{it.qty}</span>}
                      {it.equipped && <span className="badge green small">equipped</span>}
                    </div>
                    <div className="muted small">{it.category}</div>
                  </div>
                  <div className="shop-buy">
                    <span className="price">{offer > 0 ? formatMoney(offer) : "worthless"}</span>
                    <button
                      className="btn small"
                      disabled={!canTrade || offer <= 0}
                      onClick={() => void run(() => api.sell(gameId, it.id, 1, charParam))}
                      title={it.equipped ? "Selling will unequip it" : ""}
                    >
                      Sell
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </Modal>
  );
}

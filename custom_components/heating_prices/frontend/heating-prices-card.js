/*
 * Heating Prices card for Home Assistant.
 * Shows heating oil, wood pellet and natural gas prices with trends and a
 * per-kWh comparison. Data comes from the heating_prices integration.
 */

const CARD_VERSION = "0.1.3";
const FUELS = ["heating_oil", "pellets", "natural_gas"];
const RANGES = { "6m": 183, "1y": 365, "3y": 1096, max: Infinity };

const FUEL_STYLE = {
  heating_oil: { icon: "mdi:oil", color: "#e8833a" },
  pellets: { icon: "mdi:grain", color: "#8bb04b" },
  natural_gas: { icon: "mdi:fire", color: "#3d8bd9" },
};

const I18N = {
  de: {
    title: "Heizpreise",
    fuels: { heating_oil: "Heizöl", pellets: "Holzpellets", natural_gas: "Erdgas" },
    rating: { low: "Günstig", normal: "Normal", high: "Teuer" },
    ranges: { "6m": "6 M", "1y": "1 J", "3y": "3 J", max: "Max" },
    updated: "aktualisiert",
    as_of: "Stand",
    weekdays: ["So.", "Mo.", "Di.", "Mi.", "Do.", "Fr.", "Sa."],
    estimated: "geschätzt",
    estimated_hint: "Halbjahreswert von Eurostat, mit dem monatlichen Gaspreisindex fortgeschrieben",
    stale: "Daten veraltet",
    vs_previous: { heating_oil: "zur Vorwoche", pellets: "zum Vormonat", natural_gas: "zum Vormonat" },
    min: "Min",
    max: "Max",
    avg: "Ø 12 M",
    heat_price: "Wärmepreis pro kWh",
    cheapest: "Am günstigsten",
    own_price: "Dein Preis",
    below: "unter Markt",
    above: "über Markt",
    sources: "Quellen",
    no_entry: "Die Integration Heizpreise ist noch nicht eingerichtet.",
    error: "Preise konnten nicht geladen werden",
    loading: "Lade Preise …",
    editor: {
      title: "Titel",
      entry_id: "Land (Integrationseintrag)",
      fuels: "Brennstoffe",
      range: "Zeitraum der Kurven",
      show_comparison: "Wärmepreis-Vergleich anzeigen",
    },
  },
  en: {
    title: "Heating prices",
    fuels: { heating_oil: "Heating oil", pellets: "Wood pellets", natural_gas: "Natural gas" },
    rating: { low: "Low", normal: "Normal", high: "High" },
    ranges: { "6m": "6 M", "1y": "1 Y", "3y": "3 Y", max: "Max" },
    updated: "updated",
    as_of: "As of",
    weekdays: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
    estimated: "estimate",
    estimated_hint: "Eurostat half-year price carried forward with the monthly gas price index",
    stale: "Data outdated",
    vs_previous: { heating_oil: "vs. last week", pellets: "vs. last month", natural_gas: "vs. last month" },
    min: "Min",
    max: "Max",
    avg: "Avg 12 M",
    heat_price: "Price per kWh of heat",
    cheapest: "Cheapest",
    own_price: "Your price",
    below: "below market",
    above: "above market",
    sources: "Sources",
    no_entry: "The Heating Prices integration is not set up yet.",
    error: "Prices could not be loaded",
    loading: "Loading prices …",
    editor: {
      title: "Title",
      entry_id: "Country (integration entry)",
      fuels: "Fuels",
      range: "Chart range",
      show_comparison: "Show heat price comparison",
    },
  },
};

function strings(hass) {
  const lang = (hass?.locale?.language || hass?.language || "en").slice(0, 2);
  return I18N[lang] || I18N.en;
}

function lang(hass) {
  return hass?.locale?.language || hass?.language || "en";
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[ch]);
}

function number(hass, value, digits = 2) {
  if (value === null || value === undefined) return "–";
  return new Intl.NumberFormat(lang(hass), {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

function parseDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function periodLabel(hass, fuel, info, t) {
  const date = parseDate(info.period);
  if (fuel === "heating_oil") {
    // The Oil Bulletin reports the price of one day (Monday), not a weekly average.
    // Weekday abbreviations are fixed because Intl output differs between browsers.
    const day = new Intl.DateTimeFormat(lang(hass), { day: "2-digit", month: "2-digit", year: "numeric" }).format(date);
    return `${t.as_of} ${t.weekdays[date.getDay()]} ${day}`;
  }
  return new Intl.DateTimeFormat(lang(hass), { month: "long", year: "numeric" }).format(date);
}

function sparkline(points, color, id) {
  if (points.length < 2) return "";
  const width = 300;
  const height = 64;
  const pad = 4;
  const values = points.map((p) => p[1]);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const t0 = parseDate(points[0][0]).getTime();
  const t1 = parseDate(points[points.length - 1][0]).getTime();
  const tSpan = t1 - t0 || 1;
  const coords = points.map(([date, value]) => [
    ((parseDate(date).getTime() - t0) / tSpan) * width,
    pad + (1 - (value - min) / span) * (height - 2 * pad),
  ]);
  const line = coords.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${line} L${width},${height} L0,${height} Z`;
  const [lx, ly] = coords[coords.length - 1];
  return `
    <svg class="spark" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id="g-${id}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="${color}" stop-opacity="0.35"></stop>
          <stop offset="100%" stop-color="${color}" stop-opacity="0"></stop>
        </linearGradient>
      </defs>
      <path d="${area}" fill="url(#g-${id})"></path>
      <path d="${line}" fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round" stroke-linecap="round"></path>
      <circle cx="${lx.toFixed(1)}" cy="${ly.toFixed(1)}" r="3.5" fill="${color}" vector-effect="non-scaling-stroke"></circle>
    </svg>`;
}

class HeatingPricesCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("heating-prices-card-editor");
  }

  static getStubConfig() {
    return { range: "1y", show_comparison: true };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._data = undefined;
    this._error = undefined;
    this._watchKey = undefined;
    this._loading = false;
  }

  setConfig(config) {
    this._config = { range: "1y", show_comparison: true, ...config };
    if (this._config.range && !(this._config.range in RANGES)) {
      throw new Error(`Unknown range ${this._config.range}`);
    }
    this._range = this._config.range;
    this._render();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    const key = this._computeWatchKey();
    if (first || key !== this._watchKey) {
      this._watchKey = key;
      this._fetch();
    }
  }

  getCardSize() {
    return 7;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  _computeWatchKey() {
    const entities = Object.values(this._data?.fuels || {}).map((f) => f.entities?.price).filter(Boolean);
    return entities.map((id) => this._hass.states[id]?.last_updated || "").join("|");
  }

  async _fetch() {
    if (this._loading || !this._hass) return;
    this._loading = true;
    try {
      const message = { type: "heating_prices/data" };
      if (this._config?.entry_id) message.entry_id = this._config.entry_id;
      const result = await this._hass.callWS(message);
      this._data = result.entries[0] || null;
      this._error = undefined;
      this._watchKey = this._computeWatchKey();
    } catch (err) {
      this._error = err?.message || String(err);
    } finally {
      this._loading = false;
      this._render();
    }
  }

  _fuels() {
    const available = Object.keys(this._data?.fuels || {});
    const wanted = this._config?.fuels?.length ? this._config.fuels : FUELS;
    return FUELS.filter((f) => wanted.includes(f) && available.includes(f));
  }

  _visible(history) {
    const days = RANGES[this._range] ?? 365;
    if (!Number.isFinite(days) || !history.length) return history;
    const end = parseDate(history[history.length - 1][0]).getTime();
    const start = end - days * 86400000;
    const visible = history.filter(([d]) => parseDate(d).getTime() >= start);
    return visible.length >= 2 ? visible : history.slice(-2);
  }

  _tile(fuel, info, t) {
    const hass = this._hass;
    const style = FUEL_STYLE[fuel];
    const history = this._visible(info.history || []);
    const change = info.change_pct;
    const direction = change > 0 ? "up" : change < 0 ? "down" : "flat";
    const arrow = change > 0 ? "▲" : change < 0 ? "▼" : "▬";
    const rating = info.rating
      ? `<span class="badge rating-${info.rating}">${esc(t.rating[info.rating])}</span>`
      : "";
    const flags = [
      info.estimated ? `<span class="flag" title="${esc(t.estimated_hint)}">${esc(t.estimated)}</span>` : "",
      info.stale ? `<span class="flag warn"><ha-icon icon="mdi:alert-outline"></ha-icon>${esc(t.stale)}</span>` : "",
    ].join("");
    let own = "";
    if (info.own_price) {
      const diff = info.own_diff_pct;
      const cls = diff <= 0 ? "good" : "bad";
      own = `
        <div class="own">
          <span>${esc(t.own_price)} <b>${number(hass, info.own_price)} ${esc(info.unit)}</b></span>
          <span class="${cls}">${number(hass, Math.abs(diff), 1)} % ${esc(diff <= 0 ? t.below : t.above)}</span>
        </div>`;
    }
    return `
      <div class="tile" role="button" tabindex="0" data-entity="${esc(info.entities?.price || "")}" style="--fuel-color:${style.color}">
        <div class="tile-head">
          <span class="icon"><ha-icon icon="${style.icon}"></ha-icon></span>
          <span class="name">${esc(t.fuels[fuel])}</span>
          ${rating}
        </div>
        <div class="price">
          <span class="value">${number(hass, info.price)}</span>
          <span class="unit">${esc(info.unit)}</span>
        </div>
        <div class="meta">
          ${change === null || change === undefined ? "" : `<span class="chip ${direction}" title="${esc(t.vs_previous[fuel])}">${arrow} ${number(hass, Math.abs(change), 1)} %</span>`}
          <span class="period">${esc(periodLabel(hass, fuel, info, t))}</span>
          ${flags}
        </div>
        ${sparkline(history, style.color, fuel)}
        <div class="stats">
          <span>${esc(t.min)} <b>${number(hass, info.min_12m)}</b></span>
          <span>${esc(t.avg)} <b>${number(hass, info.avg_12m)}</b></span>
          <span>${esc(t.max)} <b>${number(hass, info.max_12m)}</b></span>
        </div>
        ${own}
      </div>`;
  }

  _comparison(fuels, t) {
    if (!this._config.show_comparison || fuels.length < 2) return "";
    const hass = this._hass;
    const rows = fuels.map((fuel) => ({ fuel, value: this._data.fuels[fuel].heat_price }));
    const max = Math.max(...rows.map((r) => r.value));
    const cheapest = this._data.cheapest;
    return `
      <div class="compare">
        <div class="section-title">${esc(t.heat_price)}</div>
        ${rows
          .sort((a, b) => a.value - b.value)
          .map(({ fuel, value }) => `
            <div class="bar-row ${fuel === cheapest ? "best" : ""}" style="--fuel-color:${FUEL_STYLE[fuel].color}">
              <span class="bar-label"><ha-icon icon="${FUEL_STYLE[fuel].icon}"></ha-icon>${esc(t.fuels[fuel])}</span>
              <span class="bar"><span class="fill" style="width:${Math.max(4, (value / max) * 100).toFixed(1)}%"></span></span>
              <span class="bar-value">${number(hass, value)} ct</span>
              ${fuel === cheapest ? `<span class="best-badge" title="${esc(t.cheapest)}"><ha-icon icon="mdi:trophy-outline"></ha-icon></span>` : `<span class="best-badge"></span>`}
            </div>`)
          .join("")}
      </div>`;
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const t = strings(this._hass);
    const title = this._config.title ?? t.title;
    let body;

    if (this._error) {
      body = `<div class="empty"><ha-icon icon="mdi:alert-circle-outline"></ha-icon>${esc(t.error)}: ${esc(this._error)}</div>`;
    } else if (this._data === undefined) {
      body = `<div class="empty">${esc(t.loading)}</div>`;
    } else if (this._data === null) {
      body = `<div class="empty"><ha-icon icon="mdi:information-outline"></ha-icon>${esc(t.no_entry)}</div>`;
    } else {
      const fuels = this._fuels();
      const sourceLinks = new Map(fuels.map((f) => [this._data.fuels[f].source, this._data.fuels[f].source_url]));
      const sources = [...sourceLinks]
        .map(([name, url]) => `<a href="${esc(url)}" target="_blank" rel="noreferrer">${esc(name)}</a>`)
        .join(" · ");
      const updated = this._data.last_update
        ? new Intl.DateTimeFormat(lang(this._hass), { dateStyle: "medium", timeStyle: "short" }).format(new Date(this._data.last_update))
        : "";
      body = `
        <div class="header">
          <div>
            <div class="title">${esc(title)}</div>
            <div class="subtitle">${esc(this._data.title)}${updated ? ` · ${esc(t.updated)} ${esc(updated)}` : ""}</div>
          </div>
          <div class="ranges" role="tablist">
            ${Object.keys(RANGES)
              .map((r) => `<button role="tab" data-range="${r}" aria-selected="${r === this._range}" class="${r === this._range ? "active" : ""}">${esc(t.ranges[r])}</button>`)
              .join("")}
          </div>
        </div>
        <div class="grid">${fuels.map((f) => this._tile(f, this._data.fuels[f], t)).join("")}</div>
        ${this._comparison(fuels, t)}
        <div class="footer">${esc(t.sources)}: ${sources}</div>`;
    }

    this.shadowRoot.innerHTML = `<style>${STYLES}</style><ha-card>${body}</ha-card>`;
    this._bind();
  }

  _bind() {
    this.shadowRoot.querySelectorAll("button[data-range]").forEach((button) =>
      button.addEventListener("click", () => {
        this._range = button.dataset.range;
        this._render();
      })
    );
    this.shadowRoot.querySelectorAll(".tile[data-entity]").forEach((tile) => {
      const open = () => {
        if (!tile.dataset.entity) return;
        this.dispatchEvent(new CustomEvent("hass-more-info", {
          detail: { entityId: tile.dataset.entity }, bubbles: true, composed: true,
        }));
      };
      tile.addEventListener("click", open);
      tile.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          open();
        }
      });
    });
  }
}

const STYLES = `
  :host { display: block; }
  ha-card { padding: 16px; overflow: hidden; }
  .header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
  .title { font-size: 1.25rem; font-weight: 600; color: var(--primary-text-color); line-height: 1.3; }
  .subtitle { font-size: 0.85rem; color: var(--secondary-text-color); margin-top: 2px; }
  .ranges { display: inline-flex; background: var(--secondary-background-color, rgba(127,127,127,.12)); border-radius: 999px; padding: 3px; }
  .ranges button { border: 0; background: transparent; color: var(--secondary-text-color); font: inherit; font-size: 0.8rem; font-weight: 500; padding: 4px 10px; border-radius: 999px; cursor: pointer; }
  .ranges button.active { background: var(--card-background-color, #fff); color: var(--primary-text-color); box-shadow: 0 1px 3px rgba(0,0,0,.15); }
  .ranges button:focus-visible { outline: 2px solid var(--primary-color); }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
  .tile { position: relative; border-radius: 14px; padding: 14px 14px 12px; cursor: pointer; outline: none;
    background: linear-gradient(160deg, color-mix(in srgb, var(--fuel-color) 14%, transparent), color-mix(in srgb, var(--fuel-color) 3%, transparent) 60%);
    border: 1px solid color-mix(in srgb, var(--fuel-color) 25%, transparent); transition: transform .15s ease, box-shadow .15s ease; }
  .tile:hover { transform: translateY(-1px); box-shadow: 0 4px 14px color-mix(in srgb, var(--fuel-color) 22%, transparent); }
  .tile:focus-visible { box-shadow: 0 0 0 2px var(--fuel-color); }
  .tile-head { display: flex; align-items: center; gap: 8px; }
  .icon { display: inline-flex; width: 32px; height: 32px; border-radius: 10px; align-items: center; justify-content: center;
    background: color-mix(in srgb, var(--fuel-color) 22%, transparent); color: var(--fuel-color); --mdc-icon-size: 20px; }
  .name { font-weight: 600; color: var(--primary-text-color); flex: 1; }
  .badge { font-size: 0.72rem; font-weight: 600; padding: 3px 8px; border-radius: 999px; letter-spacing: .02em; }
  .rating-low { background: color-mix(in srgb, var(--success-color, #43a047) 18%, transparent); color: var(--success-color, #2e7d32); }
  .rating-normal { background: color-mix(in srgb, var(--secondary-text-color) 15%, transparent); color: var(--secondary-text-color); }
  .rating-high { background: color-mix(in srgb, var(--error-color, #db4437) 16%, transparent); color: var(--error-color, #c62828); }
  .price { display: flex; align-items: baseline; gap: 6px; margin: 12px 0 4px; }
  .value { font-size: 2rem; font-weight: 700; color: var(--primary-text-color); letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }
  .unit { font-size: 0.9rem; color: var(--secondary-text-color); }
  .meta { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; font-size: 0.8rem; color: var(--secondary-text-color); }
  .chip { font-weight: 600; padding: 2px 7px; border-radius: 6px; font-variant-numeric: tabular-nums; }
  .chip.up { color: var(--error-color, #c62828); background: color-mix(in srgb, var(--error-color, #db4437) 12%, transparent); }
  .chip.down { color: var(--success-color, #2e7d32); background: color-mix(in srgb, var(--success-color, #43a047) 14%, transparent); }
  .chip.flat { background: color-mix(in srgb, var(--secondary-text-color) 12%, transparent); }
  .flag { display: inline-flex; align-items: center; gap: 3px; font-size: 0.72rem; padding: 2px 6px; border-radius: 6px; border: 1px dashed var(--divider-color, rgba(127,127,127,.4)); cursor: help; }
  .flag.warn { color: var(--warning-color, #f39c12); border-color: currentColor; --mdc-icon-size: 14px; }
  .spark { display: block; width: 100%; height: 64px; margin: 10px 0 6px; overflow: visible; }
  .stats { display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--secondary-text-color); gap: 6px; }
  .stats b { color: var(--primary-text-color); font-weight: 600; font-variant-numeric: tabular-nums; }
  .own { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 2px 8px; margin-top: 10px; padding-top: 8px; border-top: 1px solid var(--divider-color, rgba(127,127,127,.2)); font-size: 0.8rem; color: var(--secondary-text-color); }
  .own b { color: var(--primary-text-color); }
  .own .good { color: var(--success-color, #2e7d32); font-weight: 600; }
  .own .bad { color: var(--error-color, #c62828); font-weight: 600; }
  .compare { margin-top: 16px; padding: 14px; border-radius: 14px; background: var(--secondary-background-color, rgba(127,127,127,.08)); }
  .section-title { font-size: 0.85rem; font-weight: 600; color: var(--secondary-text-color); text-transform: uppercase; letter-spacing: .06em; margin-bottom: 10px; }
  .bar-row { display: grid; grid-template-columns: 120px 1fr 5.2em 22px; align-items: center; gap: 10px; padding: 4px 0; }
  .bar-label { display: inline-flex; align-items: center; gap: 6px; color: var(--primary-text-color); font-size: 0.9rem; --mdc-icon-size: 18px; }
  .bar-label ha-icon { color: var(--fuel-color); }
  .bar { height: 10px; border-radius: 999px; background: color-mix(in srgb, var(--fuel-color) 14%, transparent); overflow: hidden; }
  .fill { display: block; height: 100%; border-radius: 999px; background: var(--fuel-color); transition: width .4s ease; }
  .bar-value { font-variant-numeric: tabular-nums; font-weight: 600; color: var(--primary-text-color); font-size: 0.9rem; text-align: right; }
  .best .bar-value { color: var(--success-color, #2e7d32); }
  .best-badge { color: var(--success-color, #2e7d32); --mdc-icon-size: 18px; display: inline-flex; }
  .footer { margin-top: 12px; font-size: 0.72rem; color: var(--secondary-text-color); }
  .footer a { color: inherit; }
  .empty { display: flex; align-items: center; gap: 8px; color: var(--secondary-text-color); padding: 8px 0; }
  @media (max-width: 420px) { .value { font-size: 1.7rem; } .bar-row { grid-template-columns: 100px 1fr 4.8em 18px; gap: 8px; } }
`;

class HeatingPricesCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    // Home Assistant sets hass on every state change; only pass it on instead
    // of rebuilding the form, which would reset the selectors each time.
    if (this._form) {
      this._form.hass = hass;
      return;
    }
    this._render();
  }

  _render() {
    if (!this._hass || !this._config) return;
    const t = strings(this._hass);
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (schema) => t.editor[schema.name] || schema.name;
      this._form.addEventListener("value-changed", (ev) => {
        const config = { ...ev.detail.value };
        Object.keys(config).forEach((key) => {
          if (config[key] === "" || (Array.isArray(config[key]) && !config[key].length)) delete config[key];
        });
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = this._config;
    if (this._formLanguage === t) return;
    this._formLanguage = t;
    this._form.schema = [
      { name: "title", selector: { text: {} } },
      { name: "entry_id", selector: { config_entry: { integration: "heating_prices" } } },
      {
        name: "fuels",
        selector: { select: { multiple: true, options: FUELS.map((f) => ({ value: f, label: t.fuels[f] })) } },
      },
      {
        name: "range",
        selector: { select: { mode: "dropdown", options: Object.keys(RANGES).map((r) => ({ value: r, label: t.ranges[r] })) } },
      },
      { name: "show_comparison", selector: { boolean: {} } },
    ];
  }
}

const ELEMENTS = [
  ["heating-prices-card", HeatingPricesCard],
  ["heating-prices-card-editor", HeatingPricesCardEditor],
];

// The integration loads this file very early. Home Assistant can afterwards
// replace window.customElements with a scoped registry that does not know
// elements defined before, and then waits forever for the card. Registering
// again in whatever registry is current fixes that; a subclass is used when
// the registry refuses a constructor it has seen before.
function registerElements() {
  for (const [name, elementClass] of ELEMENTS) {
    if (customElements.get(name)) continue;
    try {
      customElements.define(name, elementClass);
    } catch (err) {
      try {
        customElements.define(name, class extends elementClass {});
      } catch (err2) {
        console.warn(`heating-prices-card: could not register ${name}`, err2);
      }
    }
  }
}

if (!window.customCards?.some((card) => card.type === "heating-prices-card")) {
  registerElements();
  // Check again while the frontend starts up and whenever it navigates.
  let checks = 0;
  const timer = setInterval(() => {
    registerElements();
    if (++checks >= 120) clearInterval(timer);
  }, 1000);
  window.addEventListener("location-changed", registerElements);

  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "heating-prices-card",
    name: "Heating Prices",
    description: "Heating oil, wood pellet and natural gas prices with trends and a per-kWh comparison.",
    preview: true,
    documentationURL: "https://github.com/F30onAir/ha-heating-prices",
  });
  console.info(`%c HEATING-PRICES-CARD %c ${CARD_VERSION} `, "background:#e8833a;color:#fff;border-radius:3px 0 0 3px", "background:#333;color:#fff;border-radius:0 3px 3px 0");
}

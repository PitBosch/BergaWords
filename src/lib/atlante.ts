// Colori e utilità condivise dalle mappe dell'atlante (pagina iniziale e pagina della parola).
import { geoArea, interpolateLab } from "d3";

// Palette categoriale validata con dataviz/validate_palette.js (CVD, contrasto), in ordine fisso:
// la variante più diffusa in provincia prende il primo colore. Oltre l'ottava, e "Altre forme": grigio.
export const PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];
export const GRIGIO = "#b9b5ad";
export const ALTRE = "Altre forme";

export const CARTA = "#eef0ec";
export const TERRA = "#dadfd8";
export const INCHIOSTRO = "#1c2433";
export const GRAFITE = "#5b6270";

export const coloreVariante = (nome: string, i: number) =>
  nome === ALTRE || i >= PALETTE.length ? GRIGIO : PALETTE[i];

// Rampa sequenziale a una tinta: carta a 0%, la tinta piena a ~60%, più scura (verso l'inchiostro) a 100%.
export function rampa(colore: string): (t: number) => string {
  const chiaro = interpolateLab(CARTA, colore)(0.06);
  const scuro = interpolateLab(colore, INCHIOSTRO)(0.45);
  const a = interpolateLab(chiaro, colore), b = interpolateLab(colore, scuro);
  const cache: string[] = [];
  return t => {
    const k = Math.round(Math.min(1, Math.max(0, t)) * 100);
    return (cache[k] ??= k <= 60 ? a(k / 60) : b((k - 60) / 40));
  };
}

// Fondo di un esagono nella mappa "più detta": la tinta mescolata alla carta secondo il consenso.
export function velatura(colore: string): (consenso: number) => string {
  const f = interpolateLab(CARTA, colore);
  const cache: string[] = [];
  return c => {
    const k = Math.round(Math.min(1, Math.max(0, c)) * 50);
    return (cache[k] ??= f(0.16 + 0.84 * k / 50));
  };
}

export const pct = (x: number) => (x >= 0.995 ? "100%" : x < 0.005 ? "<1%" : `${Math.round(x * 100)}%`);

export function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

const cache: Record<string, Promise<any>> = {};
export const json = (u: string) =>
  (cache[u] ??= fetch(u).then(r => { if (!r.ok) throw new Error(u); return r.json(); }));

export const movimentoRidotto = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Canvas nitido sugli schermi ad alta densità.
export function canvas2d(c: HTMLCanvasElement, w: number, h: number) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  c.width = Math.round(w * dpr); c.height = Math.round(h * dpr);
  c.style.width = `${w}px`; c.style.height = `${h}px`;
  const ctx = c.getContext("2d")!;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return ctx;
}

// d3 lavora sulla sfera e vuole gli anelli esterni in senso orario: un poligono antiorario (come quelli
// di shapely o di molti GeoJSON) diventa "tutto il mondo tranne lui". Gira gli anelli dove serve.
export function riavvolgi<T extends { features: any[] }>(fc: T): T {
  for (const f of fc.features) {
    const g = f.geometry;
    const poligoni = g.type === "Polygon" ? [g.coordinates] : g.type === "MultiPolygon" ? g.coordinates : [];
    for (const anelli of poligoni) {
      if (geoArea({ type: "Polygon", coordinates: [anelli[0]] }) > 2 * Math.PI) {
        for (const a of anelli) a.reverse();
      }
    }
  }
  return fc;
}

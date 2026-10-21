// Riepilogo testuale di ogni parola, calcolato al momento della build dai file gold: serve alle pagine
// (testo leggibile dai motori di ricerca), a sitemap.xml e a llms.txt. Gira solo lato server.
import fs from "node:fs";
import path from "node:path";
import { words, type Word } from "../data/words";

export const ALTRE = "Altre forme";

// slug degli URL e dei file gold: "L'Asso di Ori" -> "l-asso-di-ori"
export const slugPulito = (s: string) =>
  s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

export type Variante = { nome: string; quota: number; comuni: string[] };   // comuni dove è la più detta, dal più convinto
export type RigaComune = { comune: string; prima: string; quotaPrima: number; seconda: string | null; quotaSeconda: number };
export type Riepilogo = {
  word: Word; slug: string; nome: string; nomeMinuscolo: string;
  risposte: number; comuniConRisposte: number; rango: number; totale: number;
  varianti: Variante[]; righe: RigaComune[]; perComune: Map<string, RigaComune>;
};

const gold = path.join(process.cwd(), "public", "data", "gold");
const leggi = (f: string) => JSON.parse(fs.readFileSync(path.join(gold, f), "utf8"));

let cache: Riepilogo[] | null = null;

export function riepiloghi(): Riepilogo[] {
  if (cache) return cache;
  const indice = leggi("indice.json");
  const geo = leggi("esagoni.geojson");
  const comuneDi: string[] = geo.features.map((f: any) => f.properties.comune);
  const pop: number[] = geo.features.map((f: any) => Math.max(f.properties.popolazione, 1e-3));
  const perComune = new Map<string, number[]>();
  comuneDi.forEach((c, i) => perComune.set(c, [...(perComune.get(c) ?? []), i]));
  const nomiComuni = [...perComune.keys()].sort((a, b) => a.localeCompare(b, "it"));

  cache = words.map(word => {
    const slug = slugPulito(word.slug);
    const voce = indice.parole.find((p: any) => p.slug === slug);
    const L = leggi(`esagoni/${slug}.json`).livelli.lessema;
    const nomi: string[] = L.varianti.map((v: any) => v.variante);

    // quote di ogni comune: media degli esagoni pesata per popolazione (come nella tabella della pagina)
    const righe: RigaComune[] = nomiComuni.map(c => {
      const idx = perComune.get(c)!;
      const tot = idx.reduce((s, i) => s + pop[i], 0);
      const q = nomi.map(() => 0);
      for (const i of idx) L.quote[i].forEach((v: number, j: number) => (q[j] += (pop[i] / tot) * v / 1000));
      const ord = q.map((_, j) => j).filter(j => nomi[j] !== ALTRE).sort((a, b) => q[b] - q[a]);
      return { comune: c, prima: nomi[ord[0]], quotaPrima: q[ord[0]], seconda: ord[1] != null ? nomi[ord[1]] : null, quotaSeconda: ord[1] != null ? q[ord[1]] : 0 };
    });

    const varianti: Variante[] = L.varianti
      .filter((v: any) => v.variante !== ALTRE && v.quota_provincia >= 0.01)
      .map((v: any) => ({
        nome: v.variante, quota: v.quota_provincia,
        comuni: righe.filter(r => r.prima === v.variante).sort((a, b) => b.quotaPrima - a.quotaPrima).map(r => r.comune),
      }));

    return {
      word, slug, nome: word.name, nomeMinuscolo: word.name.replace(/^L'/, "l'").toLowerCase(),
      risposte: voce?.risposte_valide ?? 0, comuniConRisposte: voce?.comuni_con_risposte ?? 0,
      rango: voce?.rango_divisivita ?? 0, totale: indice.parole.length,
      varianti, righe, perComune: new Map(righe.map(r => [r.comune, r])),
    };
  });
  return cache;
}

// come pct di atlante.ts, che invece importa d3 e gira nel browser
export const pct = (x: number) => (x >= 0.995 ? "100%" : x < 0.005 ? "<1%" : `${Math.round(x * 100)}%`);
export const numero = (n: number) => n.toLocaleString("it-IT");

// "Sunì, Porsèl e Ciù"
export const elenco = (xs: string[]) => (xs.length < 2 ? xs.join("") : `${xs.slice(0, -1).join(", ")} e ${xs[xs.length - 1]}`);

// La risposta breve alla domanda "come si dice X in bergamasco?"
export function risposta(r: Riepilogo) {
  const [a, b, c] = r.varianti;
  const citta = r.perComune.get("Bergamo");
  let t = `In dialetto bergamasco ${r.nomeMinuscolo} si dice soprattutto «${a.nome}» (${pct(a.quota)} delle risposte in provincia)`;
  if (b) t += `, poi «${b.nome}» (${pct(b.quota)})${c ? ` e «${c.nome}» (${pct(c.quota)})` : ""}`;
  t += ".";
  if (citta) t += ` A Bergamo città prevale «${citta.prima}» (${pct(citta.quotaPrima)}).`;
  return t;
}

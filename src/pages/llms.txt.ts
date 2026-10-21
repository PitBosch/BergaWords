// llms.txt: il contenuto del sito in testo semplice, pensato per i modelli linguistici che rispondono
// a domande come "come si dice maiale in bergamasco?" (GEO, generative engine optimization).
import type { APIRoute } from "astro";
import { elenco, numero, pct, riepiloghi, risposta } from "../lib/riepilogo";

export const GET: APIRoute = ({ site }) => {
  const tutti = riepiloghi();
  const url = (p: string) => (site ? new URL(p, site).href : p);
  const risposte = tutti.reduce((s, r) => s + r.risposte, 0);
  const t: string[] = [
    "# BergaWords · Atlante del dialetto bergamasco",
    "",
    `> Come si dicono ${tutti.length} parole di tutti i giorni in dialetto bergamasco, a Bergamo e in ogni comune della provincia. ` +
    `Le carte sono costruite su ${numero(risposte)} risposte di parlanti bergamaschi, stimate su esagoni H3 di circa 0,7 km² ` +
    "e pesate con la popolazione del censimento ISTAT 2021.",
    "",
    "Il bergamasco è il dialetto lombardo orientale parlato a Bergamo e provincia. Le forme cambiano tra Val Brembana, " +
    "Val Seriana, Val di Scalve, Valle Imagna, Val Cavallina, Sebino, Isola e Bassa bergamasca. Le percentuali indicano " +
    "la quota di persone che usa ciascuna forma.",
    "",
    "## Parole",
    "",
  ];
  for (const r of tutti) {
    t.push(`### ${r.nome} in bergamasco`, "", `Pagina: ${url(`/${r.slug}`)}`, "", risposta(r), "");
    for (const v of r.varianti) {
      t.push(`- ${v.nome}: ${pct(v.quota)} in provincia` +
        (v.comuni.length ? `; la più detta in ${v.comuni.length} comuni, tra cui ${elenco(v.comuni.slice(0, 6))}.` : "."));
    }
    t.push("");
  }
  t.push("## Fonti e metodo", "", `- Codice e dati: https://github.com/PitBosch/BergaWords`, `- Pagina iniziale: ${url("/")}`, "");
  return new Response(t.join("\n"), { headers: { "Content-Type": "text/plain; charset=utf-8" } });
};

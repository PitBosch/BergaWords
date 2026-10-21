// Mappa del sito per i motori di ricerca: la pagina iniziale e una pagina per parola.
import type { APIRoute } from "astro";
import { riepiloghi } from "../lib/riepilogo";

export const GET: APIRoute = ({ site }) => {
  const base = site ?? new URL("http://localhost");
  const oggi = new Date().toISOString().slice(0, 10);
  const pagine = [{ p: "/", priorita: "1.0" }, ...riepiloghi().map(r => ({ p: `/${r.slug}`, priorita: "0.8" }))];
  const corpo = pagine.map(({ p, priorita }) =>
    `  <url><loc>${new URL(p, base).href}</loc><lastmod>${oggi}</lastmod><priority>${priorita}</priority></url>`).join("\n");
  return new Response(`<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${corpo}\n</urlset>\n`,
    { headers: { "Content-Type": "application/xml; charset=utf-8" } });
};

// Tutto il sito è aperto, anche ai motori di risposta basati su AI (GEO): più lo leggono, più lo citano.
import type { APIRoute } from "astro";

export const GET: APIRoute = ({ site }) => {
  const righe = [
    "User-agent: *",
    "Allow: /",
    "",
    ...["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot", "Claude-User", "PerplexityBot", "Google-Extended", "Applebot-Extended", "CCBot"]
      .flatMap(b => [`User-agent: ${b}`, "Allow: /", ""]),
  ];
  if (site) righe.push(`Sitemap: ${new URL("/sitemap.xml", site).href}`);
  return new Response(righe.join("\n") + "\n", { headers: { "Content-Type": "text/plain; charset=utf-8" } });
};

import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';

// Dominio pubblico per canonical, sitemap e anteprime social: SITE_URL, altrimenti il dominio di
// produzione che Vercel espone durante la build.
const vercel = process.env.VERCEL_PROJECT_PRODUCTION_URL;
const site = process.env.SITE_URL || (vercel ? `https://${vercel}` : undefined);

export default defineConfig({
  site,
  integrations: [tailwind()],
  output: 'static',
  trailingSlash: 'never',
});

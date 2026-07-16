// @ts-check
import { defineConfig } from "astro/config";

// Project site published at https://sumonoodle.github.io/datsun-620/
// `site` + `base` must match the repo name for links and assets to resolve.
export default defineConfig({
  site: "https://sumonoodle.github.io",
  base: "/datsun-620",
  // Old bookmarks and the digest emails already sent keep working.
  // Redirect destinations are used verbatim (base is NOT prepended).
  redirects: { "/listings": "/datsun-620/" },
});

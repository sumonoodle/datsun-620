// Publish the latest digest to the site as /digest.html so the owner can
// review dry-run digests by tapping a URL instead of reading raw HTML in git.
// Always writes SOMETHING: the home page links to /digest.html
// unconditionally, so a missing source must yield a placeholder, not a 404.
import { copyFileSync, existsSync, mkdirSync, writeFileSync } from "node:fs";

const src = "../data/digest-latest.html";
const dest = "public/digest.html";
try {
  mkdirSync("public", { recursive: true });
  if (existsSync(src)) {
    copyFileSync(src, dest);
    console.log("digest copied to public/digest.html");
  } else {
    writeFileSync(
      dest,
      "<!doctype html><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">" +
      "<title>Datsun 620 digest</title><p style=\"font-family:system-ui;padding:1rem\">" +
      "No digest generated yet. The first daily run creates it.</p>"
    );
    console.log("no digest yet, wrote placeholder");
  }
} catch (err) {
  // A broken digest copy must not fail the whole site build.
  console.warn("digest copy failed, continuing:", err.message);
}

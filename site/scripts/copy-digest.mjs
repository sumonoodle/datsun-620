// Publish the latest digest to the site as /digest.html so the owner can
// review dry-run digests by tapping a URL instead of reading raw HTML in git.
import { copyFileSync, existsSync, mkdirSync } from "node:fs";

const src = "../data/digest-latest.html";
if (existsSync(src)) {
  mkdirSync("public", { recursive: true });
  copyFileSync(src, "public/digest.html");
  console.log("digest copied to public/digest.html");
} else {
  console.log("no digest yet, skipping copy");
}

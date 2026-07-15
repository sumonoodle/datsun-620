"""Daily digest sender. Built out in M4.

Contract: renders data/changes-latest.json + data/run-log.json into a plain
single-column HTML email (mobile mail clients first), writes it to
data/digest-latest.html, and sends via Gmail SMTP only when GMAIL_USER and
GMAIL_APP_PASSWORD are set AND the DIGEST_LIVE repo variable is "1".
Until then every run is a dry run: the HTML lands in the repo for review.
"""

if __name__ == "__main__":
    print("digest: not implemented until M4 (dry-run file will land in data/)")

Title: Wait for Tor readiness in entrypoint; UI selection, progress, and export; glassmorphism polish

Summary
This PR improves container startup reliability by waiting for Tor SOCKS to be ready instead of sleeping blindly. It also enhances the Streamlit UI with investigator-friendly features and a subtle visual polish.

Changes
- entrypoint.sh
  - Replace fixed sleep with a TCP readiness loop for 127.0.0.1:9050 (up to ~60s) and fail fast if Tor is unavailable.
- ui.py
  - Add stage progress indicator across pipeline steps.
  - Allow selecting which filtered results to scrape via a multiselect.
  - Provide CSV/JSON export of scraped sources.
  - Apply a glassmorphism-inspired style to key panels.
- requirements.txt
  - Add pandas for CSV export convenience.

Notes
- JSON export uses stdlib json; CSV uses pandas for robust encoding/formatting.
- Visual styles are conservative and respect the existing dark theme.

Testing
- Manual: built and ran the container; verified Tor readiness wait and fail-fast behavior by toggling Tor availability.
- UI: ran through a full pipeline, unselected some results, and downloaded CSV/JSON outputs.

Follow-ups
- Progress per URL during scraping.
- Advanced settings panel for timeouts, retries, and per-engine toggles.

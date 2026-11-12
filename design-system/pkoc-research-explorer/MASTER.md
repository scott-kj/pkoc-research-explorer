# PKOC Research Explorer design system

Applied UI/UX Pro Max reference: `hud-sci-fi-fui` (HUD / Sci-Fi FUI), adapted to a research dashboard. Plain HTML, CSS and JavaScript; no UI framework or external font dependency.

Use a dark navy canvas, subtle grid and cyan accents. Keep the network as the landing view. Fine borders and restrained node emphasis suggest a technical instrument without flashing, scanning animations or decorative motion. Preserve readable system typography; reserve monospace for counts and small section labels.

- Background: `#080f1b`; panel: `#101c2d`; elevated surface: `#142339`.
- Main text: `#eaf1fc`; secondary text: `#a9bbd1`; links: `#99beff`; accent: `#6ce8d7`.
- Control borders: `#526b8a`; focus: three-pixel cyan outline with separation.
- Compact four/eight-pixel spacing; desktop construction sidebar and graph stage collapse to a single column on smaller screens.
- Native controls, visible labels, wrapping tabs, skip link, accessible edge tables, keyboard-operable nodes and dialogs.
- Roles use names and colors. Multiple roles remain multiple; never invent a primary role. Colors and filters use report-associated roles, not specialties or the analytical union.
- Construction controls change the graph; display controls change visibility. Retain complete constructed-network exports.
- Keep raw hashes, internal UUIDs and raw provenance JSON out of normal UI. Downloads and validation retain exact identifiers and integrity checks.
- Restrained color transitions; respect reduced motion. No external analytics, fonts, credential entry or model calls in the browser.

Review at 375, 768, 1024 and 1440 CSS pixels. Check contrast, focus, wrapping, actor/edge drill-down, role filters, deep links, downloads, and local loading. Recompute all six study projections after shared-code changes.

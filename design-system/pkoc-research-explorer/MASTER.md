# PKOC UNMIL Network Explorer design system

Applied UI/UX Pro Max reference: `hud-sci-fi-fui` (HUD / Sci-Fi FUI), adapted to a research dashboard. Plain HTML, CSS and JavaScript; no UI framework or external font dependency.

Use a dark navy canvas, subtle grid and cyan accents. Keep the network as the landing view. Fine borders and restrained node emphasis suggest a technical instrument without flashing, scanning animations or decorative motion. Preserve readable system typography; reserve monospace for counts and small section labels.

- Background: `#080f1b`; panel: `#101c2d`; elevated surface: `#142339`.
- Main text: `#eaf1fc`; secondary text: `#a9bbd1`; links: `#99beff`; accent: `#6ce8d7`.
- Control borders: `#526b8a`; focus: three-pixel cyan outline with separation.
- Compact four/eight-pixel spacing; desktop construction sidebar and graph stage collapse to a single column on smaller screens.
- Native controls, visible labels, wrapping tabs, skip link, accessible edge tables, keyboard-operable nodes and dialogs.
- Use the displayed product name PKOC UNMIL Network Explorer. Retain established repository/Pages URLs, generic toolkit naming and bundle identifiers.
- Roles use names and colors. Multiple roles remain multiple; never invent a primary role. Colors and filters use report-associated roles, not specialties or the analytical union. The CAMEO appearance toggle turns colors and the legend on/off together without changing role selection, assignments or network construction.
- Construction controls change the graph; display controls change visibility. Retain complete constructed-network exports.
- Expose Hide isolates directly among graph display controls. Explain that it hides degree-zero actors; the native roster and analytical exports retain them.
- Keep raw hashes, internal UUIDs and raw provenance JSON out of normal UI. Downloads and validation retain exact identifiers and integrity checks.
- Give the graph most of the available width and place a readable actor/edge inspector beside it on wide screens, both normally and in full screen. Stack the inspector below on smaller screens. Keep its heading and selection visible; avoid clipping text to preserve graph width.
- Use screen-sized labels with halos, collision-aware smart labels, explicit all/selected modes, pointer dragging and arrow-key node movement. Remove directional movement buttons. Offer an accessible click-position alternative to dragging, and retain keyboard operation and clear focus.
- Offer Paper, Circle, Random and 3D sphere layouts. Keep their controls distinct from branch, scale and source selection. Layout coordinates and sphere depth are presentation state only, with no inference of political distance. Avoid continuous animation; respect reduced motion.
- Use a visibly differentiated, bounded node-size scale based on constructed-network degree. State that degree means connected actors. Visibility filters do not recalculate that measure; perspective must not obscure its meaning.
- Provide SVG and PNG exports of the current graph view, including visible labels and its CAMEO state. Keep image actions separate from complete network downloads. Images omit controls and inspector; document that hidden nodes remain in table/GraphML exports.
- Research workflow begins with a connected, responsive framework linking corpus preparation, sequential annotation, L's executed model workflow, A's human-reviewed continuation, and shared three-scale projection. Link stages to detailed explanations and supply a readable text sequence. Distinguish annotation decisions that change incidence from actor attributes that characterize the nodes.
- Remove the interactive Reference audit view and R actor routes. Retain a short historical scope disclosure in research methods and preserve frozen R records/downloads. Old view links resolve to Research workflow. Reusable toolkit outputs remain explicitly model-only.
- Contact uses Krerkkaiwan Kajohnkunchonlathorn, Krerkkaiwan.k@cib.go.th, and the approved [LinkedIn profile](https://www.linkedin.com/in/police-major-krerkkaiwan-kajohnkunchonlathorn-872a91176/). Keep contact links visibly named; email opens a mail client, and the external profile opens with safe link attributes.
- Retain the original navy-and-cyan dark theme as the first-visit default. Offer an explicit, keyboard-accessible light/dark action in the header and full-screen graph toolbar, saving the preference locally. Light mode uses offwhite graph surfaces, slate text, teal accents, and dark outlines around the unchanged CAMEO category fills. Match exported images to the active theme. Appearance changes must not rerender or reset graph state.
- Restrained color transitions; respect reduced motion. No external analytics, fonts, credential entry or model calls in the browser.

Review at 375, 768, 1024 and 1440 CSS pixels. Check contrast, focus, wrapping, actor/edge drill-down, each layout, role display/filter independence, isolate visibility, deep links, SVG/PNG output, full screen, contact links and local loading. Recompute all six study projections after shared-code changes. Keep the frozen annotation and network snapshots unchanged.

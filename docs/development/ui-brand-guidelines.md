# Forest Keeper Web UI — Stage 5.1

Scope: [issue #23](https://github.com/SergeyRassohin/Forest-Keeper/issues/23), separate from Stage 6.
The accepted Stage 5 engine, APIs, model, evidence, lifecycles and permission matrix are unchanged.

## Brand source and shared tokens

Public reference verified 22 October 2026:
<https://forest-keeper-data.sergey-rassohin0511.chatgpt.site/>.
The same published `/favicon.svg` and `/assets/forest-dark.jpg` are retained locally under
`frontend/public/brand/`. No remote font, image or CDN is needed by the application.
The presentation's pine/moss/sage/cream direction is preserved. Amber is reserved for the
existing logo, current-section accent, keyboard focus and warnings.

`frontend/src/tokens.css` is the application theme: background/surface/muted surface,
primary/secondary text, border, pine/deep/sage, success/warning/danger/info/focus, spacing,
radii, typography, control height, table density and shadows. CSS contains component layout;
components share StatusBadge, DataValue, Identifier and EmptyState from `ui.tsx`.

Working surfaces are cream/light; the forest remains in the navigation and sign-in identity.
The workspace is a working tool, not a marketing landing page. System fonts keep offline use
available. The original site uses Inter; the matching family is preferred when locally installed.

## Inventory and navigation

| Existing surface | Presentation / actual flow |
| --- | --- |
| Login / session loading / connection error | Branded split view, labelled form, readable error, cleared password and retry |
| Overview / dependency health | Real API/PostgreSQL/Redis responses, no invented business metrics |
| Sources / import / upload / completed notice | Consistent controls and one primary upload action |
| Import detail / raw records / parse errors | Original file metadata, field/value layout, real pagination |
| Normalization / history / raw vs normalized / quality | Remains inside import detail, where the current product creates it; rules/JSON are expandable |
| Matching setup / history / candidates / detail | Source selection, readable statuses, secondary IDs, two source cards and evidence |
| Existing matching identity review | Unchanged REVIEWER/DATA_OWNER-only permission and required reason; not Conflict Decision |
| Conflict history / list / detail | Attribute/source first, raw and normalized values side by side, Basis in advanced disclosure |
| Users / roles | Separate navigation section; creation shown only with user.manage and role.assign |
| No assigned role / empty / loading / error / success | Explicit next step, text as well as color, no fake records or actions |

Navigation stays stable: overview → import/normalization → matching → conflicts → users.
Current section uses aria-current. The actual existing normalization workflow is retained;
a duplicate page or new backend endpoint is not invented. All server permission checks remain.

## Evidence and accessibility

Full raw, source, original checksum, position, normalized values, rule/profile/engine and
normalization origins remain available. Advanced technical details are expandable rather than
primary-page JSON. No fact is rewritten to make a prettier demonstration. Forest Codex remains
explicitly unconfigured. Conflict != Decision; no Stage 6/7 action is added.

Controls have visible focus and labels, keyboard-operable disclosures, 44px button/label targets,
text statuses and scrollable keyboard-focusable tables. Desktop targets are1920×1080,
1440×900,1280×800,1024×768; narrow390px is also tested. Horizontal table scrolling is allowed;
page-level horizontal overflow is not. Automated WCAG2/2.1 A/AA checks supplement manual visual
review; they do not claim a formal accessibility certification.

## Real screenshot capture

Build current backend/frontend images using the normal setup first, then:

```bash
FK_ENV_FILE=.env bash scripts/capture-ui-gallery.sh
```

In a managed cloud environment keep the existing proxy/CA build adapter. Image names can be
selected with FK_GALLERY_BACKEND_IMAGE/FK_GALLERY_FRONTEND_IMAGE; FK_GALLERY_PORT defaults18446.
The script starts a uniquely named disposable Compose project with its own PG/Redis/files,
prepares temporary owned accounts, imports `tests/data/ui-gallery/catalog.csv` and `onec.xml`,
and drives the real HTTPS Web Client. A complete gallery replaces the previous output only
when all checks pass. The script exits non-zero on failure and removes only its own project,
volumes and accounts. It refuses to overwrite another browser-account fixture.

Credentials are generated privately under ignored deploy/local/e2e.json; no public demo password
is published. Source names/values are deterministic synthetic catalogs. Execution IDs/timestamps
are real and may differ between captures. The manifest records exact source/tree hashes,
resource checksums, PNG checksums, accessibility and viewport results.

Output: `frontend/public/interface/index.html` and PNG/manifest files, served at `/interface/`.
`python scripts/check-ui-gallery.py` rejects missing, modified or stale screenshots. Recapture
when frontend source or branding changes. Do not manually draw or retouch application images.

The original hosted site's source/publishing tool is not available in this environment.
A complete static interface page is prepared in this repository for publication there; do not
claim its historical domain has been updated until the owner publishes it or provides access.

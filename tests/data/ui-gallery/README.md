# Stage 5.1 screenshot fixture

Synthetic material catalogues, not a customer export. `catalog.csv` is FILE; `onec.xml` uses the documented synthetic ONE_C profile. Both use the current `synthetic-material v1` normalization and current matching profile; no production profiles or business rules are modified.

Five source records each: MAT-001 exact identity with mass12500g vs12.4kg (12.5 vs12.4kg normalized); MAT-002 equivalent1kg; MAT-003 missing mass vs3kg; MAT-004 equivalent2kg; MAT-005 spelling variation generates a POSSIBLE_MATCH requiring identity review. Automatic matching does not confirm that last pair. Conflict screenshots show real persisted findings for confirmed exact pairs, with no Conflict Decision action.

Run `FK_ENV_FILE=.env bash scripts/capture-ui-gallery.sh` after building the images. It creates a unique disposable test project and generates private accounts for ADMIN/REVIEWER/VIEWER/NO_ROLES. Their temporary logins/passwords exist only in ignored `deploy/local/e2e.json` during capture and are removed by owner-run cleanup; no public demo password is committed. The Playwright script performs login itself. Use your own bootstrap administrator for manual application review.

Gallery output, source/bundle/image checksums, WCAG and responsive results: `frontend/public/interface/`. Record ordering and generated IDs/timestamps can vary; the synthetic records and business states are fixed. Loading and connection failure are explicitly controlled browser-request fixtures, labelled as such in the gallery. See [brand/capture guide](../../../docs/development/ui-brand-guidelines.md).

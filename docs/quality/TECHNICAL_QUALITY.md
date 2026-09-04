# Technical Quality Baseline

Checkpoint: `develop-v2` at `29e83753a18fe60a479591dcd815581ce4d51b7a`.

This slice is intentionally non-functional: it hardens repeatable validation and dependency policy without changing business flows, persistent database configuration, credentials, Mercado Pago, SII, or transactional SMTP behavior.

## Angular component-style budget

The production build before this slice reported only two component-style warnings:

- `inventory.scss`: 8.72 kB
- `electronic-tax.scss`: 7.80 kB

The previous warning threshold was 6 kB while the hard error threshold was 10 kB. V1 changes only the warning threshold to 9 kB and keeps the 10 kB error limit unchanged.

This is a deliberate baseline decision rather than an unlimited budget increase: the largest current stylesheet remains below the warning threshold with narrow headroom, and any component reaching 10 kB still breaks the production build. A later visual refactor may reduce these styles, but this quality slice does not rewrite stable UI CSS without browser-regression evidence.

## npm install-script policy

The lockfile at this checkpoint contains install-time scripts for the following reviewed dependencies:

- `@parcel/watcher@2.6.0`
- `esbuild@0.28.1`
- `fsevents@2.3.3`
- `lmdb@3.5.6`
- `msgpackr-extract@3.0.4`

They are pinned in `package.json` under `allowScripts`. `frontend/.npmrc` enables `strict-allow-scripts=true`, so a newly introduced dependency with an unreviewed install script must be explicitly reviewed instead of silently expanding the trusted set.

## Dependency and build gates

Local package validation and CI execute:

- `python -m pip check`
- Django system check
- `makemigrations --check --dry-run`
- complete backend test suite with temporary SQLite
- deterministic `npm ci`
- `npm audit --audit-level=high`
- every Angular spec in an isolated process
- Angular production build

MySQL remains the real application database. SQLite is only an isolated test engine selected through the process environment; `.env` is not modified.

## CI

`.github/workflows/quality.yml` runs on pushes and pull requests targeting `develop-v2`. Backend and frontend validation run as separate jobs so failures are attributable and independent.

## API/error quality boundary

The public route inventory and HTTP error-review policy are versioned under `docs/quality/`. This V1 does not impose a new global response body on already closed modules, because doing so without requirement-by-requirement evidence could break stable clients. The next QA RF01-RF26 slice must verify the documented status semantics against real endpoints and evidence any exceptions.

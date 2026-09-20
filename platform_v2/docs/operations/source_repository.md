# Source repository and local setup

The private `sandroabashishvili/SmartSignalHub` repository versions the application
source at `~/SmartSignalHub`. The nested `publish/Bitcoin-Live-Signals` repository
is independently managed and ignored by the source repository. Its public `main`
branch continues to serve GitHub Pages. Never change its origin to the source repo.

## Included

- Spot, Futures, Hedge and shared Python modules; tests and reviewed fixtures.
- Tools, news generators, CSS, JavaScript, static assets and maintained HTML pages.
- Active documentation under `platform_v2/docs` and module documentation.
- Pinned Python dependencies and an empty `.env.example`.

## Kept local

`.env`, credentials, SQLite files and their journal companions, runtime state,
logs, generated dashboards/news editions, cache directories, virtual environments,
backup archives, generated videos and the nested publication checkout. Ignoring
files does not delete them. Source history is not a backup of trading data.

## Fresh machine

```bash
gh repo clone sandroabashishvili/SmartSignalHub ~/SmartSignalHub
cd ~/SmartSignalHub
python3.12 -m venv venv
source venv/bin/activate
pip install -r platform_v2/requirements.txt
cp .env.example .env
```

Some dependencies need platform-specific native libraries; consult installation
errors for TA-Lib, media and scientific dependencies. Publication uses Git/rsync;
media workflows can require FFmpeg. Restore runtime databases separately if
continuing an existing experiment. Do not reset an existing installation merely
to load source changes. The runtime launcher is simulation-oriented, but an
explicit launch can fetch market data and create runtime state:

```bash
python3 -m platform_v2.tools.runtime_start_system
```

## Optional public website publication

```bash
mkdir -p publish
git clone https://github.com/sandroabashishvili/Bitcoin-Live-Signals.git publish/Bitcoin-Live-Signals
python3 -m platform_v2.tools.github_publish_system --dry-run
```

Review the output and generate the required dashboards/news first. Source clones
intentionally omit generated current data. Follow the normal publication runbook;
never upload the source repository or `.env` as GitHub Pages content.

## Source changes

```bash
git status --short
git diff
git add <reviewed-files>
git diff --cached --stat
git commit -m "Describe the source change"
git push origin main
```

Review staged contents for credentials and runtime files before every push.
Source commits and public website commits are separate operations.

## Initial source-import verification (2026-09-20)

726 files selected (approximately 8.3 MB). Reviewed the Git index for local secret
values, common credential formats, private-key headers and forbidden runtime paths;
no matches found. An exported index was tested independently of the working
runtime directory: 310 tests passed. MoviePy emitted 90 existing ImageIO
deprecation warnings. This check reused the installed Python environment; it is
not evidence of a fresh dependency installation on another operating system.

The old ignore rule for `video_reels/output/` was removed because that directory
contains the imported Python subtitle writer, not merely generated media. Active
documentation is now tracked. Existing Markdown hard breaks and cosmetic legacy
whitespace were retained during the initial source import.

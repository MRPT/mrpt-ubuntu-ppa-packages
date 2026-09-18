# AGENTS.md — mrpt-ubuntu-ppa-packages

Builds and publishes `.deb` packages of MRPT to Launchpad PPAs. This repo
(github.com/MRPT/mrpt-ubuntu-ppa-packages) only holds the packaging glue; the
actual MRPT source is pulled from github.com/MRPT/mrpt at build time.

## Status (2026-09): mid-migration from MRPT 2.x to 3.x

MRPT 3.x switched to a modular, colcon-orchestrated build (see
`~/code/mrpt-salsa/agents.md` for MRPT 3.x itself). **Nothing in this repo
has been ported yet** — every `debian/` branch here still packages MRPT 2.x
(plain CMake, package names like `libmrpt-core2.15`). This is why the nightly
develop-branch cron job on the publish server is currently disabled (see
below). Porting these branches to the 3.x colcon build is the main open task.

`~/code/mrpt-salsa/debian/` is a **working, up-to-date reference**: it's the
Debian-unstable (salsa) packaging already ported to MRPT 3.x colcon builds
(package names like `libmrpt-core3.1`). Use it as the template when porting
this repo's `debian/` branches — the module list, `.install` files,
`colcon-defaults.yaml` override, and `debian/rules` colcon invocation should
transfer with adaptation (this repo builds via plain `debuild`/PPA, not
`gbp buildpackage`; no `salsa`-specific bits).

New target PPAs (replacing the old `ppa:joseluisblancoc/mrpt` /
`mrpt-stable`):
- `ppa:joseluisblancoc/mrpt3-develop` — https://launchpad.net/~joseluisblancoc/+archive/ubuntu/mrpt3-develop (created)
- `ppa:joseluisblancoc/mrpt3-stable` — not created yet

Target distros going forward: **Ubuntu 24.04 (noble) and 26.04 (resolute)
only.** Older distro branches (bionic/focal/jammy/impish/kinetic/lunar/
mantic) are legacy/EOL and not in scope for mrpt3.

## Repo layout: one git branch per Ubuntu distro

This repo intentionally keeps unrelated history per branch:

- **`main`** — the build driver: `build-mrpt-deb-pkg.sh`, `docker/` (local
  test containers for building against Debian sid/experimental), this file,
  `README.md`. No `debian/` directory here.
- **`bionic`, `focal`, `jammy`, `jammy2`, `noble`, `resolute`, `impish`,
  `kinetic`, `lunar`, `mantic`** — each contains *only* a `debian/` directory:
  the full Debian packaging recipe (`control`, `rules`, `changelog`,
  per-package `.install` files, `copyright`, `watch`) for that specific
  Ubuntu codename. `jammy`/`noble`/`resolute` are the currently relevant
  ones; the rest are old EOL-distro packagings kept for history.
- **`cron-scripts`** — the two scripts (`run_mrpt-develop.sh`,
  `run_mrpt-master.sh`) that the publish server runs on a schedule.
- **`docker-deployment`** — older Docker-based build experiment (superseded
  by `docker/` on `main`).

There is no `debian/` on `main`; `build-mrpt-deb-pkg.sh` pulls the right one
at build time with `git archive --format=tar origin/${DISTRO} debian | tar -x ...`.

## Build flow: `build-mrpt-deb-pkg.sh`

Run from a checkout of *this* repo, on `main`, with an `upstream` remote
pointing at github.com/MRPT/mrpt.git:

```
./build-mrpt-deb-pkg.sh -g <upstream git tag|branch> [-d <distro-codename>] [-s]
```

1. Adds/uses the `upstream` MRPT remote, checks out `upstream/<GIT_TAG>`
   (e.g. `develop`, `master`, or a release tag) with submodules.
2. Runs `packaging/make_release.sh` from *that* MRPT checkout to produce a
   signed, reproducible source tarball in `$HOME/mrpt_release/` (this script
   lives in the MRPT source repo itself — see the working copy at
   `~/code/mrpt-salsa/packaging/make_release.sh` for what it does: reads the
   version from `modules/mrpt_common/package.xml`, optionally appends a
   snapshot suffix `-s`, sets `SOURCE_DATE_EPOCH`).
3. Restores `main`, extracts the tarball, symlinks it to a `.orig.tar.gz`.
4. Grafts in `debian/` from `origin/<distro>` (this repo) into the extracted
   tree, bumps `debian/changelog` with `debchange`, and runs
   `debuild -S -sa -d` (source-only, signed — Launchpad does the binary
   builds).

`packaging/make_release.sh`, `parse_mrpt_version.sh`, and
`generate_snapshot_version.sh` are **not** part of this repo — they live
upstream in github.com/MRPT/mrpt (`packaging/`). Check that directory (or
`~/code/mrpt-salsa/packaging/`, same content) if the release/versioning logic
needs to change; it is out of scope for edits here.

## Publish server: `ingmec.ual.es`, user `mrptppa`

SSH passwordless as `jlblanco`; `mrptppa`'s files are mostly not readable by
`jlblanco` (permission denied on `.bash_history`, no passwordless `sudo -u
mrptppa`), so anything not listed here needs the user to check directly as
`mrptppa` or via `sudo`.

**Layout under `/home/mrptppa/`:**
- `mrpt/` — checkout of github.com/MRPT/mrpt tracking branch `develop`.
- `mrpt-master/` — checkout tracking branch `master`.
- `mrpt-ubuntu-ppa-packages/` — this repo, checked out on branch
  `cron-scripts`.
- `cron/run_mrpt-develop.sh`, `cron/run_mrpt-master.sh` — symlinks into
  `mrpt-ubuntu-ppa-packages/` (so `git pull` on that branch updates the live
  scripts; each script self-updates by `git pull`-ing its own branch at the
  end of every run).
- `.mrptppa.sha`, `.mrpt-master-ppa.sha` — cache of the last-built commit SHA
  per script, so a run is a no-op if upstream has no new commits.
- `.mrptppa.lock`, `.mrpt-master-ppa.lock` — per-script lockfiles (stale
  after 2h are auto-removed) to avoid overlapping runs.
- `.dput.cf` — only defines a stanza for the legacy `ppa:joseluisblancoc/mrpt`
  (ftp/anonymous upload to `ppa.launchpad.net`). The `mrpt-stable` target used
  by `run_mrpt-master.sh` has **no matching stanza**, so it relies on dput's
  built-in generic handling of `ppa:` targets. When adding `mrpt3-develop` /
  `mrpt3-stable`, decide whether to add explicit `.dput.cf` stanzas or
  continue relying on the generic path — verify an actual upload works
  either way.
- `.gnupg*` (plus two backup dirs) — the GPG key used by `debuild -S -sa` to
  sign source packages for Launchpad. Multiple `.gnupg.bck.*` dirs suggest a
  past key rotation; the currently active key is whatever `~/.gnupg` holds.

**Crontab (`mrptppa`, confirmed by the user directly, `MAILTO=jlblanco@ual.es`):**
```
#00 */12 * * * /home/mrptppa/cron/run_mrpt-develop.sh  # disabled for 3.0!!
50 */12 * * * /home/mrptppa/cron/run_mrpt-master.sh
```
- **`run_mrpt-develop.sh` is commented out** — the nightly/twice-daily
  `develop`-branch build (old target: `ppa:joseluisblancoc/mrpt`, looping
  over `jammy`/`noble`/`resolute`) is **off** because it doesn't work against
  MRPT 3.x yet. Re-enabling this (pointed at the new `mrpt3-develop` PPA) is
  the main goal of the migration.
- **`run_mrpt-master.sh` still runs every 12h** (`:50`), building the
  `master` branch and uploading to `ppa:joseluisblancoc/mrpt-stable` for
  `jammy`/`noble`/`resolute`. Since `master` in the MRPT repo is presumably
  still pre-3.x (or only just transitioning), confirm what this is currently
  actually publishing before repurposing it for `mrpt3-stable`.

Both cron scripts share the same shape: lockfile guard → `git pull` the
source checkout → skip if SHA unchanged → `git clone` a fresh copy of
*this* repo (always `origin/main`, i.e. always picks up the latest
`build-mrpt-deb-pkg.sh`, but the `-d <distro>` branch is fetched from
`origin` too so branch updates here take effect immediately) → build +
`dput` per distro → update SHA cache → clean up → self-update.

## Local test containers (`docker/`, on `main`)

`Dockerfile.sid` / `Dockerfile.exp` build Debian sid/experimental images with
MRPT 2.x-era build deps installed (`rebuild-docker-images.sh` builds both).
`test-mrpt-salsa-build*.sh` mount `~/code/mrpt-salsa` and run
`gbp buildpackage` inside — these are for testing the salsa/Debian packaging,
not this repo's PPA packaging directly, but useful to validate a ported
`debian/` tree builds before pushing it to a distro branch here. The
build-dep list in both Dockerfiles is stale (2.x-era); it will need updating
to match `~/code/mrpt-salsa/debian/control`'s `Build-Depends` (colcon,
`libcli11-dev`, `libexprtk-dev`, `libzstd-dev`, `libglew-dev`, `xvfb`,
`xauth`, etc.) once the 3.x port starts.

## Instructions for AI agents

- Don't use `cd foo && git ...`; use `git -C foo ...`.
- Branches here have deliberately unrelated/unmerged history (each
  `debian/`-only branch is its own lineage). Don't merge branches into each
  other; port changes by editing the target branch's files directly.
- Don't SSH-execute anything destructive or upload-triggering on
  `ingmec.ual.es` (crontab edits, `dput`, key operations) without explicit
  confirmation — that server is the live publish pipeline.

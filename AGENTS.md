# AGENTS.md — mrpt-ubuntu-ppa-packages

Builds and publishes `.deb` packages of MRPT to Launchpad PPAs. This repo
(github.com/MRPT/mrpt-ubuntu-ppa-packages) only holds the packaging glue; the
actual MRPT source is pulled from github.com/MRPT/mrpt at build time.

## Status (2026-09): MRPT 3.x packaging ported, publish cutover pending

`noble` and `resolute` now carry MRPT 3.x packaging (colcon build,
`libmrpt-*3.2` binary packages). The previous MRPT 2.x state of each is
preserved verbatim on `noble-mrpt2.x` / `resolute-mrpt2.x`. `jammy` is
untouched and stays 2.x: MRPT 3.x targets **Ubuntu 24.04 (noble) and 26.04
(resolute) only**. The other distro branches are EOL leftovers.

The 3.x packaging was seeded from `~/code/mrpt-salsa/debian/` (the Debian
unstable/salsa tree, already ported to the colcon build) and is kept as close
to it as possible, so future syncs stay a clean merge — including `Vcs-Git`,
`watch` and `upstream/`, which the 2.x branches also carried. Deltas are
deliberate and few; see "Ubuntu-specific deltas" below.

Target PPAs (replacing the old `ppa:joseluisblancoc/mrpt` / `mrpt-stable`):
- `ppa:joseluisblancoc/mrpt3-develop` — https://launchpad.net/~joseluisblancoc/+archive/ubuntu/mrpt3-develop (created; first upload landed 2026-09-23)
- `ppa:joseluisblancoc/mrpt3-stable` — created 2026-09-2x, currently empty

### Open items (as of 2026-09-23)

`noble`/`resolute` (SOVERSION 3.2 rename + `libmrpt-imgui-vendor-dev`) and
`cron-scripts` (retargets both jobs to the mrpt3 PPAs, drops jammy) are all
now pushed to `origin`. The local build validation (recipe below) confirmed
the `libmrpt-imgui-vendor-dev` `.install` globs are correct — only the
module's `LICENSES/*.txt` files come up as unpackaged in `dh_missing`
(cosmetic, non-fatal). A manual `develop`/`noble` source upload to
`mrpt3-develop` succeeded end to end on 2026-09-23.

The live server checkout (`/home/mrptppa/mrpt-ubuntu-ppa-packages`) had not
self-updated past its Dec-2025 commit as of that date, so `run_mrpt-master.sh`
on disk there still points at the legacy `mrpt-stable` PPA — it needs a
`git pull` there before the retarget takes effect.

**To do:**
1. `git pull` the `cron-scripts` checkout on the server so both cron scripts
   pick up the mrpt3 PPA retarget (currently blocked on manual action: no
   passwordless access to run non-read-only commands there was granted in
   session).
2. Re-enable the `run_mrpt-develop.sh` line in `mrptppa`'s crontab (still
   commented out, "disabled for 3.0!!"). Only the server account can do this.
3. `mrpt3-stable` cannot be fed from `master` until a release tag includes
   `mrpt_imgui_vendor` — see "master vs develop".

## Versioning rules that bite

**SOVERSION is `MAJOR.MINOR`** (`mrpt_cmake_functions.cmake`), so the
binary package names carry it: MRPT 3.2.x ships `libmrpt-math3.2`, etc. When
upstream bumps the minor version, the distro branches must be bumped in
lockstep: rename every `debian/libmrpt-*<old>.install`, and replace the
`libmrpt-*<old>` names in `debian/control` and `debian/rules`. Do **not**
blanket-replace the version string: `debian/copyright` and `debian/changelog`
contain unrelated `3.1`/`3.2` strings (license text, history). Match on
`libmrpt-[a-z0-9_-]*<old>` instead. This mirrors how the 2.x branches were
maintained (a single SOVER per branch, bumped as upstream moved).

**`debian/scripts/gen-packaging.py` is a one-shot bootstrapper, not a
regenerator.** Its output has drifted behind the hand-maintained
`debian/control`: re-running it drops `libexprtk-dev`/`xvfb`/`xauth`, reverts
`Standards-Version` and re-adds fields removed for lintian. Never wire it into
the build pipeline; edit `debian/control` by hand.

**master vs develop.** `master` is currently the 3.2.0 tag, but
`mrpt_imgui_vendor` was added on `develop` *after* that tag. The packaging
ships that module (`libmrpt-imgui-vendor-dev`), and `dh_install` fails when an
`.install` glob matches nothing — so these branches build `develop` but not
today's `master`. `mrpt3-stable` must wait for a release tag that includes
`mrpt_imgui_vendor`.

## Ubuntu-specific deltas from the salsa tree

- **noble drops `libexprtk-dev`** from `Build-Depends`: Ubuntu 24.04 has no
  such package (26.04 does). `modules/mrpt_expr/CMakeLists.txt` falls back to
  the bundled `exprtk.hpp`, which *is* present here — `make_release.sh` ships
  it as an ordinary tracked file, and only Debian's `+ds` repack strips it.
  `resolute` keeps the build-dep and is otherwise the salsa tree verbatim.
- **`libmrpt-imgui-vendor-dev`** is added on top of salsa: `mrpt_imgui_vendor`
  builds a *static* archive by design (Dear ImGui has no SOVERSION or ABI
  promise), so the `.a`, the vendored headers and the module CMake config must
  be shipped or `find_package(mrpt_imgui)` breaks for users. The blanket
  "static archives are never shipped" rule was removed from
  `debian/not-installed` accordingly.
- `debian/copyright`'s `Files-Excluded` is left untouched. It only drives
  `uscan`/`mk-origtargz` repacking, which this pipeline never runs, so it is
  inert here even though the PPA tarball does contain some of those files.

## Repo layout: one git branch per Ubuntu distro

This repo intentionally keeps unrelated history per branch:

- **`main`** — the build driver: `build-mrpt-deb-pkg.sh`, `docker/` (local
  test containers for building against Debian sid/experimental), this file,
  `README.md`. No `debian/` directory here.
- **`noble`, `resolute`** — the live MRPT 3.x packaging, one branch per
  supported Ubuntu release. Each contains *only* a `debian/` directory.
- **`noble-mrpt2.x`, `resolute-mrpt2.x`** — the MRPT 2.x packaging those two
  branches held before the port, kept for reference. They are ancestors of the
  3.x branches, so the 3.x commits were plain fast-forwards and no history was
  rewritten or force-pushed.
- **`bionic`, `focal`, `jammy`, `jammy2`, `impish`, `kinetic`, `lunar`,
  `mantic`** — MRPT 2.x packaging for now-EOL (or, for `jammy`, out-of-scope)
  Ubuntu releases, kept for history.
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
   (e.g. `develop`, `master`, or a release tag), and inits only the
   submodules that checkout's `make_release.sh` exports (parsed from its
   `EXTERNAL_MODS`, so it follows master/develop differences on its own).
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
- **`run_mrpt-develop.sh` is commented out** — the twice-daily `develop`
  build is off, disabled when MRPT went 3.x. Re-enabling it (now pointed at
  `mrpt3-develop`) is the main goal of the migration, and requires editing
  this crontab as the `mrptppa` account.
- **`run_mrpt-master.sh` runs every 12h** (`:50`), building `master`.

On the `cron-scripts` branch both scripts have been retargeted to
`mrpt3-develop` / `mrpt3-stable` with the jammy builds dropped. **Pushing that
branch takes effect on the server within one run**, because each script ends
by `git pull`-ing its own branch and `~/cron/*.sh` are symlinks into that
checkout. Do not push it before the `mrpt3-stable` PPA exists, or every run
uploads into a non-existent PPA and gets rejected.

Note the scripts only rebuild when the upstream SHA differs from the cached
one, so whether a push has an immediate effect depends on whether
`master`/`develop` moved since `.mrpt*-ppa.sha` was written.

Both cron scripts share the same shape: lockfile guard → `git pull` the
source checkout → skip if SHA unchanged → `git clone` a fresh copy of
*this* repo (always `origin/main`, i.e. always picks up the latest
`build-mrpt-deb-pkg.sh`, but the `-d <distro>` branch is fetched from
`origin` too so branch updates here take effect immediately) → build +
`dput` per distro → update SHA cache → clean up → self-update.
The `~/mrpt*` checkouts are only used for the SHA check (no submodules), and
both scripts export `GIT_TERMINAL_PROMPT=0`: a GitHub hiccup answering 401
would otherwise make a manual run stop at a `Username for 'https://github.com'`
prompt.

## Testing a branch locally before publishing

The PPA only uploads *source* packages; Launchpad builds the binaries. To
reproduce what a Launchpad builder does, assemble the same tree
`make_release.sh` would ship and build it in a stock Ubuntu container. Do not
use `~/code/mrpt-salsa` as the source: it is the `+ds` repacked tree, so it is
missing the bundled `exprtk.hpp`, libfyaml and googletest that real PPA
tarballs carry. Use a clean upstream checkout instead:

```bash
git -C ~/code/mrpt worktree add --detach /tmp/src <tag-or-origin/develop>
cd /tmp/src
# Exactly the submodules make_release.sh exports (EXTERNAL_MODS). nanoflann,
# simpleini and zlib are deliberately NOT exported: the build uses the system
# libnanoflann-dev / libsimpleini-dev / zlib1g-dev instead.
for m in modules/mrpt_gui/3rdparty/nanogui 3rdparty/googletest \
         modules/mrpt_containers/3rdparty/libfyaml 3rdparty/rplidar_sdk \
         modules/mrpt_imgui_vendor/3rdparty/{imgui,implot,portable-file-dialogs,IconFontCppHeaders}; do
  git submodule update --init "$m"
done
(cd modules/mrpt_gui/3rdparty/nanogui && git submodule update --init ext/nanovg)
rm -rf debian && git -C <this-repo> archive <branch> debian | tar -x -C .

docker run --rm --security-opt seccomp=unconfined -v /tmp:/build ubuntu:noble bash -c '
  apt-get update -qq
  apt-get install -y -qq --no-install-recommends devscripts equivs build-essential fakeroot
  cd /build/src
  mk-build-deps -i -t "apt-get -y -qq --no-install-recommends" debian/control
  DEB_BUILD_OPTIONS="nocheck parallel=$(nproc)" dpkg-buildpackage -b -us -uc'
```

Notes: `--security-opt seccomp=unconfined` is needed because `debian/rules`
wraps the build in `setarch -R`, which Docker's default seccomp profile
blocks. Mount a *parent* directory, since `dpkg-buildpackage` writes the
`.deb`s next to the source tree and they are otherwise lost with `--rm`.
`nocheck` skips the (long) test suite; drop it for a full run. Running just
`mk-build-deps` is already a fast, useful check that `Build-Depends` resolves
on that Ubuntu release.

The older `docker/` helpers on `main` (`Dockerfile.sid`, `Dockerfile.exp`,
`test-mrpt-salsa-build*.sh`) target Debian sid/experimental with a stale
MRPT 2.x-era build-dep list, and test the salsa tree via `gbp buildpackage`
rather than this repo's packaging.

## Instructions for AI agents

- Don't use `cd foo && git ...`; use `git -C foo ...`.
- Branches here have deliberately unrelated/unmerged history (each
  `debian/`-only branch is its own lineage). Don't merge branches into each
  other; port changes by editing the target branch's files directly.
- Don't SSH-execute anything destructive or upload-triggering on
  `ingmec.ual.es` (crontab edits, `dput`, key operations) without explicit
  confirmation — that server is the live publish pipeline.

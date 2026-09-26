# Manual PPA build trigger (web UI)

A tiny password-protected web page on `ingmec.ual.es` to run
`run_mrpt-develop.sh` / `run_mrpt-master.sh` on demand instead of waiting for
their next cron slot (`:50` every 12h), and watch the output live.

`trigger_server.py` is a dependency-free Python 3 stdlib HTTP server. It runs
as the `mrptppa` user (same user/environment the cron jobs already use, so no
new privilege boundary is introduced) and binds to `127.0.0.1:8765` only.
Apache reverse-proxies a Basic-Auth-protected path to it; the Python server
itself does no authentication and must never be exposed directly.

It does not change what the scripts do: like cron, a trigger is a no-op
(near-empty log) if the upstream branch has no new commit since the last
build. Concurrent triggers of the same job are deduplicated in-process, and
the underlying script's own lockfile (`~/.mrptppa.lock` /
`~/.mrpt-master-ppa.lock`) is also honored, so clicking "Trigger now" while
cron is already mid-run just shows you cron's own in-progress log.

## One-time server setup (root required)

```bash
# Apache modules (already enabled as of 2026-09, included for completeness)
sudo a2enmod proxy proxy_http

# Basic-auth credentials for this page (pick your own username)
sudo htpasswd -c /etc/apache2/mrpt-trigger.htpasswd jlblanco

# systemd service running the trigger server as mrptppa
sudo cp /home/mrptppa/mrpt-ubuntu-ppa-packages/web-trigger/mrpt-ppa-trigger.service \
    /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mrpt-ppa-trigger
sudo systemctl status mrpt-ppa-trigger   # should be active/running
```

Then hand-edit the two Apache vhosts (paste the matching block from
`apache-snippet-ssl.conf` into `000-default-le-ssl.conf`'s `<VirtualHost
*:443>`, and `apache-snippet-http-redirect.conf` into `000-default.conf`'s
`<VirtualHost *:80>`, so Basic Auth credentials are never sent over plain
HTTP), then:

```bash
sudo apache2ctl configtest
sudo systemctl reload apache2
```

The page is then at `https://ingmec.ual.es/mrpt-trigger`.

## Updating

The `mrpt-ubuntu-ppa-packages` checkout under `/home/mrptppa/` self-updates
(each cron script `git pull`s its own branch at the end of every run), so a
push to `cron-scripts` reaches the server on its own. That only refreshes the
file on disk, though — after changing `trigger_server.py` itself, restart the
service to pick it up:

```bash
sudo systemctl restart mrpt-ppa-trigger
```

## Known limitation

Triggering `master` may currently fail partway through the Debian build:
`mrpt_imgui_vendor` isn't in a release tag yet, so `master` doesn't build
cleanly with this packaging (see the main `AGENTS.md`, "master vs develop").
That's a pre-existing gap in what gets built, not a bug in this trigger tool
&mdash; the log will show exactly where `debuild` fails.

## Notes

- Logs live under `~/web-trigger/logs/` (mrptppa's home), last 15 runs per
  job kept, older ones pruned automatically.
- If the systemd service restarts while a build is mid-flight, the "last
  exit code" shown on the page is lost (only for that in-flight run); the
  log file on disk is unaffected and the lockfile-based "is it running"
  status is unaffected either way.

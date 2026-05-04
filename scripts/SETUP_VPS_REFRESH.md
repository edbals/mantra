# VPS daily-refresh setup

The Mantra dashboard reads from a SQLite DB that the IDX-API project syncs from
the Indonesian stock exchange. **Nothing in this repo refreshes that DB on its
own** — you have to schedule `scripts/daily_refresh.sh` on whatever box hosts
the dashboard. This doc shows two ways: cron (simple) and systemd (preferred
for production VPSes because of `Persistent=true` catch-up).

## Prerequisites on the VPS

- The `IDX-API` repo cloned somewhere (default expected: alongside `mantra/`).
- `deno` installed and on `PATH`.
- `python3` with the deps in `requirements.txt` installed (a venv is fine).
- `flock` (ships with util-linux on every mainstream distro).
- `mantra/config.json` pointing at the IDX-API SQLite path on the VPS.

Quick sanity check:

```bash
cd /opt/mantra
./scripts/daily_refresh.sh   # should run sync, then screener, then exit 0
```

If that works, schedule it.

## Option A — cron (easiest)

```cron
# /etc/cron.d/mantra-refresh
# IDX closes ~16:00 WIB; 17:30 WIB = 10:30 UTC.
30 10 * * 1-5  mantra  /opt/mantra/scripts/daily_refresh.sh >> /var/log/mantra-refresh.log 2>&1
```

Replace `mantra` (user) and the path to match your install. Make sure the user
can write `/var/log/mantra-refresh.log` (e.g. `touch` it and `chown` once).

## Option B — systemd (recommended)

The repo ships templates at `scripts/mantra-refresh.{service,timer}`. Edit the
`User=`, `WorkingDirectory=`, and `Environment=` lines to match the VPS layout,
then install:

```bash
sudo cp scripts/mantra-refresh.service /etc/systemd/system/
sudo cp scripts/mantra-refresh.timer   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mantra-refresh.timer
```

Verify:

```bash
systemctl list-timers mantra-refresh.timer    # next-fire time
sudo systemctl start mantra-refresh.service   # run once on demand
journalctl -u mantra-refresh.service -n 200   # see last log
```

`Persistent=true` in the timer means if the VPS was down when the job was due,
it fires as soon as the box comes back — so a server reboot won't silently
skip a day.

## Troubleshooting

- **"deno: command not found"** in the log → set `DENO_BIN=/full/path/to/deno`
  in the systemd unit (or in the cron line via an env wrapper). Cron has a
  minimal `PATH`.
- **Lock file held** → a previous run is still going. `daily_refresh.sh`
  uses `flock` on `output/.refresh.lock`; safe to leave alone, or remove
  the lock if you've confirmed nothing is running.
- **DB still stale after a run** → check `IDX_API_DIR` points at the right
  checkout, and that `config.json`'s `idxdb_path` points at the same SQLite
  file the sync writes to.
- **Holidays** (e.g. Labour Day) → the upstream API returns "No data found"
  for non-trading days; that's expected and the script keeps going.

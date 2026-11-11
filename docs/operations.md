# Operations

Running both tools day to day: backups and restores, updates, disk and retention, health
alerts, and the recorder's service, logs and spool. The deep reference is keyup's
[Operating the database](reference/keyup/OPERATIONS.md) and trunkd's
[Operating trunkd](reference/trunkd/operations.md) and
[Windows service](reference/trunkd/windows-service.md).

Commands below assume the keyup checkout is your working directory and the database container
has compose's default name, `keyup-db-1`.

## keyup

### What to back up

| What | Where | Back it up? |
| --- | --- | --- |
| The database | the `db` container's volume | **Yes.** Nightly dumps, below. |
| Original recordings | `AUDIO_ROOT` (default `/srv/keyup/audio`) | **Yes.** They cannot be recreated. |
| `.proc.mp3` processed copies | beside the originals | No. The audio worker can make them again. |
| `.env` | the checkout | Yes, somewhere private. It holds `SECRET_KEY`, the database password and any exporter or RadioReference credentials. |
| TLS certificates | the `keyup_caddy_data` volume | Optional. Losing it costs a fresh issuance, not an outage. |

A compressed dump with no indexes is small next to the live database (one archive's dump was
about 7 % of its database size). The recordings are the bulk. Plan the off-host copy around
them.

!!! warning "A copy on the same disk is not a backup"
    It protects you from a bad migration, an accidental `DELETE` or a broken container. It does
    not protect you from losing the disk. If the Docker host is a VM or container, find out
    where its disk really lives. A hypervisor snapshot on the same drive fails along with it.

Use two tiers:

1. **On the host, automated.** Nightly database dumps in `KEYUP_BACKUP_DIR` (default
   `/srv/keyup/backups/db`). Keep that directory outside the checkout, so replacing or
   re-cloning the checkout never takes the backups with it.
2. **Off the disk.** Copy the newest dump and the original recordings somewhere else: a second
   disk, a NAS, or object storage through `rclone` or `restic`. You choose the target. The
   scripts do not choose one for you.

### Nightly database backup

`deploy/backup/keyup-db-backup.sh` runs on the Docker host as root, from a systemd timer, at
02:30 host time. Each run:

- takes one consistent snapshot and counts every table in it;
- runs `pg_dump --format=custom --compress=zstd:3` at low CPU and I/O priority;
- writes `keyup-<UTC stamp>.dump`, then its manifest `keyup-<stamp>.json`, which holds the
  sha256, sizes, alembic head and the row counts. The manifest is written last, so it marks a
  successful run;
- keeps the newest 3 dumps plus the newest dump from each of the 2 previous ISO weeks.

It refuses to start unless 40 GiB stays free after the dump, and it takes a lock so two runs
never overlap. It only reads the live database.

Install the timer once, as root:

```bash
cd /path/to/keyup          # your checkout
install -m 644 deploy/backup/keyup-db-backup.{service,timer} /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now keyup-db-backup.timer
systemctl list-timers keyup-db-backup.timer        # next run
journalctl -u keyup-db-backup.service -n 20        # last run
```

The unit runs the script from the checkout named by `KEYUP_DIR` (default `/opt/keyup`). If your
checkout is somewhere else, change that line with `systemctl edit --full
keyup-db-backup.service`.

Environment knobs, all optional, set in the unit or on the command line:

| Variable | Default | Meaning |
| --- | --- | --- |
| `KEYUP_BACKUP_DIR` | `/srv/keyup/backups/db` | Where dumps and manifests go |
| `KEYUP_DB_CONTAINER` | `keyup-db-1` | The running Postgres container |
| `KEYUP_BACKUP_MIN_FREE_GB` | `40` | Free space that must remain after a dump or drill |
| `KEYUP_BACKUP_KEEP_DAILY` | `3` | Newest dumps kept |
| `KEYUP_BACKUP_KEEP_WEEKLY` | `2` | Older ISO weeks kept, one dump each |
| `KEYUP_BACKUP_COMPRESS` | `zstd:3` | `pg_dump` compression |

!!! note "`BACKUP_DIR` in `.env` and `KEYUP_BACKUP_DIR` must name the same directory"
    The backup script writes to `KEYUP_BACKUP_DIR`. The worker's `backup_stale` health check
    reads manifests through a read-only mount of `BACKUP_DIR` from `.env`. From keyup v0.1.1
    both default to `/srv/keyup/backups/db`, so a stock install needs nothing. If you move the
    dumps, set `BACKUP_DIR` in `.env` and `KEYUP_BACKUP_DIR` in the service to the same path,
    then run `docker compose up -d`; otherwise the check watches an empty directory and
    reports "no database backup … yet".

    **Installed with keyup v0.1.0?** There, an unset `BACKUP_DIR` mounted `./backups/db` next
    to `compose.yaml` instead. Upgrading to v0.1.1 fixes that, or set it yourself:

    ```bash
    # .env
    BACKUP_DIR=/srv/keyup/backups/db
    ```

    and run `docker compose up -d`.

### Copying the recordings off the host

`deploy/backup/keyup-audio-backup.sh` copies the **original** recordings to any rsync target. It
skips the `.proc.mp3` copies, the waveform cache and the upload temp directory. It never deletes
anything at the target, so a retention purge or a mistake on the host does not spread to the
copy. It does nothing until you name a target:

```bash
KEYUP_AUDIO_BACKUP_TARGET=backup@nas.example.org:/volume1/keyup-audio \
  deploy/backup/keyup-audio-backup.sh --dry-run
KEYUP_AUDIO_BACKUP_TARGET=backup@nas.example.org:/volume1/keyup-audio \
  deploy/backup/keyup-audio-backup.sh
```

Other knobs: `KEYUP_AUDIO_ROOT` (default `/srv/keyup/audio`), `KEYUP_AUDIO_BACKUP_BWLIMIT`
(KiB/s, default unlimited) and `KEYUP_AUDIO_BACKUP_SSH` (default `ssh -o BatchMode=yes`). The
dumps can go along in the same nightly job, for example
`rclone copy /srv/keyup/backups/db remote:keyup-db`. The repository ships no timer for the audio
copy. Schedule it the same way as the database timer, or with cron.

### The restore drill

A backup that has never been restored is a hope, not a backup.
`deploy/backup/keyup-restore-drill.sh [DUMP]` proves that a dump restores. With no argument it
uses the newest dump that has a manifest. It:

1. checks the dump's sha256 against the manifest;
2. refuses to start unless 40 GiB would stay free after a restore as large as the source
   database;
3. restores into a scratch database, `keyup_drill_<stamp>`, on the same server, at low
   priority;
4. compares every table's row count and the alembic head with the manifest;
5. drops the scratch database on success, failure or Ctrl-C;
6. writes `<dump>.drill.json` and exits 0 only if every table matched.

If disk space or time is short, `KEYUP_DRILL_SECTIONS=pre-data,data` skips indexes and
constraints (the counts still prove the data), and `KEYUP_DRILL_JOBS=1` halves the CPU it uses.
Run a drill after any change to the schema or the backup script, and monthly otherwise.

!!! note "Thin-provisioned disks"
    If the Docker host's disk is a thin volume and the filesystem is mounted without
    `discard`, the space the drill wrote and freed stays allocated in the pool. Run `fstrim`
    after a drill, or on a weekly schedule.

### A real restore

Use this when the database is gone or a migration went wrong. Stop the app first. Never restore
while the api or worker can write:

```bash
cd /path/to/keyup && docker compose stop api worker web edge
D=/srv/keyup/backups/db/keyup-<stamp>.dump
docker exec keyup-db-1 psql -U keyup -d postgres -c "DROP DATABASE keyup WITH (FORCE)" -c "CREATE DATABASE keyup"
docker run --rm --network container:keyup-db-1 -v /srv/keyup/backups/db:/b:ro postgres:18 \
  pg_restore -h 127.0.0.1 -U keyup -d keyup --jobs 4 --no-owner --exit-on-error /b/$(basename $D)
docker compose up -d        # migrate runs first; a dump from an older head is upgraded
```

The database loses everything recorded between the dump and the failure. The audio for those
calls is still on disk, and `keyup ingest scan` can re-read what file names and tags carry.
Metadata that existed only in the database (per-source radios, talker aliases, quality
reports) does not come back that way. Assume the window since the last dump is lost.

### Updating keyup

```bash
scripts/update.sh              # git pull --ff-only, then build, migrate, restart
scripts/update.sh --no-pull    # deploy whatever is checked out now
scripts/update.sh --no-build   # reuse images already built
make update                    # same as scripts/update.sh
```

Each step can fail before anything live is touched:

1. **pull**: fast-forward only. Local commits or a diverged branch stop the update here.
2. **build**: builds the new images while the old containers keep running.
3. **migrate**: runs `alembic upgrade head` in a one-off container from the new image. The old
   API keeps accepting uploads during the migration. If it fails, the update stops and the old
   containers keep serving.
4. **up**: recreates the containers from the built images, then waits up to five minutes for
   `/api/healthz`.

The script never touches `.env`. **Back up the database before a release whose notes mention a
migration you cannot undo.** trunkd spools calls and retries them while the API restarts, so a
normal update loses none of its calls.

### Postgres sizing

All Postgres tuning lives as `-c` flags on the `db` service in `compose.yaml`, not in
`ALTER SYSTEM`. The memory settings depend on the host, so they come from `.env`:

| `.env` key | Postgres setting | Default | Sizing |
| --- | --- | --- | --- |
| `PG_SHARED_BUFFERS` | `shared_buffers` | `512MB` | about 25 % of the RAM Postgres can count on |
| `PG_EFFECTIVE_CACHE_SIZE` | `effective_cache_size` | `2GB` | about 60 % of it (a planner hint; allocates nothing) |
| `PG_WORK_MEM` | `work_mem` | `16MB` | per sort or hash, per query node; multiplies by every concurrent query |
| `PG_MAINTENANCE_WORK_MEM` | `maintenance_work_mem` | `128MB` | index builds, `VACUUM`, restores |
| `PG_MAX_WAL_SIZE` | `max_wal_size` | `1GB` | checkpoint spacing under bulk writes |
| `PG_SHM_SIZE` | the container's `/dev/shm` | `256m` | see below |

The defaults suit a host with about 4 GB of RAM that also runs the rest of the stack and the
`stt-cpu` speech container. For bigger hosts:

| Host RAM | SHARED_BUFFERS | EFFECTIVE_CACHE_SIZE | WORK_MEM | MAINTENANCE_WORK_MEM | MAX_WAL_SIZE | SHM_SIZE |
| --- | --- | --- | --- | --- | --- | --- |
| 4 GB | 512MB | 2GB | 16MB | 128MB | 1GB | 256m |
| 8 GB | 1GB | 4GB | 32MB | 256MB | 1GB | 512m |
| 16 GB | 3GB | 9GB | 32MB | 512MB | 2GB | 1g |
| 32 GB | 8GB | 20GB | 64MB | 1GB | 4GB | 2g |

**`/dev/shm` is not optional.** Parallel query workers pass results to each other (and parallel
hash joins keep their tables) in shared memory under `/dev/shm`. Docker's default of 64 MB is
too small: a single statistics query needed 16 MB for each of three workers and failed with
`could not resize shared memory segment … No space left on device`. A larger size costs nothing
until it is used, but it can still run out. On one archive, about 30 full-text searches running
at once used up a 1 GB `/dev/shm`. Because of that, keyup now lets only a few searches run at a
time (4 slots), each with one parallel worker. A search that waits more than 5 s for a slot gets
`503` with `Retry-After: 2`. If the error shows up in `docker compose logs db`, raise
`PG_SHM_SIZE`.

!!! note "Changing a `PG_*` value recreates the db container"
    The next `docker compose up -d` stops the database container and starts a new one, which
    means a few seconds of outage. Recorders spool and retry, so nothing is lost, but
    transcription and export jobs that are running will fail their current attempt and back
    off. Make the change while the transcription queue is short.

The fixed settings in `compose.yaml` assume an SSD (`random_page_cost` 1.1,
`effective_io_concurrency` 200). On spinning disks, set `random_page_cost` back to 4.
`log_temp_files` (10MB) and `pg_stat_statements` show which queries spill to disk, which tells
you whether `PG_WORK_MEM` needs raising:

```bash
docker exec keyup-db-1 psql -U keyup -d keyup -c \
  "SELECT calls, mean_exec_time::int, temp_blks_written, left(query,90)
     FROM pg_stat_statements ORDER BY temp_blks_written DESC LIMIT 20"
```

A quick look at bloat and the cache hit rate:

```bash
docker exec keyup-db-1 psql -U keyup -d keyup -c \
  "SELECT relname, n_live_tup, n_dead_tup,
          round(100.0*n_dead_tup/nullif(n_live_tup,0),1) AS pct, last_autovacuum
     FROM pg_stat_user_tables WHERE n_dead_tup > 10000 ORDER BY n_dead_tup DESC LIMIT 15"

docker exec keyup-db-1 psql -U keyup -d keyup -c \
  "SELECT round(100.0*blks_hit/nullif(blks_hit+blks_read,0),1) AS cache_pct,
          pg_size_pretty(temp_bytes) AS temp, stats_reset
     FROM pg_stat_database WHERE datname='keyup'"
```

### Disk and retention

Recordings grow every day. Watch the growth and decide on retention before the disk decides for
you.

**Retention.** Retention is set in **Admin → Settings → Retention**, and a retention policy for a
system or talkgroup overrides the global defaults. The `.env` values are only the starting
defaults:

| Setting | Default | Meaning |
| --- | --- | --- |
| `RETENTION_KEEP_DAYS` | `0` (keep for ever) | Delete calls older than this |
| `RETENTION_KEEP_AUDIO_DAYS` | `0` (never) | Purge the audio after this many days, keep the row and transcript |
| `RETENTION_KEEP_TRANSCRIPTS` | `true` | Keep transcripts when audio is purged |
| `RETENTION_ARCHIVE_PATH` | blank (delete) | Move purged audio here instead of deleting it |
| `RADIO_EVENTS_KEEP_DAYS` | `90` | Registration and affiliation (presence) events; see [Legal and privacy](legal-privacy.md). Not in `.env.example`; add the line. |
| activity log (`activity_retention_days`) | `30` | The diagnostic activity log |
| `CRON_RETENTION` | `20 3 * * *` | When the nightly pass runs |

Call retention ships at "keep for ever", so with no policy set the archive grows without limit.
Test a new window before the nightly pass applies it:

```bash
docker compose exec api keyup retention run --dry-run
docker compose exec api keyup retention run
```

The first time you apply a window to a large archive, run the pass by hand at a time you choose,
so it does not surprise you at 03:20.

**Per-talkgroup switches.** A talkgroup with **Record** off keeps its transcript and metadata but
discards the audio. With **Record** and **Transcribe** both off, and no exporter selecting the
talkgroup, keyup tells recorders not to send it at all.

**Disk alerts.** The worker samples free space every five minutes on `AUDIO_ROOT`, any archive
path and any `DISK_WATCH_PATHS` (comma-separated; not in `.env.example`, add the line). It raises `disk_low` once per crossing: a warning below 15 %
or 30 GB free, and critical below 5 % or 10 GB. These are runtime settings. `GET /api/status`
shows free space, the growth rate and the estimated days until full.

**Hard floor.** Below `UPLOAD_MIN_DISK_FREE_BYTES` (5 GiB) free under `AUDIO_ROOT`, every upload
is refused with `507` and `Retry-After`. At that point recording has stopped, which is why the
`disk_low` alert fires much earlier.

### Health alerts and monitoring

The worker checks these every minute. It raises each condition **once** and clears it once the
condition has been good for five minutes. The thresholds are under **Admin → Settings → Health**,
and `0` turns a check off.

| Check | Fires when | Default |
| --- | --- | --- |
| `recorder_silent:<instance>` | a *hot* recorder has stopped reporting | 5 min |
| `ingest_lag` | no call recorded at all | 20 min |
| `stt_backlog` | the oldest live transcription job has waited this long | 30 min |
| `backup_stale` | the newest manifest in `BACKUP_DIR` is older than this | 30 h |

Raising or clearing a condition writes a `system.health` activity row and sends a delivery to
every enabled alert rule of kind **`health`**, over webhook, Discord, ntfy or email.
`GET /api/status` lists the raised conditions under `health`, and the status panel shows them as
a banner.

Nothing checks the checker: if the worker itself is down, no alert fires. Probe
`GET /api/healthz` from **another machine** (Uptime Kuma, or a cron `curl`):

```bash
curl -fsS https://archive.example.org/api/healthz
curl -s  https://archive.example.org/api/status | jq '{health, disk}'
```

## trunkd

### Service management

=== "Linux (systemd)"

    The shipped unit runs `/usr/local/bin/trunkd --config /etc/trunkd/trunkd.toml` as the
    `trunkd` user and restarts it on failure.

    ```bash
    sudo systemctl status trunkd
    sudo systemctl restart trunkd
    sudo systemctl stop trunkd       # clean: open calls finish, queues drain
    journalctl -u trunkd -f
    ```

    The unit stops trunkd with SIGINT, the same clean shutdown as Ctrl+C. trunkd does not
    catch SIGTERM, so a plain `kill` ends it at once. Send `kill -INT` instead. Use
    `systemctl edit trunkd` to change paths, add an `EnvironmentFile=` for the upload token, or
    set `Nice=`. If you keep the config or spool outside `/etc/trunkd` and `/var/lib/trunkd`,
    add those paths to `ReadWritePaths=`.

=== "Windows (service)"

    From an **elevated** prompt:

    ```powershell
    cd C:\trunkd\bin
    .\trunkd.exe service status      # state, pid, start type, command line
    .\trunkd.exe service stop        # clean: open calls finish, queues drain
    .\trunkd.exe service start
    ```

    `services.msc`, `sc.exe start/stop trunkd` and `Restart-Service trunkd` do the same. The
    Service Control Manager restarts a crashed recorder after 5 s, then 30 s, then 60 s. The
    counter resets after a day without a failure.

**Validate a config** without opening any hardware:

```bash
trunkd --config /etc/trunkd/trunkd.toml check
```

**Reload the config without restarting:** `POST /api/config/reload` on the local panel rebuilds
the recording pipeline inside the same process. If the file no longer parses, the recorder logs
the error and keeps its current configuration.

### Logs

| Platform | Where |
| --- | --- |
| Linux | the journal (`journalctl -u trunkd`), plus daily files in `[server] log_dir` if you set one |
| Windows | `C:\trunkd\logs\trunkd.log.YYYY-MM-DD` (`[server] log_dir`, default `logs` next to the config) |
| Windows monitor | `C:\trunkd\logs\trunkd-monitor.log.YYYY-MM-DD` |
| Windows startup failure | `C:\trunkd\logs\trunkd-service-error.txt`, written only if the config or logging failed to load |

`[server] log_level` sets the verbosity (`error` … `trace`; `RUST_LOG` takes precedence).
Per-call lines are logged at `info`. The encrypted/clear decision and fragments dropped as noise
are logged at `debug`.

On Windows, Explorer may show a log as **0 bytes** while the service is writing to it. NTFS
updates the size only when the file is closed. Read the file with `Get-Content -Tail 50`.

The line to watch is the status line, every 10 s:

```text
INFO status site=Example County/Site 1 control="851.2000 MHz" nac=0x123 tsbk_per_s=26.8
     active_calls=0 pool=0/20 started=12 ended=12 uploaded=12 spooled=0 failed=0
     spool_mib=0.0 disk_free_mib=214093 dropped=0 voice_frames=3480 overflow=0 throughput=10.00 Msps
```

[Troubleshooting](troubleshooting.md#trunkd) explains what each field means when it goes wrong.

### Spool and disk

Calls the server has not accepted are kept as:

```text
spool/YYYY/MM/DD/<system>_<talkgroup>_<start-unix-ms>.mp3
spool/YYYY/MM/DD/<system>_<talkgroup>_<start-unix-ms>.json
```

That is audio plus a trunk-recorder-style JSON sidecar, so a spool directory is a valid archive
on its own. The spool is drained oldest-first every 30 s. Two separate limits protect the disk:

| Key | Default | Bounds |
| --- | --- | --- |
| `[uplink] spool_cap_bytes` | 1 GiB | the most trunkd will ever hold, oldest evicted first |
| `[uplink] spool_min_free_bytes` | 2 GiB | free space the volume must keep; trunkd evicts the oldest spooled calls to stay above it (`0` disables) |

Keep the spool on one volume. It depends on renames within a volume being atomic.

The other steady disk user is the raw event log (`events/`, one file per UTC day, gzipped once
the day closes). A busy site writes a couple of hundred MB uncompressed for the current day and
about 20 MB for each gzipped past day. Old files are deleted after `[recorder]
event_log_keep_days` (14). The log records which radios registered, affiliated and talked, and
when. Keep it only as long as you need it; see [Legal and privacy](legal-privacy.md).

**Record without uploading.** `[uplink] spool_only = true`, or
`TRUNKD_UPLINK__SPOOL_ONLY=true` for a single run, holds uploads while the control plane stays
connected. This is the safe way to prove reception before uploading anything. Release the hold
from keyup or from the panel (`POST /api/uplink` with `{"spool_only": false}`). Whichever writer
acted last wins.

### Health monitor

`trunkd monitor` is a small separate process of the same executable. It watches the local panel
and restarts the recorder when the recorder is alive but no longer recording. It needs the panel
enabled (`[server] enabled = true`).

| Rule | Fault | Window |
| --- | --- | --- |
| unreachable | the panel does not answer | 60 s |
| no lock | every control-following tuner reports `locked = false` | 10 min |
| failed unit | a supervised unit used up its restart budget | 30 s |
| service down (Windows) | the service stopped with a non-zero exit code | 30 s |

It never restarts twice within 2 minutes. If a fault returns within 10 minutes of a restart, the
wait doubles each time, up to 30 minutes.

=== "Linux"

    ```bash
    trunkd monitor --url http://127.0.0.1:8080 --restart-cmd "systemctl restart trunkd" --log-dir /var/log/trunkd
    ```

    `--log-dir` must be writable by the monitor's user, and that user must be allowed to run the
    restart command (root, or a sudo or polkit rule for exactly that command). trunkd ships no
    unit for the monitor, so run it under a unit or supervisor of your own. With panel tokens
    set, pass `--token`, set `TRUNKD_MONITOR_TOKEN`, or pass `--config` so the monitor reads the
    first `[server] tokens` entry.

=== "Windows"

    `trunkd.exe service install --config C:\trunkd\config\trunkd.toml --monitor` registers it as
    the `trunkd-monitor` service. An installed monitor already has `--config`, so it finds a
    panel token by itself.

### Updating trunkd

New config keys come with defaults, so an existing file keeps working. Read `CHANGELOG.md` for
anything whose meaning changed. The panel's `/about` page shows which build is running.

=== "Linux"

    ```bash
    cd trunkd && git pull && cargo build --release
    sudo install -m 0755 target/release/trunkd /usr/local/bin/trunkd
    sudo systemctl restart trunkd
    ```

    With a release binary, replace the `install` source with the downloaded file. The shipped
    unit grants real-time priority itself. If you run a binary from a checkout instead, re-run
    `scripts/grant-rt.sh` after every build, because file capabilities do not survive a
    rebuild.

=== "Windows (script)"

    `scripts\windows\update-trunkd.ps1` (PowerShell 7, elevated) fast-forwards the checkout,
    builds, runs the tests, swaps the exe, restarts both services and waits for the tuners to
    lock. If they do not lock, it rolls back.

    ```powershell
    pwsh -File scripts\windows\update-trunkd.ps1             # update if needed
    pwsh -File scripts\windows\update-trunkd.ps1 -BuildOnly  # build and test only
    ```

    | Exit | Meaning |
    | --- | --- |
    | 0 | already up to date, or deployed and the tuners locked |
    | 1 | failed: nothing changed, or the previous exe was put back |
    | 2 | built and staged as `trunkd-staged.exe`, not installed (not elevated, or `-BuildOnly`) |
    | 3 | another run is in progress |

    It needs the panel at `http://127.0.0.1:8080` (`-PanelUrl`, and `-PanelToken` if tokens are
    set). Without the panel the lock check can never pass, and every deploy is rolled back.
    The previous exe is kept as `C:\trunkd\bin\trunkd.exe.prev`.

=== "Windows (by hand)"

    ```powershell
    git pull; cargo build --release
    C:\trunkd\bin\trunkd.exe service stop        # the recorder
    Stop-Service trunkd-monitor                  # the monitor runs the SAME exe and holds it open
    Copy-Item target\release\trunkd.exe C:\trunkd\bin\ -Force
    C:\trunkd\bin\trunkd.exe service start       # starts the monitor again too
    ```

    Stop both services before copying. Otherwise Windows refuses to overwrite `trunkd.exe`, and
    the recorder comes back on the old binary without any other sign that the update failed.

### Keep the clock right

Every timestamp trunkd writes is anchored to the host clock. Keyup merges duplicate copies of a
call by time, and linked recorders refuse frames more than 30 s apart. Run NTP on every recorder,
against the same server. On Linux, check that `timedatectl` reports
`System clock synchronized: yes`. On Windows, the default time settings poll far too rarely; the
trunkd repository's `docs/windows-service.md` gives the registry and Group Policy settings.

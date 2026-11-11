# Install keyup

keyup runs as a Docker Compose stack on a Linux host. One script, `scripts/bootstrap.sh`, takes a
fresh checkout to a running archive with an admin account and a recorder token. This page walks
through it; keyup's [README](https://github.com/pwsh/keyup/blob/v0.1.1/README.md) and
[`.env.example`](https://github.com/pwsh/keyup/blob/v0.1.1/.env.example) are the reference.

<!-- Commands on this page are copied from keyup v0.1.1 README.md, scripts/bootstrap.sh,
     scripts/update.sh, docs/RECORDERS.md and docs/STT.md. Not verified on a clean host by the
     docs build. -->

## What you need

- A Linux host with **Docker** and the **Compose v2 plugin**: `docker compose version` must work,
  and the user running the script must be able to talk to the Docker daemon (be in the `docker`
  group). Install Docker from <https://docs.docker.com/engine/install/>.
- Enough memory and disk: about 4 GB of RAM for the default stack, an SSD, and a few GB of disk
  per month of audio ([Hardware](../hardware.md#the-archive-keyup)).
- Free ports **8095** and **8443** on the host (the web front door; both can be changed).

## 1. Clone and bootstrap

```bash
git clone https://github.com/pwsh/keyup.git && cd keyup
scripts/bootstrap.sh          # or: make bootstrap
```

The script works through these steps, and says what it did at each one:

1. **Configuration.** Creates `.env` from `.env.example` with a fresh `SECRET_KEY` and
   `POSTGRES_PASSWORD`, `TZ` from this host, and `PUBLIC_URL` set to
   `http://<this host's first address>:8095`. An existing `.env` is left alone.
2. **Build.** Builds the images (the first build takes several minutes).
3. **Data directories.** Creates the host directories the containers write to, owned by the
   containers' user (uid 10001).
4. **Start.** Starts the stack (database, migrations, API, worker, web, and the `edge` front door)
   and waits for it to report healthy.
5. **Transcription.** Starts the CPU transcription container (the `stt-cpu` profile). Its first
   start downloads the Whisper model (about 500 MB), so transcripts begin a few minutes later.
6. **Admin account.** Asks for the first admin's username and password.
7. **Recorder token.** Mints an upload token labelled `trunkd` and prints the `[uplink]` block to
   paste into trunkd's config. **The token is shown once**; keep it for
   [Connect trunkd to keyup](../connect.md).

It is safe to run again: an existing `.env`, admin or token is left alone, and a running stack is
not rebuilt.

**Options** (`scripts/bootstrap.sh --help` lists them all):

| Option | Effect |
| --- | --- |
| `--public-url URL` | the address recorders and browsers use for this server, instead of `http://<first address>:8095` |
| `--tz ZONE` | timezone written to a new `.env` |
| `--admin NAME` | the admin account to create |
| `--token-label LABEL` | the recorder token's label (default `trunkd`) |
| `--no-stt` | do not enable the CPU transcription profile, when transcription will run elsewhere |
| `--force-env` | replace an existing `.env` (the old one is kept as `.env.bak.<timestamp>`) |
| `--non-interactive`, `-y` | never prompt |

Unattended, the admin password comes from `KEYUP_ADMIN_PASSWORD`, or is generated and printed
once:

```bash
scripts/bootstrap.sh --non-interactive --admin admin
```

## 2. Sign in

Open `PUBLIC_URL` (`http://<this host>:8095`) in a browser and sign in with the admin account.
The API's interactive documentation is at `<PUBLIC_URL>/api/docs`.

Until a recorder sends calls the archive is empty; [Connect trunkd to keyup](../connect.md) is
next.

## 3. Settings worth knowing

All configuration lives in `.env` beside `compose.yaml`; each key is explained in
`.env.example`. After editing it, apply the change with `docker compose up -d`.

| Key | Default | What it does |
| --- | --- | --- |
| `PUBLIC_URL`, `PUBLIC_BASE_URL` | set by bootstrap | The address people and recorders reach keyup at. Used in the printed `[uplink]` block, in alert links, and (when `https`) for the Secure cookie flag. |
| `TZ` | the host's | The recorders' wall-clock zone, an IANA name such as `America/New_York`. |
| `AUTH_REQUIRE_READ` | `false` | Whether reading the archive needs a sign-in. See below. |
| `COMPOSE_PROFILES` | `stt-cpu` | Optional services to start. Blank when transcription runs on another machine. |
| `STT_CPU_MODEL`, `STT_CPU_THREADS` | `Systran/faster-whisper-small`, `0` (all) | The CPU transcription model, and how many cores one transcription may use. |
| `WEB_PORT`, `WEB_TLS_PORT` | `8095`, `8443` | The host ports of the `edge` front door (HTTP and HTTPS). |
| `AUDIO_ROOT` | `/srv/keyup/audio` | Where call audio is stored on the host. Put it on a disk with room to grow. |
| `RETENTION_KEEP_DAYS`, `RETENTION_KEEP_AUDIO_DAYS` | `0` (keep forever) | Delete old calls, or only their audio while keeping the transcript. |
| `PG_SHARED_BUFFERS` and the other `PG_*` | sized for 4 GB | PostgreSQL memory; see [Hardware](../hardware.md#the-archive-keyup). |

`STT_BACKENDS` only seeds the transcription backends on the first start; after that they are
managed in **Admin → Backends** and the database wins. See [Transcription](../transcription.md).

### Who can read the archive

**Reads are open by default** (`AUTH_REQUIRE_READ=false`): anyone who can reach `PUBLIC_URL` can
search, read and play every call. Changes always need a sign-in or a token. Transcripts can name
real people and addresses, so set `AUTH_REQUIRE_READ=true` in `.env` (then
`docker compose up -d`) before the archive is reachable by anyone you would not show every
transcript to. The bootstrap script warns about this at the end. See
[Legal and privacy](../legal-privacy.md).

### Ports

Only the `edge` container (Caddy) listens on the network: `WEB_PORT` (8095) for HTTP and
`WEB_TLS_PORT` (8443) for HTTPS. The API (8096), PostgreSQL (55440) and the CPU transcription
server (8093) are published on the host's loopback only, for local checks. HTTPS is off until you
configure it: see [TLS and reverse proxies](../tls.md).

## 4. Check that it is healthy

```bash
docker compose ps stt-cpu             # "healthy" once the model is downloaded
curl -s localhost:8093/health         # STT_CPU_PORT, published on the loopback only
```

`docker compose logs <service>` shows one service's log (`api`, `worker`, `db`, `edge`).

## Recorder tokens

The bootstrap token is for your first trunkd. Give every recorder its own, so one can be revoked
without silencing the others. Mint them in **Admin → Recorder → Connect a recorder**, or from the
shell:

```bash
docker compose exec api keyup token create trunkd --scopes upload
docker compose exec api keyup token list
docker compose exec api keyup token revoke <id>
```

[Connect trunkd to keyup](../connect.md) covers what to do with them.

## Updating

```bash
scripts/update.sh             # or: make update
```

It runs `git pull --ff-only`, builds the new images while the old containers keep serving, runs
the database migrations, restarts the stack and waits for it to report healthy. It stops at the
first step that fails, and never touches `.env`. Back up the database before a release whose
notes mention a migration you cannot undo; see [Operations](../operations.md).

## Next

- [Connect trunkd to keyup](../connect.md)
- [Configure your P25 system](../configure/radioreference.md): import sites and talkgroups
- [Transcription](../transcription.md): a GPU or an Intel accelerator instead of the CPU
- [TLS and reverse proxies](../tls.md)
- [Operations](../operations.md): backups, retention, health alerts

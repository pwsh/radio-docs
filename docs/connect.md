# Connect trunkd to keyup

trunkd uploads each finished call to keyup with one HTTP POST, authenticated by a **recorder
token**. Over the same URL and token it also reports its tuners, posts what the site announces,
and takes settings that keyup pushes back. This page gets a token, puts it in trunkd's `[uplink]`
block, and checks that calls arrive.

The reference for both sides: keyup's
[RECORDERS.md](reference/keyup/RECORDERS.md) and trunkd's
[keyup.md](reference/trunkd/keyup.md).

<!-- Commands on this page are copied from keyup v0.1.1 docs/RECORDERS.md and
     scripts/bootstrap.sh, and trunkd v0.2.2 docs/install-linux.md, docs/operations.md,
     docs/keyup.md and docs/windows-service.md. Not verified on a clean host by the docs build. -->

## 1. Get a recorder token

**If you installed keyup with `scripts/bootstrap.sh`, you already have one.** Its last step mints
an upload token labelled `trunkd` and prints a ready `[uplink]` block, addressed to `PUBLIC_URL`
from keyup's `.env`, with the token in it. The token is shown once; keyup stores only its hash.
Running the script again finds the existing token and does not mint another, so to replace a lost
one, revoke it and run the script again.

**From the browser:** **Admin → Recorder → Connect a recorder** mints an upload token and shows
the `[uplink]` block with the token already in it, addressed to whatever URL your browser reached
keyup on.

**From the shell**, on the keyup host, in the keyup checkout:

```bash
docker compose exec api keyup token create trunkd --scopes upload
# {"id": 4, "label": "trunkd", "scopes": ["upload"], "token": "kup_…"}   ← shown once
```

The `upload` scope permits exactly the recorder's own endpoints (the call upload, tuner status,
site observations, radio events and desired state) and nothing else: it cannot read the archive or
change anything. Never give a recorder an `admin` token; the key travels with every request.
**Give each recorder its own token** so one can be revoked without silencing the others:

```bash
docker compose exec api keyup token list
docker compose exec api keyup token revoke <id>
```

## 2. Put it in `[uplink]`

In `trunkd.toml` (`/etc/trunkd/trunkd.toml` on Linux, `C:\trunkd\config\trunkd.toml` on
Windows):

```toml
[uplink]
url          = "http://192.0.2.10:8095/api/call-upload"
api_key      = "kup_…"              # the token printed above
system_label = "Example System"     # becomes the keyup system name
site_label   = "Site 1"

[recorder]
instance_id = "rec-01"              # how this recorder is named in keyup
```

- **`url`** is keyup's web port (`WEB_PORT`, 8095 by default) followed by `/api/call-upload`.
  Not the API's own port 8096: that one is published on the keyup host's loopback only. trunkd
  derives every other keyup route from this one URL. If you later change `WEB_PORT` (switching
  to [HTTP-01 certificates](tls.md) sets it to 80), change the port in `url` to match.
- **`api_key`** is the token. To keep it out of the file, leave it empty and set the environment
  variable `TRUNKD_UPLINK__API_KEY` instead (on Linux, in a root-only file the systemd unit loads
  with `EnvironmentFile=`).
- **`system_label`** is the system keyup files the calls under. It **must match** the system name
  your talkgroups are filed under in keyup, or the calls start a second system. Choose it once,
  and use the same name when you import talkgroups
  ([Configure your P25 system](configure/radioreference.md)).
- **`site_label`** is recorded on every call.
- **`instance_id`** names the recorder in keyup. It defaults to the hostname; give every recorder
  its own.

**HTTPS.** Once keyup serves HTTPS ([TLS and reverse proxies](tls.md)), move `url` to
`https://<your keyup name>/api/call-upload` when convenient. It is not urgent: keyup keeps
answering `/api/…` over plain HTTP so recorders that push by IP address keep working, but until
you move, the token crosses the network unencrypted.

## 3. Check the config

```bash
sudo -u trunkd trunkd --config /etc/trunkd/trunkd.toml check
```

(on Windows: `C:\trunkd\bin\trunkd.exe --config C:\trunkd\config\trunkd.toml check`). The output
says where uploads go and whether they are held, for example:

```text
  uplink spool-only (uploads held; control plane connected) → https://keyup.example.org/api/call-upload
```

## 4. Prove reception, then release the hold

Start with uploads held, so the first calls stay on disk where you can listen to them:

```bash
sudo -u trunkd env TRUNKD_UPLINK__SPOOL_ONLY=true \
  trunkd --config /etc/trunkd/trunkd.toml run
```

The hold stops uploads only. The recorder still connects to keyup, reports its tuners every
~15 s and polls for settings every ~10 s, so it appears in keyup from its first run. That is also
how the hold can be released without touching the file:

- in **keyup**, on the **Recorder** page: each recorder's card shows *Uploading* or *Holding uploads*
  with one button to switch it;
- on trunkd's **local panel** (`[server] enabled = true`, `http://127.0.0.1:8080`), with the
  Uplink section's button, or its API:

    ```powershell
    Invoke-RestMethod -Method Post http://127.0.0.1:8080/api/uplink `
      -ContentType application/json -Body '{"spool_only": false}'   # release the upload hold
    ```

- or by running without the override (the systemd service does, unless the file sets
  `spool_only = true`).

The most recent of these wins. Releasing the hold uploads the spool, oldest call first.

## 5. Check that calls arrive

**On the recorder.** The status line every 10 s counts them: `uploaded=` rises, and `spooled=`
and `failed=` stay at 0. How trunkd treats each answer from the server:

| keyup answers | trunkd |
| --- | --- |
| `Call imported successfully.` or `duplicate call rejected` | done |
| `401 invalid key` | logs it once, keeps the call in the spool, waits 60 s before retrying |
| `incomplete call data: …` | drops the call, with an error in the log |
| anything else (5xx, timeout, keyup down) | keeps the call in the spool and retries every 30 s |

So a wrong token shows up as calls piling up in the spool with an `invalid key` line in the log,
not as lost calls.

**On keyup.** New calls appear in the web interface within seconds, filed under the
`system_label` you chose, with a transcript once the transcription backend has caught up. From a
shell on the keyup host (the API listens on the loopback, port 8096). The `/api/admin` routes
need a token with the `read` scope even from the loopback; mint one once and keep it in a
variable:

```bash
docker compose exec api keyup token create ops-read --scopes read    # prints the token once
TOKEN=kup_…                                                           # the token printed above
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8096/api/admin/ingest | jq   # ledger counts, last run
curl -s -H "Authorization: Bearer $TOKEN" 'http://localhost:8096/api/admin/ingest/files?status=failed' | jq  # and why
curl -s 'http://localhost:8096/api/calls?page_size=5' | jq '.items[] | {started_at, tgid, ingest_source, time_source}'
```

`ingest_source` is `trunkd` for calls from trunkd, and `time_source` `upload`, which means the
call's start time came from the recorder and is exact.

## Several recorders

- Give each its own token and its own `[recorder] instance_id`.
- Two recorders on the same site are fine: keyup matches the two copies of each call and keeps the
  better one. To have them share tuners rather than both record everything, set up trunkd's
  [recorder link](reference/trunkd/recorder-link.md). The two
  hosts' clocks must agree to within 30 s for the link to work.
- sdrtrunk and trunk-recorder can feed the same keyup; see keyup's
  [RECORDERS.md](reference/keyup/RECORDERS.md).

## Without keyup: any Rdio-Scanner-compatible server

trunkd's call upload is the Rdio Scanner upload contract (one `multipart/form-data`
`POST /api/call-upload` per call, in the trunk-recorder dialect). Point `[uplink] url` at any
server that accepts it, with that server's API key in `api_key`, and calls arrive with talkgroup,
radios, timing and audio.

Everything else (site observations, radio events, tuner status, remote settings, skip lists,
Broadcastify Calls delivery) is keyup's. Another server answers those routes with a 404, which
trunkd ignores; recording is not affected. To keep a recorder quiet towards a plain Rdio Scanner
server, set:

```toml
[uplink]
observations_interval_s    = 0
stream                     = false
desired_prefetch_timeout_s = 0

[recorder]
radio_events = false
```

The tuner-status POST and the settings poll still go out every 10–15 s and get a harmless 404
each.

**No server at all:** with `[uplink] spool_only = true`, calls stay in the spool on disk. Leaving
`url` empty sends nothing anywhere.

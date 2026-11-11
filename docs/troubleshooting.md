# Troubleshooting

Find the symptom, then check the causes in order. Most problems show up in one of three places:

- **trunkd's 10-second status line** (`journalctl -u trunkd -f`, or `C:\trunkd\logs\trunkd.log.<date>`);
- **the local panel**: `curl -s localhost:8080/api/status | jq`;
- **keyup's logs and status**: `docker compose logs api worker edge`, and
  `curl -s localhost:8096/api/status | jq` on the keyup host.

## trunkd

### No calls at all

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| No `device streaming` line at startup | The radio did not open | See [SDR not found](#sdr-not-found-or-dropping-samples) |
| `control="hunting"` that never ends | No control channel acquired | See [Control channel not acquired](#control-channel-not-acquired) |
| Status line shows `started` rising but `uploaded=0`, `spooled` rising | Uploads are held or failing | Check the `uplink` block below |
| `started=0` with the control channel locked | Quiet site, or every talkgroup is skipped | Wait for traffic; check `[recorder] skip_talkgroups` and the `recorder.skip_talkgroups` keyup pushes |
| `dropped_no_audio` climbing | A grant was followed but no voice was decoded, so the clear call is not posted | Check signal on the traffic channels: gain, antenna, and `snr_db` on the panel |
| `traffic pool exhausted`, `pool=20/20` | More simultaneous calls than the site's traffic pool | Raise `traffic_pool_size` in that `[[site]]` |

Check the upload state:

```bash
curl -s localhost:8080/api/status | jq .uplink
```

| `uplink` shows | Meaning | Fix |
| --- | --- | --- |
| `"spool_only": true` | The upload hold is on (`source` says who set it: `config`, `keyup` or `panel`) | Release it from keyup or the panel; the most recent writer wins |
| `stream.last_error` set, `connected: false` | The push channel to keyup is down | Check `[uplink] url` and the network; uploads still work without it |
| `url` empty | Nothing is sent anywhere | Set `[uplink] url` |

`[uplink] enabled = false` or an empty `url` keeps a recorder completely offline. `spool_only`
holds only uploads.

### SDR not found or dropping samples

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `trunkd check` lists no devices, library loaded | Module for your radio missing, or no USB permission | Linux: install the SoapySDR module and udev rules, add the service user to `plugdev`. Windows: bind WinUSB with Zadig (not for SDRplay) |
| `trunkd check` says the library is `unavailable` | SoapySDR runtime missing | Install it; the message names what to install. Unusual location: `TRUNKD_SOAPYSDR_LIB=/path/libSoapySDR.so.0.8` |
| The radio works in another program but is not listed | Another program has it open | Stop sdrtrunk, SDR# or similar. Only free radios enumerate |
| SDRplay never appears | The SDRplay API service is not running | `systemctl status sdrplay` (Linux), or start the SDRplay API service (Windows) |
| Startup error about the sample rate | Rate not supported exactly, or `sample_rate / 12500` is not an even integer of at least 4 | Use a rate from the [hardware](hardware.md) table (for example Airspy R2 `10e6`, RTL-SDR `2.4e6`) |
| Startup error about a control frequency | Frequency outside `center_frequency ± sample_rate/2` (less a 1 % guard) | Move `center_frequency` or split the site over tuners |
| `overflow` climbing, `SDR ring overflow: the DSP thread is not keeping up` | CPU cannot keep up with the sample rate | Raise `ring_seconds` (2.0 on Windows), grant real-time priority on Linux, move other work off the box |
| `throughput` well under the configured rate | USB or driver trouble, not the DSP | One wideband SDR per USB controller; shorter or better cables |
| Linux log says `no permission for real-time scheduling` | No `CAP_SYS_NICE` | Use the shipped systemd unit, or `scripts/grant-rt.sh` after each build |
| Windows: crash `0xC0000005` or exit code 1067 on clean stop, Airspy attached | libusb newer than 1.0.24 beside libairspy | Use the bundle from `build-redist.ps1`, which pins libusb 1.0.24 |
| `SoapyVOLKConverters: no VOLK config file found` | Harmless message from PothosSDR | Ignore, or run `volk_profile` |

### Control channel not acquired

`control="hunting"` means no candidate frequency has produced five valid TSBKs. It normally
locks in well under a second.

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Hunts forever, waterfall shows the carrier | Frequency error (ppm) | See [ppm and offset](#frequency-error-ppm-and-carrier-offset) |
| Hunts forever, no carrier visible | Wrong `control_frequencies`, or `center_frequency` puts them outside the capture | Check the site's current control channels; check the tuner covers them |
| Hunts, weak `rssi_dbfs` and `snr_db` on the panel | Antenna, cable or gain | Use an antenna resonant in the band; raise gain step by step; add a band-pass filter near strong pager or cellular sites |
| Noise floor jumps when gain goes up | Overload from a strong nearby transmitter | Back off `LNA` (Airspy) or add filtering. More gain is not better |
| Locked, then `control channel lost`; `tsbk_per_s` falling toward zero first | Fading signal, or the site moved to its alternate control channel | List every control frequency of the site; `[health] control_sync_timeout_secs` (30) sets when it hunts the alternates |

A healthy P25 Phase 1 control channel carries about 25–30 TSBKs per second (`tsbk_per_s`).

### Frequency error (ppm) and carrier offset

At 855 MHz, each ppm of oscillator error is about 855 Hz, and the decoder does not lock beyond a
few hundred Hz. A board that streams and shows the carrier but still hunts is almost always off
frequency.

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Works in sdrtrunk, only hunts in trunkd | sdrtrunk was correcting the error automatically | Leave `auto_ppm` on (default); it measures and corrects up to `auto_ppm_limit` (5 ppm) |
| RTL-SDR never locks | These dongles are tens of ppm off | Measure once with `rtl_test -p` or kalibrate and set `ppm` |
| Error larger than `auto_ppm_limit` | Board far off frequency | Set `ppm` near the real value, or raise `auto_ppm_limit` |
| A board hunts while a sibling on the same antenna locks | Board-specific error | Try `ppm = 1.0` then `-1.0` for 30 s each; the one that locks gives the sign |
| A board needs re-hunting after every restart | Remembered correction not saved | Check `[recorder] ppm_memory_path` is writable; `trunkd check` prints the table |
| Panel `pll err` reads a couple of hundred Hz | That is normal | Watch `carrier off` (`freq_error_hz`) instead |

`auto_ppm` works only on backends that can retune while running (`soapy`), and only on tuners
that follow a P25 site. A **channel-only tuner** never corrects itself. Set `ppm` by hand and
watch each call's `offset_hz` on the panel. Aim for under a few hundred Hz; a steady value beyond
±500 Hz means `ppm` needs setting.

### Conventional channel never opens, false opens, wrong tone

Check the panel's channels table, or `curl -s localhost:8080/api/status | jq .channels`.

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Startup error naming the channel | Frequency on the capture centre (DC bin), outside the usable span, too close to another channel or to a control channel, or a duplicate (`system`, `talkgroup`) | Read the error; put `center_frequency` at least 25 kHz from every channel; give each channel its own talkgroup |
| `state` stays `idle` | Tuner not streaming or disabled | Fix the tuner first |
| Never opens, carrier clearly present | `tone` set and not matching; `tone_mismatch` climbing | Check the tone (`"167.9"` CTCSS, `"D445N"` DCS). Remove `tone` to test with carrier squelch |
| Never opens, weak audio, large `offset_hz` | Tuner off frequency (no auto correction on channel-only tuners) | Set `ppm`; at 155 MHz a 30 ppm error puts the carrier 4.7 kHz off, outside the ±4 kHz passband |
| Channel near the edge of the capture records weakly or not at all | Outside the radio's IF filter even though inside the sample rate | Keep every channel inside the filter with margin, or split over two tuners |
| `false_opens` climbing | Squelch too sensitive | Raise `[channel.squelch] open_db` (default 8.0) |
| `tone_mismatch` climbing | Another user on the frequency with a different tone | Expected with a `tone` set; those openings are discarded on purpose |
| Many `calls_too_short` | Kerchunks or noise bursts shorter than `min_call_ms` (500) | Usually correct; lower `min_call_ms` only if real calls are being dropped |
| Calls cut into pieces | Transmissions longer than `max_call_s` (180), or gaps longer than `hang_ms` (1000) | Raise `max_call_s` or `hang_ms` |
| Channel never records, warning at start | `mode = "am"` (accepted but skipped) | Only NBFM is recorded |
| Startup error on `bandwidth_hz` | `25000` (wideband) is refused | Only 12.5 kHz channels are supported |
| Every channel on a tuner noisy | Front end overloaded | Reduce gain until the noise floor stops falling with it |

A tuner that carries only channels never logs `control channel acquired`. That is expected.

### Uploads to keyup fail

trunkd spools any call that fails to upload and retries it.

| trunkd log or status | keyup answered | Cause | Fix |
| --- | --- | --- | --- |
| `invalid key`, logged once, 60 s back-off, `spooled` rising | `401 invalid key` | Wrong token, revoked token, or a token without the `upload` scope | Mint a token: `docker compose exec api keyup token create trunkd --scopes upload`; set `[uplink] api_key` (or `TRUNKD_UPLINK__API_KEY`) |
| Push channel closes with code **4401** | Key refused on the stream | Same as above | Same as above |
| Failures with `413` | `413 Request Entity Too Large` | A proxy in front of keyup limits body size (keyup's own cap is 50 MiB per upload) | On an outer nginx set `client_max_body_size 0`; do not add a `request_body` limit to Caddy |
| `429` with `Retry-After`, `spooled` rising | `queue full, retry later` | The live transcription queue is over `UPLOAD_MAX_QUEUE_LIVE` | Transcription is not keeping up; see [STT backend down](#transcription-stalls) |
| `507` with `Retry-After` | `insufficient storage` | Free space under `AUDIO_ROOT` below `UPLOAD_MIN_DISK_FREE_BYTES` (5 GiB) | Free disk, or set retention ([Operations](operations.md#disk-and-retention)) |
| `incomplete call data: no audio` | `400` | A clear call reached keyup without audio | Should not happen with trunkd (it drops these locally); check the recorder version |
| Connection refused or timeouts | — | Wrong `[uplink] url`, keyup down, firewall | `curl` the URL from the recorder; recorders push to `/api/call-upload`, which is never redirected to https |
| `uploaded` rising but keyup shows nothing new | Calls filed under another system | `[uplink] system_label` does not match the system keyup files talkgroups under | Fix the label; keyup's `RECORDERS.md` covers folding a stray system |

On the keyup host,
`curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8096/api/admin/ingest | jq` shows the
ingest ledger, and `?status=failed` on `/api/admin/ingest/files` shows why individual files
failed. `/api/admin` needs a token with the `read` scope even from the loopback
(`docker compose exec api keyup token create ops-read --scopes read`); see
[Connect trunkd to keyup](connect.md#5-check-that-calls-arrive).

### Health monitor restarts the recorder

Read the monitor log (`trunkd-monitor.log.<date>`). It names the rule that fired.

| Rule | Meaning | Fix |
| --- | --- | --- |
| unreachable | Panel did not answer for 60 s | Enable the panel (`[server] enabled = true`); check `bind` matches `--url` |
| no lock | No control-following tuner locked for 10 min | See [Control channel not acquired](#control-channel-not-acquired) |
| failed unit | A unit used up its restart budget | Read the recorder log just before the restart |
| Panel answers 401/403 to the monitor (logged once) | Panel tokens set, monitor has none | Pass `--token`, set `TRUNKD_MONITOR_TOKEN`, or give it `--config` |

### Timestamps are off

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| All calls a fixed amount early or late | Host clock is off | Run NTP; on Windows set a short poll interval |
| `clock_resyncs` above 0, `stream clock re-anchored` warning | Samples were lost before the ring (memory stall, suspended VM, USB hiccup) | Check the kernel log for out-of-memory kills, and `overflow` and `throughput` |
| `stream_gaps` climbing with no resyncs | Small repeated sample loss | Same as above |
| Two recorders' copies of a call are not merged | Recorder clocks disagree | Point both at the same NTP server |

## keyup

### Transcription stalls

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `stt_backlog` health alert; calls stay `queued` | The speech backend is down or too slow | `docker compose ps stt-cpu` (should be `healthy`); `curl -s localhost:8093/health` |
| `stt-cpu` never becomes healthy | The model is still downloading (about 500 MB the first time), or `STT_CPU_MODEL` differs from the backend's `model` | Wait for the download; make the two match |
| A backend shows `healthy: false` with a `last_error` | Server unreachable or failing | Check the server named in **Admin → Backends**; see the command below |
| Editing `STT_BACKENDS` in `.env` changes nothing | `.env` only seeds the table on the first start | Change backends in **Admin → Backends**; changes reach the worker in about ten seconds |
| Jobs piled up as `failed` after an outage | The outage parked them | They are re-queued automatically within a few minutes once a backend is healthy again; `POST /api/admin/jobs/requeue` does it by hand |
| Every backend switched off | Transcription paused by design | Jobs wait, they are not failed; turn a backend back on |
| Short calls never transcribed | Calls under `TRANSCRIBE_MIN_SECONDS` (0.75 s) are skipped | Expected: these are squelch tails |
| A talkgroup is never transcribed | Its **Transcribe** switch is off | Turn it on in the talkgroup list |
| Uploads answer `429 queue full` | The live queue is over `UPLOAD_MAX_QUEUE_LIVE` (5000) | Fix transcription first; add a faster backend |

What the worker reports about each backend:

```bash
curl -s -H "Authorization: Bearer $KEYUP_ADMIN_TOKEN" localhost:8096/api/admin/stt/backends \
  | jq '.backends[] | {name, healthy, stale, in_flight, mean_rtf, last_error}'
```

### Slow search, or 503 with Retry-After

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Search answers `503 Too many searches are running` with `Retry-After: 2` | All 4 search slots busy for more than 5 s | Expected under load; the client retries. Persistent: the database is undersized |
| Search or stats fail with `could not resize shared memory segment` in `docker compose logs db` | `/dev/shm` too small for parallel query workers | Raise `PG_SHM_SIZE` in `.env`, then `docker compose up -d` |
| Searches slow, `temp_bytes` growing in `pg_stat_database` | Sorts spilling to disk | Raise `PG_WORK_MEM`; see [Postgres sizing](operations.md#postgres-sizing) |
| Everything slow on a large archive, low cache hit rate | `PG_SHARED_BUFFERS` and `PG_EFFECTIVE_CACHE_SIZE` left at the 4 GB-host defaults | Size them to the host |
| Fuzzy search misses new words | Search vocabulary not yet rebuilt | It refreshes every 5 minutes and fully once a day; after a restore run `docker compose exec api keyup transcripts search-vocab` |

### Live feed and the web app behind a proxy

| Symptom | Cause | Fix |
| --- | --- | --- |
| Header badge reads **Offline**, calls list works | WebSocket upgrade not forwarded by the outer proxy | `proxy_http_version 1.1` and the `Upgrade`/`Connection` headers |
| Live feed drops every 60 s | Outer proxy read timeout at its default | Raise `proxy_read_timeout` to 3600 s |
| Activity log does not tail, waterfall stays blank | Server-sent events buffered | `proxy_buffering off` on those paths |
| Signed in, but every change answers **403** | `X-Forwarded-Proto` / `X-Forwarded-Host` not set | Forward both; the API's same-origin check needs them |
| Bulk selection answers **414** | Header buffers too small | `large_client_header_buffers 4 32k` |
| The app loads but every API call is 404 | `/api/` not routed to keyup | Route it |

The complete outer-proxy configuration is on [TLS and reverse proxies](tls.md).

### TLS certificate problems

keyup's `edge` container (Caddy) gets certificates from Let's Encrypt. When issuance fails, it
keeps serving plain HTTP and https never comes up, so the symptom is often "nothing happened".

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Admin → HTTPS shows **wanted** HTTPS, **serving** plain HTTP | Issuance is failing | `docker compose logs edge` names the failing challenge |
| DNS-01: token check fails on the zone | Cloudflare token scoped to the wrong zone, or a global API key used instead of a token | Create a token with **Zone → DNS → Edit** on the zone that holds the names; use **Test Cloudflare token** |
| HTTP-01 fails | Name does not resolve publicly to the box, ports 80/443 not forwarded, or `WEB_PORT`/`WEB_TLS_PORT` not 80/443 | Let's Encrypt connects only to 80 and 443; fix DNS and forwarding |
| Browser says the certificate is not trusted | `ACME_CA` points at Let's Encrypt staging | Expected when rehearsing; blank `ACME_CA` for production |
| Rate-limited by Let's Encrypt | Repeated issuance, often after deleting the `keyup_caddy_data` volume | Rehearse on staging; do not prune that volume |
| Secure cookie problems, alert links use `http://` | `PUBLIC_URL` / `PUBLIC_BASE_URL` not changed to `https://` | Set both by hand; nothing derives them |
| `.env` change to TLS settings is undone a second later | A row in Admin → HTTPS overrides `.env` | Change it in Admin → HTTPS |
| Recorders stop uploading after enabling TLS | They should not: `/health` and `/api/*` are never redirected on `:80` | Check the recorder `url`. A recorder pointed at `https://` by IP address fails the handshake (no certificate covers an IP); use plain `http://` by IP, or `https://` with the hostname |

Check the result:

```bash
docker compose logs -f edge                      # look for: certificate obtained successfully
curl -vk https://keyup.example.com/health        # ok, plus the certificate chain
curl -sI http://keyup.example.com/               # 308 to https://
```

Certificates renew automatically about 30 days before expiry. Your only job is to keep the DNS-01
token valid, or for HTTP-01 to keep the names and ports pointed at the box.

### Backups

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `backup_stale` reports "no database backup … yet" while dumps exist | `BACKUP_DIR` (.env) and `KEYUP_BACKUP_DIR` (script) point at different directories: one was moved, or the install predates keyup v0.1.1, where an unset `BACKUP_DIR` meant `./backups/db` | Set `BACKUP_DIR` in `.env` to the directory the script writes to (default `/srv/keyup/backups/db`), then `docker compose up -d`; see [Operations](operations.md#nightly-database-backup) |
| Backup refuses to start | Less than `KEYUP_BACKUP_MIN_FREE_GB` (40) would stay free | Free disk or lower the floor on purpose |
| `another backup or drill holds … .lock` | A backup and a drill overlapped | Wait for the other run |
| Audio backup exits with "KEYUP_AUDIO_BACKUP_TARGET is not set" | No target named | Expected until you choose one |

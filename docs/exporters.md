# Exporters

keyup can re-publish your live calls to three outside services. **All three ship switched
off**, and keyup ships with no keys for any of them.

| Destination | What it is | You need |
| --- | --- | --- |
| **Broadcastify Calls** | one upload per call into Broadcastify's searchable call archive | an API key and numeric system id from your Broadcastify Calls dashboard |
| **Broadcastify Feed** | one continuous live audio stream to your feed's Icecast mount | the feed's server, port, mount and password |
| **OpenMHz** | one upload per call | the system's API key and `shortName` |

The two Broadcastify products are **different products with different credentials**: the
feed's mount password is refused by the Calls upload, and the Calls API key is refused by the
mount.

!!! warning "Terms of service, and what you may rebroadcast"
    Each service has its own terms, and **you** are the one agreeing to them. Read
    [Broadcastify's terms](https://www.broadcastify.com/terms) and the Broadcastify Calls and
    OpenMHz contributor rules before you turn anything on. Use only credentials issued to you
    for a feed or system you are authorised to provide, upload only traffic you may lawfully
    rebroadcast where you are, and keep to the documented APIs. See also
    [Legal and privacy](legal-privacy.md).

!!! danger "One uploader per system"
    If sdrtrunk, trunk-recorder or anything else already uploads this system to a service,
    turning keyup's exporter on posts every call twice. Stop the other uploader first.

Everything below is configured in **Admin → Exports**. The full reference is keyup's
[EXPORTERS.md](reference/keyup/EXPORTERS.md).

## What is never uploaded

Two safety rules apply to every exporter and cannot be turned off:

* **Live calls only.** Calls that arrive as a backfill or bulk import (an archive migration,
  say) are never published. trunkd marks every call it uploads as live.
* **Only calls after the switch.** Turning an exporter on stamps the time; only calls that
  start after it are uploaded. Turning it off clears the stamp, so turning it back on later
  starts from live rather than replaying the gap.

On top of those:

* **Encrypted calls** are skipped (`export_include_encrypted`, off by default). They carry no
  audio: trunkd never decodes or stores encrypted voice.
* **Very short calls** under `export_min_duration_s` (0.5 s) are skipped, as are calls with
  no speech in them (a key-up and release).
* **Unit-to-unit (private) calls** are never sent to Broadcastify Calls or OpenMHz. The live
  Feed carries them unless you turn `broadcastify_feed_include_unit_calls` off.
* **The global Calls and OpenMHz accounts take trunked systems only.** A call from a system
  keyup does not consider trunked is refused with the reason `not_trunked`. Whether a system is
  trunked is shown, and can be set, in the Systems list on the **Sites** page. A system that was
  first created by trunkd's uploads has no protocol recorded, so keyup counts it as **not
  trunked**: mark your P25 system **Trunked** on the Sites page before you switch Broadcastify
  Calls on (its enable switch stays disabled while Calls has nothing it could publish).
* **Analog calls are conventional, whatever system they are filed under.** A call trunkd marks
  `nbfm` or `am` (every call from a `[[channel]]`) is treated like a call from a conventional
  system. From keyup v0.2.0, conventional calls go to Broadcastify Calls or OpenMHz **only**
  through a destination set on their own system; the Feed takes them like any talkgroup. See
  [Conventional systems](#conventional-systems).
* A call already more than `export_max_age_minutes` (60) old when the exporter first sees it is
  not picked up, so a worker that was down for an afternoon does not replay it.

## Choosing what goes out

### Per-talkgroup tick boxes

Every talkgroup has three export check boxes on the **Talkgroups** page, one per destination,
all ticked by default:

| Column | Used by |
| --- | --- |
| `export_broadcastify` | the Broadcastify **Feed** |
| `export_bcfy_calls` | **Broadcastify Calls** (held off for talkgroups Calls could never publish: a conventional system with no Calls account of its own) |
| `export_openmhz` | **OpenMHz** |

The boxes only matter once you pick a mode. Each service has a talkgroup mode
(`export_<service>_talkgroup_mode`); the two Broadcastify products share one:

| Mode | Publishes |
| --- | --- |
| `all` (default) | **every** talkgroup. The tick boxes are not looked at. |
| `allow` | only talkgroups whose box is ticked. |
| `deny` | every talkgroup except those whose box is cleared. |

Use `allow` to curate a short list (untick everything, tick the few you want) and `deny` to
publish the whole system with a few exceptions. The Talkgroups page's filter row can show
"what is **not** going to OpenMHz", and its bulk-edit drawer sets a box on many talkgroups at
once.

### Per-system limits

`export_broadcastify_systems` and `export_openmhz_systems` limit a service to some of your
systems: **keyup** system ids (not the remote service's ids), picked from a list on the Exports
page. Empty means every system the service could publish.

From keyup v0.2.0 the Feed has its own list, `export_broadcastify_feed_systems`: blank (the
default) follows the Broadcastify Calls list, as the Feed always did; `all` streams every system,
conventional ones included; or pick the systems yourself.

## Conventional systems

keyup archives trunked systems and conventional ones (NBFM fire and EMS channels, AM airband)
side by side. Broadcastify Calls and OpenMHz file every upload under one remote system, and the
global account's system is your trunked one, so a conventional channel sent there would be
filed under the wrong system. From keyup v0.2.0 the rule is:

| Call | Broadcastify Calls | OpenMHz | Feed |
| --- | --- | --- | --- |
| a **trunked** system with no destination of its own | the global account | the global account | follows the Feed's selection |
| a trunked system with its own destination | its own account | its own system | follows the Feed's selection |
| a **conventional** call (system not trunked, or marked `nbfm`/`am` by trunkd) with its own destination | its own account | its own system | follows the Feed's selection |
| a conventional call with no destination of its own | **never sent** (`not_trunked`) | **never sent** (`not_trunked`) | follows the Feed's selection |

"Marked by trunkd" means a conventional channel filed under your P25 system's label is still
conventional: it goes nowhere on Calls or OpenMHz unless that system has a destination of its
own. Giving analog channels their own `system` in trunkd is still the tidy way
([Configure manually](configure/manual.md#system-and-talkgroup-numbers)): keyup records a system
first created by a channel's calls as `NBFM` or `AM`, not trunked.

### A destination of the system's own

On the **Sites** page, open the system and fill in its **Export destinations** (admin only):

* **Broadcastify Calls:** the Calls API key and the Calls system id Broadcastify issued for
  that system. For a conventional system, Broadcastify identifies each channel by a
  **frequency-slot id** instead of a talkgroup: enter it as the **Broadcastify slot** in each
  channel's talkgroup edit dialog. A channel without one is skipped with the reason
  `no_bcfy_slot`, which names the channel that needs it.
* **OpenMHz:** the system's OpenMHz short name and API key.

Both halves of a pair must be set; one without the other is not a destination. The keys are
write-only, like the global ones: the page shows only whether one is set. Then, as for any
system, turn the service's switch on, and add the system to `export_broadcastify_systems` or
`export_openmhz_systems` if that list is not empty.

* Per-system Calls accounts are production credentials. Under the **development**
  environment only the global development pair is used, so conventional systems are not
  uploaded there.
* A service with no global account still runs when some system has a destination of its
  own; any other call it would have sent is skipped with `no_destination`.
* New talkgroups on a conventional system with no Calls account of its own start with the
  Calls box off, and removing a system's Calls destination turns its talkgroups' Calls boxes
  off again.

### Keeping analog calls off the Feed

The Feed is only audio, with no system identity, so none of the above applies to it. To keep
analog channels off it, either set `export_broadcastify_feed_systems` to your P25 systems
(leaving it blank follows the Calls list, which you may have limited already), or switch the
Broadcastify mode to `deny` and clear the analog talkgroups' `export_broadcastify` boxes.

??? note "Before keyup v0.2.0, and trunkd before v0.2.2"
    With **keyup v0.1.1**, analog calls never went to Broadcastify Calls, but **OpenMHz took
    them** under the global short name like any talkgroup; to keep them off it, limit
    `export_openmhz_systems` to your trunked systems or use `deny` mode. With **keyup v0.1.0**
    or **trunkd before v0.2.2**, analog calls filed under your P25 system's label could also
    reach Broadcastify Calls.

    **Recorder-direct uploads with trunkd before v0.2.2:** with *Broadcastify Calls uploaded
    by: recorder* and the mode left at `all`, an old trunkd uploads every group call it records,
    analog channels included, under your Broadcastify system id. Upgrade trunkd. trunkd v0.2.2
    and later never send a conventional channel's call to Broadcastify Calls, in any mode.

## Turning one on

1. **Stop the other uploader** for this system and confirm it has stopped posting.
2. **Enter the credentials** in Admin → Exports, in that service's section (or put them in
   `.env` as a starting value and `docker compose up -d`). Secrets are stored write-only; a
   blank field on save keeps the key you already have.
3. **Test.** For Broadcastify Calls, **Test credentials** makes Broadcastify's documented test
   check of the key (nothing is registered or uploaded) and reports the host clock offset.
   OpenMHz has no such check: its key is only validated by a real upload.
4. **Choose the selection** (mode, tick boxes, systems) if you want one.
5. **Flip one switch.** It takes effect within one exporter cycle (`EXPORT_POLL_SECONDS`,
   15 s). Watch the status on that page and Admin → Activity (`source=export`).
   `configured: false` means a credential is missing and nothing will be sent.
6. Only once that service looks right, flip the next.

To stop, flip the switch off. Calls in flight finish and nothing new is picked up.

Each service keeps a ledger with one row per call, which is also the guarantee that a call is
never uploaded twice. Failed uploads retry with backoff and park after `EXPORT_MAX_ATTEMPTS`
(5); a parked row has a retry button on the Exports page.

## Broadcastify Calls

* **Credentials:** `BROADCASTIFY_API_KEY` and `BROADCASTIFY_SYSTEM_ID` from the Broadcastify
  Calls dashboard. Broadcastify issues development and production credentials separately;
  the **Environment** setting selects which set (and endpoint) is used, and the card shows a
  **DEVELOPMENT** badge when it is not production.
* **Clock:** Broadcastify deduplicates on the call's timestamp, so keyup checks the host clock
  against `EXPORT_NTP_SERVER` and **pauses** Calls uploads while it is more than 5 s out. Keep
  NTP running on the host.
* **Format:** `BROADCASTIFY_ENCODING` is `m4a` (preferred by Broadcastify) or `mp3`.
* **Recorder-direct upload (optional).** *Broadcastify Calls uploaded by* can be `keyup`
  (default: about 3 s after the call ends) or `recorder`: each trunkd uploads at call end,
  typically under a second, with credentials keyup pushes to it. keyup remains the record of
  what was uploaded, and uploads anything no recorder reported. A recorder with
  `[uplink] direct_broadcastify = false` refuses the credentials. Recorders upload only for
  trunked systems that use the global account; calls of a system with a destination of its
  own are left to keyup. trunkd v0.2.2 and later never upload a conventional channel's call;
  with an older trunkd, read the note at the end of
  [Conventional systems](#conventional-systems) before using it.

## Broadcastify Feed

The live stream that listeners hear on your feed's page. keyup connects to the feed's Icecast
mount as its broadcasting client and plays live calls in order, with silence in between. The
five settings are the *Feed Technical Details (Advanced)* panel of your feed's page, field for
field: `broadcastify_feed_server`, `broadcastify_feed_port` (80), `broadcastify_feed_mount`,
`broadcastify_feed_password`, `broadcastify_feed_username` (`source`). Bitrate (16 kbit/s) and
sample rate (22050 Hz) must match how the mount was provisioned.

A mount takes **one** source at a time. Stop your current broadcasting client, press
**Test mount** (it writes two seconds of silence), then set `export_broadcastify_feed_enabled`.
The queue is kept near live: if calls back up past `broadcastify_feed_max_backlog_s` (120 s),
the oldest are dropped.

The Feed follows the Broadcastify selection (mode, `export_broadcastify` tick boxes) and its
own system list (`export_broadcastify_feed_systems`, see [Per-system limits](#per-system-limits)),
the encryption and minimum-duration filters, but plays key-ups with no speech, and plays
unit-to-unit calls unless `broadcastify_feed_include_unit_calls` is off.

## OpenMHz

`OPENMHZ_API_KEY` (the system's API key) and `OPENMHZ_SHORT_NAME` (the system's short name,
the path segment in its OpenMHz URL) are the global account, for your trunked system. OpenMHz
also hosts conventional systems: give each its own short name and key on the Sites page
([Conventional systems](#conventional-systems)).

## Advanced: Broadcastify feed statistics

Separately from uploading, keyup can poll Broadcastify's **feed owner API** for your own live
feed's listener counts and archive listings, and chart them beside your call volume. It uses
your Broadcastify site login (not the Calls key), is off by default (`bcfy_stats_enabled`), and
is only for feeds you provide. Its page scrape and dashboard import rely on undocumented
markup and can break without notice: treat them as use-at-your-own-risk, read Broadcastify's
terms first, and keep poll intervals at their defaults or longer. See keyup's
[BCFY_STATS.md](reference/keyup/BCFY_STATS.md).

## `.env` reference

These are starting values. Admin → Exports overrides each one, and clearing a field there
brings the `.env` value back. The enable switches are not in `.env` at all.

| Variable | Default | Meaning |
| --- | --- | --- |
| `BROADCASTIFY_API_KEY`, `BROADCASTIFY_SYSTEM_ID` | *(empty)* | Broadcastify Calls production credentials. Blank keeps the exporter dormant. |
| `BROADCASTIFY_DEV_API_KEY`, `BROADCASTIFY_DEV_SYSTEM_ID` | *(empty)* | Development credentials. |
| `BROADCASTIFY_ENVIRONMENT` | `production` | Which credential set and endpoint to use. |
| `BROADCASTIFY_ENCODING` | `m4a` | `m4a` or `mp3`. |
| `EXPORT_NTP_SERVER` | `pool.ntp.org` | Clock check for Broadcastify Calls; blank turns it off. |
| `OPENMHZ_API_KEY`, `OPENMHZ_SHORT_NAME` | *(empty)* | OpenMHz credentials. |
| `EXPORT_MAX_ATTEMPTS` | `5` | Tries before a failed upload is parked. |
| `EXPORT_POLL_SECONDS` | `15` | Exporter cycle. |
| `EXPORT_MAX_AGE_MINUTES` | `60` | Older calls are not picked up. |

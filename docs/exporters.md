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
* **Broadcastify Calls takes trunked systems only.** A call from a system keyup does not
  consider trunked is refused with the reason `not_trunked`. Whether a system is trunked is
  shown, and can be set, in the Systems list on the **Sites** page. A system that was first
  created by trunkd's uploads has no protocol recorded, so keyup counts it as **not trunked**:
  mark your P25 system **Trunked** on the Sites page before you switch Broadcastify Calls on
  (its enable switch stays disabled while no system is trunked).
* **Analog conventional calls** never go to Broadcastify Calls with trunkd v0.2.2 and keyup
  v0.1.1 or later, whatever system they are filed under. The Feed and OpenMHz still take them
  like any talkgroup, and older releases send them to Broadcastify Calls too. See
  [Analog conventional calls](#analog-conventional-calls).
* A call already more than `export_max_age_minutes` (60) old when the exporter first sees it is
  not picked up, so a worker that was down for an afternoon does not replay it.

## Choosing what goes out

### Per-talkgroup tick boxes

Every talkgroup has three export check boxes on the **Talkgroups** page, one per destination,
all ticked by default:

| Column | Used by |
| --- | --- |
| `export_broadcastify` | the Broadcastify **Feed** |
| `export_bcfy_calls` | **Broadcastify Calls** (held off for talkgroups of a system that is not trunked) |
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
systems: comma-separated **keyup** system ids (not the remote service's ids). Empty means every
system.

## Analog conventional calls

!!! warning "Analog channels still go to the Feed and OpenMHz unless you keep them out"
    trunkd uploads each analog `[[channel]]` call as an ordinary **group call** with the
    channel's `talkgroup` number (see [Configure manually](configure/manual.md#analog-conventional-channels)).
    To the Feed and OpenMHz it is a talkgroup like any other, and in the shipped `all` mode
    every talkgroup is published.

    **Broadcastify Calls** accepts trunked-system calls only, and from **trunkd v0.2.2** and
    **keyup v0.1.1** analog channel calls are never sent there, whatever system label they
    carry. You need **both** upgrades: keyup v0.1.1 keeps the `mode=nbfm` field trunkd sends
    with every channel call, and its own Broadcastify uploader refuses those calls
    (`not_trunked`); trunkd v0.2.2 refuses them itself when it uploads to Broadcastify Calls
    directly (`skipped_conventional` in its panel). With an older trunkd or keyup, analog
    calls filed under your P25 system's label can still reach Broadcastify Calls, so follow
    the steps below for it too.

What happens depends on the system you file the channel under:

| Channel's `system` | Broadcastify Calls | Feed | OpenMHz |
| --- | --- | --- | --- |
| the P25 system's label (the default when `system` is unset) | never sent (trunkd v0.2.2 + keyup v0.1.1); **published**, as if it were a P25 talkgroup, with older releases | published | published |
| a label of its own, e.g. `"Example County Fire"` | refused (`not_trunked`) when keyup uploads; see the recorder-direct note below for older releases | published | published |

To keep analog calls off the Feed and OpenMHz (and off Broadcastify Calls on older releases),
use one of these:

1. **Give analog channels their own `system`** in trunkd. keyup treats that system as not
   trunked (from keyup v0.1.1 a system first created by a channel's calls is recorded as
   `NBFM`), so Broadcastify Calls refuses it, and step 2 can leave it out. Check the Systems
   list on the Sites page.
2. **Limit the services to your P25 systems**: set `export_openmhz_systems` and
   `export_broadcastify_systems` to the keyup ids of the trunked systems only. The Broadcastify
   setting covers both the Feed and Calls.
3. **Or** switch the service's mode to `deny` and clear the analog talkgroups' tick boxes
   (`export_broadcastify` for the Feed, `export_openmhz` for OpenMHz).

If you do want an analog channel on the Feed or OpenMHz, leave its boxes ticked: both services
take analog calls.

!!! danger "Recorder-direct Broadcastify uploads with trunkd before v0.2.2"
    With **Broadcastify Calls uploaded by: recorder** (below) and the mode left at `all`,
    keyup sends trunkd no talkgroup list, and a trunkd **older than v0.2.2** uploads **every
    group call it records, including analog channel calls**, under your Broadcastify system
    id. It cannot tell which keyup system a call belongs to, so keyup's trunked-only rule does
    not stop this. Upgrade trunkd; until then, if a recorder carries analog channels, use
    `allow` or `deny`: keyup then sends an explicit list of talkgroup numbers from trunked
    systems only. Because that list is numbers only, also give analog channels talkgroup
    numbers that no P25 talkgroup on the system uses. trunkd v0.2.2 and later never send a
    conventional channel's call to Broadcastify Calls, in any mode.

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
  `[uplink] direct_broadcastify = false` refuses the credentials. trunkd v0.2.2 and later
  never upload a conventional channel's call; with an older trunkd, read the
  [analog warning](#analog-conventional-calls) above before using it.

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

The Feed follows the Broadcastify selection (mode, `export_broadcastify` tick boxes, systems),
the encryption and minimum-duration filters, but plays key-ups with no speech, and plays
unit-to-unit calls unless `broadcastify_feed_include_unit_calls` is off.

## OpenMHz

`OPENMHZ_API_KEY` (the system's API key) and `OPENMHZ_SHORT_NAME` (the system's short name,
the path segment in its OpenMHz URL). OpenMHz accepts conventional systems, so the
[analog warning](#analog-conventional-calls) applies in full.

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

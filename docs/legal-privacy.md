# Legal and privacy

!!! warning "This page is not legal advice"
    It lists questions you need to answer before you record, keep or publish radio traffic, and
    the settings trunkd and keyup give you for each. It does not answer them for your
    jurisdiction. If you are unsure, ask a lawyer who knows your local law.

## You are responsible for what you receive, keep and publish

Laws on receiving, recording and publishing radio communications **vary by country, state and
locality**, and they change. The same setup can be legal in one place and not in another. The
questions to answer for your location include:

- **Receiving.** Is it lawful to listen to public-safety and other radio traffic at all? Some
  places restrict scanners in vehicles, or using what you hear to commit or avoid a crime.
- **Recording and keeping.** May you record the traffic and keep it? For how long?
- **Publishing.** May you rebroadcast it, or publish its contents or transcripts? Some
  jurisdictions restrict divulging the contents of communications that were not addressed to
  you, even when receiving them is lawful.
- **Personal data.** Do data-protection or privacy laws apply to the names, addresses, health
  details and radio identifiers in what you keep? See [Removal requests](#removal-requests).

Neither tool decides any of this for you. You are responsible for configuring and operating them
lawfully, and for the terms of every third-party service you connect them to.

## Encrypted traffic is never decoded

P25 encrypts the voice payload and nothing else. On an encrypted call, trunkd still sees the
talkgroup, the radio IDs, the timing, the encryption algorithm and the key ID, but not the
audio.

- **trunkd never tries to decrypt anything and never stores ciphertext.** An encrypted call is
  uploaded as metadata only (`encrypted=1`, no audio part). In the spool it is a JSON sidecar
  with no audio file.
- **Voice frames are never written to trunkd's event log.** The engine drops them at the source;
  no downstream filter does it.
- **keyup stores the metadata row without audio.** The audio route answers `410 Gone`, and
  nothing is queued for transcription.
- **Exporters skip encrypted calls by default.** `export_include_encrypted` is off, so encrypted
  calls are never sent to Broadcastify or OpenMHz unless you change it.

Metadata about encrypted calls is still information about people: which radios were active,
when, and on which talkgroup. Treat it with the same care as the rest of the archive.

## What the tools collect

| Data | Where | Default retention | Notes |
| --- | --- | --- | --- |
| Call audio | keyup `AUDIO_ROOT`; trunkd spool until uploaded | keyup: kept for ever (`RETENTION_KEEP_AUDIO_DAYS=0`) | Clear calls only |
| Transcripts | keyup database | kept for ever (`RETENTION_KEEP_DAYS=0`) | Machine-made, with mistakes, including wrong names and addresses |
| Call metadata (talkgroup, radio IDs, times) | keyup database | kept for ever | Includes encrypted calls |
| Unit-to-unit (private) calls | keyup, if followed | as calls | trunkd follows them by default; `[recorder] follow_unit_calls = false` turns it off |
| Presence: registrations and affiliations | keyup `radio_events` | **90 days** (`RADIO_EVENTS_KEEP_DAYS`) | Recorded whether or not the person ever transmits |
| Raw non-voice event log | trunkd `events/` | **14 days** (`[recorder] event_log_keep_days`) | Stays on the recorder unless you turn on `event_log_archive` |
| Decoded location reports (LRRP), on systems that send them | trunkd | — | Live location of radio users; treat as highly sensitive |
| Visitor analytics | Google Analytics, only if you turn it on | Google's settings | See [Analytics](#analytics) |

**Presence data deserves particular care.** A registration says which radio was on which site
at which minute. An affiliation says which talkgroup its user selected, which is to say which job
that person was doing. Shift patterns, arrival and departure times, and mutual-aid movements fall
straight out of it. That is why keyup's presence window does not default to "keep for ever".
Keep it, and trunkd's `event_log_keep_days`, as short as your purpose needs. Set
`[recorder] event_log = false` if you do not need the raw log at all.

## Publishing transcripts and audio

Public-safety traffic routinely contains **names, home addresses, phone numbers, dates of birth,
licence plates, medical conditions, mental-health crises, and details of victims and children**.
Once a transcript is indexed by a search engine or copied elsewhere, deleting it from your archive
does not bring it back. Transcripts are also wrong in places: a misheard name or address can attach
an incident to the wrong person.

Decide who can read the archive before anyone outside your household can reach it.

### Who can read: `AUTH_REQUIRE_READ`

keyup ships with **reads open** (`AUTH_REQUIRE_READ=false`): anyone who can reach the web app
can read every call and transcript without signing in. Changes always need a sign-in or a token.

```bash
# .env
AUTH_REQUIRE_READ=true
```

Set this **before** the archive is reachable by anyone you would not show every transcript to.
With reads closed, reading anything needs a sign-in, and the embeddable transcript page
(`/embed/`) tells anonymous visitors the archive is closed. In practice a closed archive cannot be
embedded in other sites.

You can also limit what reaches the archive at all:

- **Per talkgroup, in keyup.** **Transcribe** off means no transcript. **Record** off keeps the
  metadata but discards the audio. With both off and no exporter selecting the talkgroup, keyup
  tells the recorder not to send it.
- **On the recorder.** trunkd's `[recorder] skip_talkgroups` never records the listed talkgroups.
  The grant is still decoded and counted, but no tuner is used and nothing is uploaded.

### Search engines

By default keyup tells search engines to index **nothing**. With `VITE_PUBLIC_HOST` blank (the
default), `robots.txt` disallows everything and every page answers `X-Robots-Tag: noindex`.

If you set `VITE_PUBLIC_HOST` to your site's public hostname, only the **shell pages** on that
hostname become indexable: the landing page, talkgroups, stats and help, and those only without a
query string. **Every call, radio and search page still answers `noindex`**, as does every other
hostname and the `/embed/` pages. This lets people find the site without making individual
transcripts findable by searching a person's name.

### Retention

Every call-retention default is "keep for ever". Pick windows that match what you need:

| Setting | Default | Effect |
| --- | --- | --- |
| `RETENTION_KEEP_DAYS` | `0` (for ever) | Delete calls (and transcripts) older than this |
| `RETENTION_KEEP_AUDIO_DAYS` | `0` (never) | Delete audio after this, keep the row |
| `RETENTION_KEEP_TRANSCRIPTS` | `true` | Whether transcripts survive an audio purge |
| per-system / per-talkgroup policies | — | Shorter windows for sensitive talkgroups |
| `RADIO_EVENTS_KEEP_DAYS` | `90` | Presence data; runs even when calls are kept for ever. Not in `.env.example`; add the line. |
| trunkd `event_log_keep_days` | `14` | Raw event log on the recorder |

These are set in **Admin → Settings → Retention**; `.env` holds only the starting defaults. Test a
change with `docker compose exec api keyup retention run --dry-run`. More in
[Operations](operations.md#disk-and-retention).

### Removal requests

Expect people to ask for a call to be removed: someone named in a transcript, a family after a
death, an agency. Data-protection laws in many places (the EU and UK GDPR among them) give people
rights over personal data **even when it came from a public-safety broadcast**. Whether those laws
apply to you depends on where you, your servers and your readers are. Have a process ready either
way:

1. **Publish a contact.** Set `VITE_PRIVACY_CONTACT` (an email address or URL) and rebuild the
   web image. keyup's `/privacy` page then tells readers to send the call's link there.
2. **Delete the call.** First note its recording's path: the call page's raw metadata panel
   shows `file_path`, relative to `AUDIO_ROOT`. Then an admin removes the row, its transcripts
   and its jobs:

    ```bash
    curl -X DELETE "https://archive.example.org/api/calls/<id>?delete_audio=1" \
      -H "Authorization: Bearer $KEYUP_ADMIN_TOKEN"
    ```

    In the standard compose stack the API mounts the audio read-only. The row is deleted, but the
    request answers `409` because the recording could not be. Delete the file on the host
    yourself, together with the `.proc.mp3` processed copy beside it.

3. **Remember the copies.** Database dumps keep the call until they rotate out (up to about three weeks
   with the default rotation). The audio backup script **never deletes at the target**, so remove
   the file there by hand. If an exporter was on, the call may already be on Broadcastify or
   OpenMHz; ask them separately. RSS feeds and search-engine caches may also hold the text.
4. **Keep a record** of the request and what you did, without copying the personal data into it.

### Analytics

Analytics is off unless you turn it on. When `VITE_GTM_CONTAINER_ID` and `VITE_PUBLIC_HOST` are
both set, keyup loads Google Tag Manager **only for guests on the public hostname**. Signed-in
readers, other hostnames and the `/embed/` pages never load it. Before it starts, and on every
navigation, keyup replaces the page address with a clean one:

- page paths with IDs replaced (`/calls/:id`), no query string and no tab title, so Google is not
  told which call someone opened or what they searched for;
- `call_play` and `live_start` events that carry the clean page only;
- referrers from your own site dropped.

The code cannot change two settings in the Google Analytics stream, and you must set both
yourself:

1. **Enhanced measurement: off.** Its history-change page view reads the real address.
2. **Automatic detection of user-provided data: off.** Pages here contain transcripts full of
   names, addresses and phone numbers.

Leave the Tag Manager container with **no custom tags**. To check, load the site signed out on a
URL with `?q=` and a call ID: every request to `/g/collect` must carry the clean address. Keep
the `/privacy` page true to what you actually send.

### Other ways data leaves the archive

- **RSS/Atom feeds.** The token in a feed URL is the whole credential. Anyone holding the URL can
  read that feed's transcripts.
- **Embeds.** `/embed/transcripts` may be framed by other sites (`EMBED_FRAME_ANCESTORS`, any site
  by default) and shows whatever an anonymous visitor may read.
- **Webhooks.** Off unless `WEBHOOK_URL` and `WEBHOOK_EVENTS` are set. Set `WEBHOOK_SECRET` so
  the receiver can verify each delivery.
- **trunkd's live audio monitor** (`[server] live_audio`) is off by default, and the panel listens
  on loopback only. If you expose the panel (`bind = "0.0.0.0:8080"`), set `[server] tokens`.

## Third-party services and their terms

Each service has its own terms of service, and **you** are the one agreeing to them. Read them
before connecting anything. Neither tool ships credentials for any of them.

### RadioReference

keyup can read system, site and talkgroup data from RadioReference's web service for the channel
audit. This needs **your own RadioReference Premium account** and an **application key issued to
you** by RadioReference (`RR_USERNAME`, `RR_PASSWORD`, `RR_APP_KEY`). keyup syncs each system at
most once every `RR_SYNC_HOURS` (24) because the service is someone else's server.

RadioReference's [terms of use](https://www.radioreference.com/terms/) prohibit commercial use and
redistribution of its data without a licence. Do not republish what you download.

RadioReference has **no write API**. Corrections go through its signed-in submission form, which
volunteer database administrators review, and they expect every item to be something the
submitter has verified. keyup never submits anything to RadioReference automatically.

### Broadcastify

keyup can export to two Broadcastify products, both **off by default**:

- **Broadcastify Calls**, one upload per call, using an API key and system ID from the Calls
  dashboard. Trunked systems only.
- **A Broadcastify live feed**, one continuous audio stream to a feed mount, using the feed's
  mount credentials.

The two use different credentials and neither accepts the other's. Read
[Broadcastify's terms](https://www.broadcastify.com/terms) and the contributor rules first. Use
only credentials issued to you, for a feed or system you are authorised to provide. Upload only
traffic you may lawfully rebroadcast: no encrypted or restricted channels, and use the talkgroup
selection to leave out anything sensitive. Run **one** uploader per system. If sdrtrunk or
trunk-recorder already feeds it, turning keyup's exporter on posts every call twice.

trunkd can upload directly to Broadcastify Calls when keyup pushes it credentials.
`[uplink] direct_broadcastify = false` vetoes that on the recorder.

### OpenMHz

keyup's OpenMHz exporter is **off by default** and needs a per-system API key and the system's
short name from OpenMHz. Read OpenMHz's contributor rules before turning it on. The same rules
apply: one uploader per system, and only traffic you may lawfully rebroadcast.

Setup for all three exporters is on [Exporters](exporters.md).

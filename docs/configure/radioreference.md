# Configure from RadioReference

[RadioReference](https://www.radioreference.com/) (RR) documents most public-safety radio
systems: each site's control channels, the voice channels it uses, and the talkgroups with
their names and service tags. trunkd and keyup use it in two ways:

* **By hand, for trunkd.** RR's page for your system lists every site's control channels
  (the frequencies marked `c`). Those go into trunkd's `[[site]] control_frequencies`; see
  [Configure manually](manual.md#a-p25-site).
* **Automatically, in keyup.** keyup can sync a system from RR on a schedule: talkgroup
  names, descriptions and service tags fill in the directory, and RR's channel list is
  compared with what the recorder actually hears on the air (the *site channel audit*).

The automatic sync is optional and **off by default**. Everything else in keyup works
without it.

!!! warning "You need your own RadioReference Premium account and application key"
    RR's web service only answers a **Premium** subscriber, and every application that calls
    it needs an **application key** issued by RR. Both are yours: keyup ships with none, and
    you should not share them. With the credentials blank (the default) the RR half of keyup
    stays dormant and the API logs one line at start-up saying so.

!!! note "RadioReference's terms"
    RR data is licensed to you, not to the people who visit your archive. RR's
    [terms of use](https://www.radioreference.com/terms/) prohibit commercial use and
    redistribution without a licence. keyup's sync is read-only, runs on your own account,
    and caches what it reads only to compare it with what your recorder hears. Do not
    republish the cached tables, and keep `RR_SYNC_HOURS` at its default (24) or longer:
    RR is somebody else's server.

## What the sync does

One sync of one system makes three calls to RR's SOAP service, plus at most one tag lookup
for the whole run:

| RR call | What keyup does with it |
| --- | --- |
| `getTrsDetails` | The system: WACN, system id, NAC. |
| `getTrsSites` | Every site with its frequencies, each marked primary control, alternate control or voice. Kept as a reference cache, including the sites your recorder never hears, so the audit can name the neighbours a control channel announces. |
| `getTrsTalkgroups` | Fills in talkgroup aliases, descriptions and the **service tag** (`Fire Dispatch`, `Law Tac`, ...). |
| `getTag` | Turns a bare tag id into its name, when a talkgroup arrives without one. |

A few rules keep the sync from fighting you:

* **It never overwrites your edits.** If you renamed or reclassified a talkgroup in keyup,
  your value stays. A service tag sets the talkgroup's **category** only when the category
  is still blank. (What the three classification fields mean is in keyup's
  [TALKGROUPS.md](../reference/keyup/TALKGROUPS.md).)
* **It never creates sites.** A site in keyup is one your recorder has heard. RR sites are
  matched to keyup sites by an explicit mapping first, then by site number, then by NAC,
  then by description. A site that matches nothing, or more than one, is logged and skipped
  rather than guessed.
* **A frequency RR stops listing is dropped** from that site's RR rows, so it does not sit
  in the "missing" list for ever.

## Turning it on

### 1. Put your credentials in `.env`

In the keyup `.env` (next to `compose.yaml`):

```sh
RR_APP_KEY=<your RadioReference application key>
RR_USERNAME=<your RadioReference Premium username>
RR_PASSWORD=<its password>
```

`.env` now holds a password in the clear: keep it out of version control and readable only by
the account that runs Docker Compose.

### 2. Map your keyup system to an RR system id

RR's system id (its `sid`) is the number in the URL of the system's database page. It is not
the P25 system id the control channel broadcasts.

Either map it in `.env`, as JSON from the keyup **system name** (the `system_label` trunkd
uploads under) to the RR id:

```sh
RR_SYSTEMS={"Example County": 1234}
```

or, once the system exists in keyup, open **Sites**, edit the system and fill in
**RR system id** (needs an admin account). A mapping set there wins over `RR_SYSTEMS`.

### 3. Restart and sync

```sh
docker compose up -d
```

The worker recomputes the channel audit every `CHANNEL_AUDIT_MINUTES` (60) and, on each pass,
syncs any mapped system that has not been synced in the last `RR_SYNC_HOURS` (24). To sync
now instead of waiting, call the admin endpoint with a token that has the `admin` scope:

```sh
curl -X POST -H "Authorization: Bearer $KEYUP_ADMIN_TOKEN" \
  "http://keyup.example.org/api/admin/radioreference/sync?force=true"
```

Without `?force=true`, a system synced within `RR_SYNC_HOURS` is left alone.

### 4. Fix a site the matcher got wrong

If a keyup site is matched to the wrong RR site (or to none), edit the site on the **Sites**
page and set its RR site id, or call `PUT /api/admin/sites/{id}/radioreference` with
`{"rr_id": <RR site id>}`. That mapping is tried first on every later sync.

## The site channel audit

The audit compares three views of each site: what the control channel announces on the air
(reported by trunkd), what RR documents, and what trunkd is configured to hunt. Open it from
the **Sites** page. It reports:

| Finding | Meaning |
| --- | --- |
| **undocumented** | Heard on the air, absent from RR. A new voice channel usually means the system grew. |
| **missing** | Documented by RR and not heard within `CHANNEL_AUDIT_STALE_DAYS` (14). |
| **control drift** | RR and the air disagree about whether a frequency is a control channel. |
| **recorder config** | Control channels the site announces that trunkd is not hunting, configured ones the site no longer announces, and a suggested list to paste back into `control_frequencies` (live control channel first). |
| **adjacent sites** | The neighbours the control channel names, resolved against RR's site list where possible. A neighbour RR does not know is the interesting one. |

The audit works without RR too: it then compares only the air with trunkd's configuration.
An alert rule of kind `channel_audit` can notify you the first time a new undocumented
frequency or unknown neighbour appears. The full description is keyup's
[CHANNEL_AUDIT.md](../reference/keyup/CHANNEL_AUDIT.md).

## Sending corrections back to RadioReference

**keyup never writes to RadioReference.** RR's web service is read-only: it has no method to
add or change anything. The only way to correct RR's database is its signed-in
[submission form](https://wiki.radioreference.com/index.php/RR_Database_Submission_Guidelines),
which a volunteer database administrator reviews by hand and which expects every item to be
something you have verified yourself.

So anything keyup can offer here is a **draft for you to check**. The audit's *undocumented*
and *adjacent sites* findings, and talkgroups with calls that RR does not list, are the
evidence; you decide what is real, write it up in RR's template and submit it yourself.
Nothing is ever submitted automatically, and a script that posted the form for you would be
against the spirit of RR's terms. A built-in submission-report helper is described in keyup's
[RR_WRITEBACK.md](../reference/keyup/RR_WRITEBACK.md) as a
possible addition; it is not part of this release.

## Settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `RR_APP_KEY` | *(empty)* | Your RadioReference application key. |
| `RR_USERNAME` | *(empty)* | A RadioReference account with a **Premium** subscription. |
| `RR_PASSWORD` | *(empty)* | Its password. |
| `RR_SYSTEMS` | `{}` | JSON map of keyup system name to RR system id, e.g. `{"Example County": 1234}`. A mapping set on the Sites page wins. |
| `RR_SYNC_HOURS` | `24` | Minimum hours between two syncs of one system. |
| `CHANNEL_AUDIT_STALE_DAYS` | `14` | A documented channel not heard within this many days counts as missing. |
| `CHANNEL_AUDIT_MINUTES` | `60` | How often the worker recomputes the audit (and checks whether a sync is due). |

All three credentials empty leaves the sync off.

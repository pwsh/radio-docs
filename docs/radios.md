# Radio names

Every call names the radio that talked. keyup keeps a directory of the radios it has heard, and
the more of them have a name (an alias such as `E7` or `MEDIC 12`), the more useful the archive
is. From keyup v0.2.0, names come from several places, each alias records where it came from,
and nothing automated ever replaces a name you typed in.

The reference is keyup's [TALKGROUPS.md](reference/keyup/TALKGROUPS.md) (sections "Radio
aliases from a playlist" onwards) and [RADIO_IMPORT.md](reference/keyup/RADIO_IMPORT.md). Who
may see these names is on [Legal and privacy](legal-privacy.md#radio-names-and-guests).

## Where a name comes from

Each radio's page shows its alias with a **source** badge. When two sources disagree, the
higher rank wins:

| Rank | Source | Meaning |
| --- | --- | --- |
| 3 | `manual` | Typed in on the Radios page or the radio's page, or a candidate accepted with **Use this**. |
| 2 | `talker` | The radio's own on-air talker alias, promoted by keyup (below). |
| 1 | `import`, `playlist` | A radio list or an sdrtrunk playlist imported here. Between the two, the newer wins, unless one is a longer form of the other. |
| 0 | `recorder` | A name a recorder sent with a call. Aliases stored before v0.2.0 count as this, typed-in ones included, because keyup cannot tell them apart. |

- A name set by hand is **never** replaced by anything automated.
- Nothing proposed is lost: every value any source offered is kept as a **candidate** on the
  radio's page, where **Use this** makes it the alias (and so a hand-set one).
- Clearing an alias by hand lets the automated sources fill it again.
- **No import ever creates a radio.** A radio ID the archive has never heard is reported and
  skipped: the directory is the list of radios actually heard here.

## Names the radios send on air

trunkd decodes the talker alias many radios send with each transmission, and keyup stores it on
the call. Every 15 minutes the worker promotes the value a radio clearly sends to that radio's
alias: the most-heard value in the last 90 days, heard at least 3 times and at least 80 % of what
the radio sent. A radio that keys up under several names (a console, a shared position) gets
none of them and keeps its alias; its page shows the competing values. Names that look cut off
or that another radio also sends are held back, and values that are only digits or carry
characters the decoder could not read are never promoted.

The four knobs are in **Admin → Settings → Directory** ("On-air aliases"); `.env` holds their
first values (`ALIAS_PROMOTE_ENABLED`, `ALIAS_PROMOTE_WINDOW_DAYS`,
`ALIAS_PROMOTE_MIN_SIGHTINGS`, `ALIAS_PROMOTE_MIN_SHARE`). The worker counts only calls ingested
after its first pass. To take in history once, preview and then run the backfill:

```bash
docker compose exec api keyup radios promote-aliases --since 2026-01-01 --dry-run
docker compose exec api keyup radios promote-aliases --since 2026-01-01
```

It refuses to walk a range it has already walked, so running it twice does not count calls
twice.

## Importing a radio list

Someone else's list of radio IDs and names (another monitor's radio database, a spreadsheet, an
sdrtrunk playlist) can fill in the names of radios this archive has heard. An import is always
two steps, a **dry run** that changes nothing and a **commit** of that reviewed dry run, and a
committed import can be **reverted**. It is admin-only.

**In the web interface:** **Admin → Radios → Import a radio list**. Upload the file, map each
system name the list uses to one of your systems (or to *skip*), and read the report before you
commit.

**From the shell:** put the file in your site directory (`KEYUP_SITE_DIR`, mounted at `/site`
in the `migrate` container), then:

```bash
# 1. dry run: prints a summary and the batch id; writes nothing but the batch record
docker compose run --rm migrate keyup radios import /site/radios.csv \
    --system-map "METRO=Example P25" --system-map STATE=skip \
    --origin "neighbouring monitor's list"

# 2. review the summary (the per-row report is also in Admin → Radios), then commit that batch
docker compose run --rm migrate keyup radios import --apply 17

# 3. if it was wrong
docker compose run --rm migrate keyup radios import-revert 17
```

| Format | What it is |
| --- | --- |
| `sighting_csv` | A monitor's radio database with the header `Date,System,Site,Name,RadioID,Alias,Talkgroup,WACN,NETSYS,NAC,CNTRL,FREQ`. This format cuts aliases at seven characters, so such an alias is marked as possibly truncated, and a longer name for the same radio later replaces it. |
| `generic_csv` | A header row with at least `radio_id,alias`, and optionally `system`, `wacn`, `home_system`, `agency_code`, `unit_id`, `kind`, `last_heard`, `site`, `tgid`. |
| `sdrtrunk_xml` | sdrtrunk's `default.xml`: the radio IDs of each alias, with the alias list's name as the system. |

`--format auto` (the default) recognises the file. Things to know:

- **Every system name in the list must be mapped**, by name or ID, to a keyup system or to
  `skip`. Rows naming an unmapped system are rejected, not guessed, and a row only ever matches
  radios of the one system it maps to.
- **The dry-run report** counts rows matched, ambiguous, not heard (skipped) and rejected, and
  what the alias rule would do with each: applied, kept because you set it by hand, kept because
  a stronger source holds it, and so on. It also lists aliases many radios share (consoles,
  test lists) and sites or talkgroups keyup does not know.
- **A commit applies what you reviewed.** If the archive has changed since the dry run in a way
  that changes an outcome (you named one of the radios in between, say), the commit is refused
  and you run a fresh dry run. The same file with the same map is not committed twice.
- **A revert** puts back each alias the batch wrote, unless it has been changed since, and
  removes what the batch added without touching another batch's evidence.
- Large lists are applied a few hundred radios at a time, so calls keep arriving during a
  commit. If one stops part way, run the same command again and it carries on.

Imported names are never shown to guests under the default `guest_radio_visibility`.

## Where a radio was heard

keyup rolls calls and control-channel events up into **sightings**: the sites and talkgroups
each radio was heard on, with first and last time. The radio's page shows **Where heard** and
**last heard**, and the Sites page lists radios that roam between sites. A committed import adds
the sites the list reported, labelled as reported by an external list, not heard here.

Sightings are kept for `radio_sightings_keep_days` (365) after the radio was last heard at that
site, and only signed-in readers see them. To build them from calls recorded before v0.2.0,
once:

```bash
docker compose exec api keyup radios backfill-sightings --since 2026-01-01 --step-days 7
```

It only reads calls and events, one week at a time, and is safe to stop and run again.

## Suggestions, never applied by themselves

keyup can point at names and fields worth a second look. None of these changes anything until
an admin accepts it.

- **Suggested agency, kind and home system.** **Admin → Radios → Alias prefix rules** take rules
  of your own, such as "an alias starting with `52-` belongs to agency `EXFD`" or "… is a
  `mobile` radio". keyup then suggests the agency, kind or home system for radios that lack
  one, shown in the **Suggested** column of the Radios page with accept and reject buttons. A
  rejected suggestion is remembered and not made again. Suggestions refresh nightly, after an
  import and after a rule change, or now with
  `docker compose exec api keyup radios infer --dry-run` (drop `--dry-run` to store them).
- **Suspect aliases.** **Admin → Radios** counts radios whose alias may be cut short, carries
  characters the decoder could not read, is only digits, equals the radio's own ID, is shared
  by many radios, contains a test keyword (`TEST` by default), or disagrees with what the radio
  sends on air. Each count opens the Radios page filtered to those radios. From the shell:
  `docker compose exec api keyup radios suspect-aliases --csv`.
- **Control channels.** An imported list that reports control channels is cross-checked
  against what keyup knows and against RadioReference, in the dry-run report only; nothing is
  stored from it.

# Import from sdrtrunk

If you already run [sdrtrunk](https://github.com/DSheirer/sdrtrunk), its playlist (usually
`default.xml` in sdrtrunk's `playlist` folder) holds most of what trunkd and keyup need. Two
importers read it, and each takes a different half:

| Importer | Reads | Writes |
| --- | --- | --- |
| `trunkd import-sdrtrunk` | the playlist's **channels**: P25 sites and NBFM channels | a starting `trunkd.toml`, printed to stdout |
| `keyup playlist import` | the playlist's **aliases**: talkgroup and radio names, groups, colours | keyup's talkgroup and radio directory |

Neither changes the playlist, and sdrtrunk can keep running while you prepare trunkd. Do not
let both upload the same system to the same places at once; see the last section.

## trunkd: sites and channels

```sh
trunkd import-sdrtrunk default.xml > trunkd.toml
```

The output is a complete `trunkd.toml`: every section with its defaults written out, plus the
devices, sites and channels taken from the playlist. Treat it as a draft.

### What carries over

| From the playlist | Becomes | Notes |
| --- | --- | --- |
| P25 Phase 1 channel | `[[site]]` | `system`, `site` (the channel name when the site is blank), `control_frequencies`, `traffic_pool_size`, the hunt's rotation delay, and `enabled`. Several playlist entries for one (system, site) are merged into one site with the union of their control frequencies. |
| NBFM channel | `[[channel]]` | `name`, `system`, `site`, `frequency`, `talkgroup`, `bandwidth_hz` and `enabled`. A **25 kHz** channel is kept but written `enabled = false`, since trunkd records 12.5 kHz only. |
| sdrtrunk squelch thresholds | `[channel.squelch]` `noise_open`, `noise_close`, `hysteresis_open`, `hysteresis_close` | Carried so nothing is lost, then **ignored** by trunkd (one info line at start): they mean nothing to trunkd's dB squelch. |
| AM channel | `[[channel]]` with `mode = "am"` | Kept, not recorded. |
| Disabled entries | kept, with `enabled = false` | Nothing is dropped just because it was off. |
| DMR, NXDN, LTR and other decoders | nothing | Out of scope for trunkd. |
| Aliases | nothing | Names go into keyup instead (below). |

The playlist says nothing about your radios, so the importer **invents placeholder tuners**:
one `[[device]]` per site (`sdr0`, `sdr1`, ...), centred between that site's lowest and
highest control channel, plus one per group of NBFM channels no site tuner can hear. Each is
written as `backend = "soapy"`, `soapy = "driver=hackrf"`, `sample_rate = 20000000`.

### What to fix afterwards

1. **The tuners.** Replace each placeholder with your real radio: `driver` (or `backend =
   "hackrf"`), a `sample_rate` that radio supports, gains, and `serial` when several of the
   same kind are attached. If your radio is narrower than 20 MHz, re-centre it so it covers
   the whole site, not only the control channels; see
   [Picking the centre for a site](manual.md#picking-the-centre-for-a-site).
2. **The upload target.** `[uplink] url`, `api_key`, `system_label` and `site_label` come out
   blank. `system_label` must be the system name keyup files your talkgroups under (see
   [Configure manually](manual.md#the-upload-target)).
3. **Tones.** CTCSS and DCS settings are not imported: every channel comes out as **carrier
   squelch**. Add `tone = "..."` to the channels that need tone squelch.
4. **Wideband channels.** A 25 kHz channel stays disabled; trunkd cannot record it yet.
5. **Analog systems and talkgroup numbers.** Channels keep the playlist's system label and
   talkgroup number, which keeps an existing archive's talkgroups continuous. If a channel's
   system is blank, it falls back to `[uplink] system_label` (the P25 system); give it a
   label of its own instead (see the tip in
   [Configure manually](manual.md#system-and-talkgroup-numbers)). Two channels may not share
   (`system`, `talkgroup`).
6. **Recorder name.** Set `[recorder] instance_id` if the host name is not what you want shown
   in keyup.
7. **Trim.** You can delete any key that only restates a default.

Then validate:

```sh
trunkd --config trunkd.toml check
```

## keyup: talkgroup and radio names

keyup reads the playlist's aliases into its directory, so talkgroups have names before they
are first heard. Only `protocol="APCO25"` identifiers are read; DMR, LTR and NBFM aliases in
the same file are skipped and counted.

From the web interface: **Talkgroups → Import playlist**, then choose or paste the file.

From the command line, put the file in your site directory (`KEYUP_SITE_DIR` in `.env`, which
is mounted at `/site` in the `migrate` container) and run:

```sh
docker compose run --rm migrate keyup playlist import /site/default.xml --system "Example County"
```

`--system` names the keyup system the aliases go into, and creates it if needed. It must be
the same name as trunkd's `system_label`. Without it the import uses the only system there
is, and refuses if there are none or several.

The importer **overwrites** aliases: importing a playlist is an explicit act and the playlist
is your own naming. A talkgroup that has never been heard is created with no calls so it
shows up in the directory. It also takes a CSV (`tgid,alias,group,category,service_tag,agency_code,color`,
the same columns keyup's talkgroup export writes), so you can export, edit in a spreadsheet and
re-import.

### Check for duplicate talkgroups per system

All aliases in the file go into the **one** system you name: the importer does not look at
which sdrtrunk alias list an alias belongs to. If your playlist holds alias lists for several
systems that reuse the same talkgroup numbers, or one list has two aliases with the same
number, they collapse into one talkgroup and **the alias that comes last in the file wins**.

Before importing a multi-system playlist:

* split it so each file holds one system's aliases, and import each with its own `--system`;
  or
* import it, then open **Talkgroups**, filter to the system and check the names of talkgroups
  you know were duplicated.

The import prints a summary (aliases read, entries skipped as non-P25, unknown service tags
and agency codes dropped) so you can see what it did.

## Moving uploads off sdrtrunk

If sdrtrunk uploads to Broadcastify or OpenMHz today, keep it doing so until keyup's exporters
are set up, then turn the sdrtrunk stream off **before** you turn keyup's on. Two uploaders for
one system post every call twice. See [Exporters](../exporters.md#turning-one-on).

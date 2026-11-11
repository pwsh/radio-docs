# Configure manually

This page writes a `trunkd.toml` by hand: one P25 trunked site, plus a few analog
conventional (NBFM) channels on a second tuner. Everything here describes a fictional
"Example County"; replace the frequencies with your own.

The complete, commented reference is
[`trunkd.example.toml`](https://github.com/pwsh/trunkd/blob/v0.2.2/trunkd.example.toml), and every
key is explained in trunkd's
[configuration.md](../reference/trunkd/configuration.md). This page is
the short path through them.

## Where the file lives

* Linux: `/etc/trunkd/trunkd.toml` for the system service.
* Windows: `C:\trunkd\config\trunkd.toml` for the service. Inside the file, Windows paths need
  forward slashes (`"C:/trunkd/spool"`) or doubled backslashes.

The file holds your keyup upload token, so keep it out of reach of other users: on Linux the
service install makes it mode `0640`, owned by `trunkd:trunkd`
([Install trunkd on Linux](../install/trunkd-linux.md#3-install-the-binary-a-user-and-a-config)). Any value can also come from the environment instead, with a
`TRUNKD_` prefix and `__` for nesting, e.g. `TRUNKD_UPLINK__API_KEY=...`.

After every edit, validate it without opening any radio:

```sh
trunkd --config /etc/trunkd/trunkd.toml check
```

It prints `configuration: OK` with a summary of devices, sites and channels, or a
configuration error that names the offending entry.

## The upload target

```toml
[uplink]
url          = "http://keyup.example.org/api/call-upload"
api_key      = ""                  # a keyup token with the `upload` scope
system_label = "Example County"    # what keyup files the P25 calls under
site_label   = "Site 1"

[recorder]
instance_id = "rec-01"             # this recorder's name upstream; hostname when unset
```

`system_label` must match the system name keyup files your talkgroups under (and, if you use
it, the name in keyup's `RR_SYSTEMS`). Getting the token is covered in
[Connect trunkd to keyup](../connect.md).

## A P25 site

### The tuner

Each `[[device]]` is one SDR. For an Airspy R2 covering a whole 800 MHz site:

```toml
[[device]]
id               = "sdr0"
backend          = "soapy"
driver           = "airspy"
sample_rate      = 10000000
center_frequency = 856000000       # covers 851-861 MHz
[device.gains]
LNA = 12
MIX = 10
VGA = 12
```

`sample_rate / 12500` must be an even whole number of at least 4, and the radio must support
that rate exactly; trunkd refuses to start if the driver quietly picks a different one. Known
good rates per radio, gains and frequency correction are on the [Hardware](../hardware.md)
page and in trunkd's
[sdr-hardware.md](../reference/trunkd/sdr-hardware.md).

### The site

```toml
[[site]]
system  = "Example County"
site    = "Site 1"
devices = ["sdr0"]
control_frequencies = [851200000, 852400000, 853600000]
traffic_pool_size   = 20
```

| Key | Default | What it does |
| --- | --- | --- |
| `system`, `site` | (required) | Labels for display and for matching sites between recorders. |
| `devices` | `[]` | The tuners serving this site. (`device = "x"` is the older single-tuner spelling and still works.) |
| `enabled` | `true` | A disabled site stays in the file but is not decoded. |
| `control_frequencies` | `[]` | Control-channel candidates in Hz. All are tried at once; the first to give five valid trunking messages under one NAC wins, so the order is only a preference. |
| `traffic_pool_size` | `20` | How many voice channels the site may follow at once. Raise it if the log says `traffic pool exhausted`. |
| `data_follow` | `false` | Also follow data-channel grants, not just voice. |

**Where the control frequencies come from.** RadioReference's page for your system lists
every site's control channels (marked `c`); see
[Configure from RadioReference](radioreference.md). An sdrtrunk playlist carries them too
([Import from sdrtrunk](sdrtrunk-import.md)). Once keyup is receiving, its site channel audit
lists any control channel the site announces that you have not configured.

**What you do not configure.** You do not enter the WACN, system id or NAC: trunkd learns them
from the control channel. You do not list talkgroups either: trunkd records every clear group
call the site grants, and keyup builds the talkgroup directory as calls arrive. Names come
from RadioReference, an sdrtrunk playlist import, or editing in keyup. To stop recording a
talkgroup at all, list it in `[recorder] skip_talkgroups`, or in keyup turn its Record and
Transcribe switches off (with no exporter selecting it, keyup then tells the recorder to skip
it). Encrypted calls are never decoded or stored.

### Picking the centre for a site

A P25 site's voice channels can be anywhere in its band, so the tuner has to hear the whole
site, not only the control channels:

1. List every frequency the site uses (RadioReference shows them all; the control channels
   alone are not enough).
2. Set `center_frequency` near the middle of the lowest and highest.
3. Check the spread fits inside `center_frequency ± sample_rate / 2`, less a 1 % guard band at
   each edge. trunkd refuses to start if a control frequency falls outside it; a voice
   channel outside it is simply never recorded.

If one tuner cannot cover the site (an RTL-SDR's 2.4 MHz covers roughly a quarter of a
typical site), use several `[[device]]`s, list them all in the site's `devices`, and give each
a `bands` list saying which part of the site it records, e.g.
`bands = ["851000000-853000000"]`. The details are in configuration.md under
[`bands`](../reference/trunkd/configuration.md#bands--what-a-tuner-is-responsible-for).

## Analog conventional channels

A `[[channel]]` records one analog NBFM frequency (a fire dispatch, a public works channel)
call by call. It is cut out of a tuner's capture by the same channelizer the P25 sites use, so
a tuner can carry a site and channels at once, or channels only. A config with channels and
no `[[site]]` is valid.

Each call is uploaded to keyup as an ordinary **group call** under (`system`, `talkgroup`),
with `name` as the talkgroup's label.

```toml
[[device]]
id               = "vhf0"
backend          = "soapy"
driver           = "sdrplay"
sample_rate      = 2000000
center_frequency = 155000000       # usable roughly 154.0-156.0 MHz

[[channel]]
name      = "Fire Dispatch"
system    = "Example County Fire"
frequency = 154250000
talkgroup = 14
tone      = "167.9"                # CTCSS: only calls carrying 167.9 Hz are recorded

[[channel]]
name      = "Fireground 2"
system    = "Example County Fire"
frequency = 154430000
tone      = "D023N"                # DCS code 023, normal polarity

[[channel]]
name      = "Highway Maintenance"
system    = "Example County Public Works"
frequency = 155535000              # no tone: carrier squelch

[channel.squelch]                  # applies to the channel just above it
open_db  = 10.0
close_db = 6.0
hang_ms  = 1500
```

### 12.5 kHz only

trunkd records **narrowband (12.5 kHz) channels only**. `bandwidth_hz` defaults to `12500`
and that is the only accepted value: `25000` is refused at start-up. A wideband channel
imported from sdrtrunk is written disabled for this reason. `mode = "am"` is accepted but not
recorded (skipped with a warning).

### Tone squelch or carrier squelch

| Setting | Behaviour |
| --- | --- |
| `tone` set | **Tone squelch.** A call is recorded only if the carrier carries that sub-audible tone. A carrier without it is discarded and counted as a tone mismatch. Use it on a shared frequency where you only want one user. |
| `tone` unset | **Carrier squelch.** Any carrier opens the channel. The tone heard, if any, is still reported on the call, which is a good way to find out which tone a channel uses. |

Tone spellings:

* **CTCSS**: a frequency from the standard 50-tone table, `"167.9"` (also `"PL 167.9"`, or a
  bare TOML number).
* **DCS**: `"D445N"` (normal), `"D445I"` (inverted), `"445"` or `"DCS 445"`.
  `dcs_strict = true` accepts only error-free code words instead of correcting one bit.

The squelch itself is relative to the channel's own noise floor, in dB. Its knobs live in
`[channel.squelch]`, which must come **after** the channel's other keys (a TOML rule). All are
optional:

| Key | Default | What it does |
| --- | --- | --- |
| `open_db` | `8.0` | Open when power is this many dB above the tracked noise floor. Must be greater than `close_db`. |
| `close_db` | `5.0` | Close when power falls to or below this. |
| `attack_ms` | `40` | How long power must stay above `open_db` before the channel opens. |
| `hang_ms` | `1000` | How long power must stay below `close_db` before the call ends. A re-key inside it continues the call. |
| `tone_timeout_ms` | `750` | With a `tone`: how long after carrier-up the tone must be confirmed. |
| `max_call_s` | `180` | Longer transmissions are split into consecutive calls; no audio is lost. |
| `min_call_ms` | `500` | Shorter calls (kerchunks) are dropped and counted. |

### System and talkgroup numbers

| Key | Default | Notes |
| --- | --- | --- |
| `name` | (required) | The talkgroup label in keyup. |
| `frequency` | (required) | Channel centre, Hz. |
| `system` | `[uplink] system_label` | The system the calls are filed under. |
| `talkgroup` | `frequency / 1000` | 154.250 MHz becomes `154250`. If an existing archive already uses a number for this channel, keep it. |
| `site` | `[uplink] site_label`, then the device id | Site label recorded on the calls. |
| `device` | automatic | The tuner carrying the channel. Unset picks the one device whose span covers the frequency. |
| `deemphasis_us` | `750` | De-emphasis time constant; `0` disables it. |
| `enabled` | `true` | A disabled channel stays in the file and is not checked or started. |

!!! tip "Give analog channels their own `system`"
    Left unset, `system` falls back to `[uplink] system_label`, which files your analog calls
    as talkgroups of the **P25 system**. A made-up talkgroup number can then collide with a
    real P25 talkgroup, and the exporters publish the calls as part of the P25 system. With
    trunkd v0.2.2 and keyup v0.1.1 or later, analog calls never go to Broadcastify Calls
    (you need both upgrades; older releases sent them there like P25 talkgroups), but the
    Broadcastify Feed and OpenMHz still take them unless you leave them out. A separate label
    such as `"Example County Fire"` keeps them apart. See
    [Exporters](../exporters.md#analog-conventional-calls) before you publish anything.

`[recorder] skip_talkgroups` never applies to conventional channels: to stop recording one,
set `enabled = false`.

### What is checked at start-up

Each of these is a start-up error naming the channel (only enabled NBFM channels are
checked):

* the device exists (or exactly one device covers the frequency), has a `center_frequency`,
  and a sample rate the channelizer can drive;
* the frequency is inside the device's usable span, `center_frequency ± (sample_rate / 2 − 12.5 kHz)`;
* the frequency is **not on the capture centre**: keep `center_frequency` at least 25 kHz
  from every channel;
* no two channels on one device are closer than 6.25 kHz;
* no channel is closer than 12.5 kHz to a control-channel candidate of an enabled site on
  the same device;
* `tone` parses, `bandwidth_hz` is `12500`, and `open_db` is greater than `close_db`;
* (`system`, `talkgroup`) is unique across channels.

A channel inside the outer 1 % of the capture only gets a warning.

### Picking a receiver centre for channels

1. Start at the midpoint of the lowest and highest channel.
2. Check that the spread, plus a margin at each edge, fits inside the radio's **analog
   filter**, not just the sample rate. On some radios the filter is narrower than the
   capture (an SDRplay at 2 Msps with a 1.536 MHz filter, for example), and a channel between
   the filter edge and the capture edge passes the check but records weakly or not at all.
3. Nudge the centre (by 50-100 kHz, say) until no channel is within 25 kHz of it. On zero-IF
   radios (RTL-SDR, SDRplay) the centre also carries the local-oscillator spur.
4. Avoid centring on a strong local transmitter you do not record.
5. Run `trunkd check`. If the channels do not fit in one capture, split them over two tuners.

A channel-only tuner (no `[[site]]` on it) has no control channel to measure its frequency
error against, so it never corrects itself. Set `ppm` by hand, then watch the carrier offset
each call reports (`offsetHz` on the upload); aim for under a few hundred Hz. More in
sdr-hardware.md under
[Tuners for conventional channels](../reference/trunkd/sdr-hardware.md#tuners-for-conventional-channels).

## Check it

With the blocks above in one file:

```console
$ trunkd --config trunkd.toml check
configuration: OK
  devices=2 sites=1 (1 enabled, 0 disabled) channels=3 (3 enabled, 0 disabled)
  device 'sdr0' backend=Soapy rate=10000000 center=856000000 Hz
  device 'vhf0' backend=Soapy rate=2000000 center=155000000 Hz
  site 'Example County/Site 1' [enabled] control_freqs=3 pool=20
  uplink keyup → http://keyup.example.org/api/call-upload
  link disabled
```

followed by the radios it can see. Two typical errors, and what they mean:

```text
trunkd: configuration error: channel 'Highway Maintenance': 155000000 Hz is on device 'vhf0''s capture centre (the DC bin, which the channelizer refuses); move the device's `center_frequency`
trunkd: configuration error: channel 'Fireground 2': 25 kHz channels are not supported yet (bandwidth_hz = 25000); use 12500
```

For a first run, set `[uplink] spool_only = true`: trunkd records and spools every call but
uploads nothing until you release the hold from keyup or the local panel.

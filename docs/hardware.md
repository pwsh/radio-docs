# Hardware

trunkd decodes a whole P25 site from **one wideband capture**: a polyphase channelizer cuts the
capture into 12.5 kHz channels, one follows the control channel and the others follow whichever
voice channels are granted. So the radio's job is to cover the site's frequencies, and the host's
job is to keep up with the sample rate. keyup's host needs disk for audio, memory for PostgreSQL
and CPU (or a GPU) for transcription.

The full reference is trunkd's
[sdr-hardware.md](reference/trunkd/sdr-hardware.md).

## SDRs

| Radio | Backend | Sample rate to use | Avoid | Notes |
| --- | --- | --- | --- | --- |
| Airspy R2 | `soapy` | 10 Msps, or 2.5 Msps | — | 10 MHz covers most single-band 800 MHz sites in one tuner. |
| Airspy Mini | `soapy` | 6 Msps, or 3 Msps | — | |
| SDRplay RSPdx | `soapy` | 2–10 Msps; 8 Msps with `bandwidth_hz = 8000000` | — | Needs SDRplay's proprietary API service. Wide frequency coverage suits VHF/UHF conventional channels. |
| RTL-SDR | `soapy` | 2.4 Msps | 3.2 Msps (drops samples on USB 2), 2.56 Msps (not divisible by 12500) | Runs tens of ppm off frequency; needs a measured `ppm`. |
| HackRF One (and PortaPack) | `hackrf` | 20 Msps | — | 8-bit; the widest single capture. Driven through `hackrf_transfer`. |

**`soapy`** reaches every radio SoapySDR has a driver module for. trunkd loads SoapySDR (0.8) at
run time, so building trunkd needs none of the SDR libraries; a running recorder needs the
SoapySDR runtime plus the module for its radio. **`hackrf`** runs the stock `hackrf_transfer`
tool, which must be on `PATH`. The install pages cover both:
[Linux](install/trunkd-linux.md#2-install-the-sdr-runtime), [Windows](install/trunkd-windows.md#2-the-sdr-runtime).

A radio that another program (sdrtrunk, SDR#) has open does not show up in trunkd at all. Stop the
other program first, or give trunkd a different board.

### Sample rates and spans

- `sample_rate / 12500` must be an **even integer of at least 4**, and the radio must support the
  rate **exactly**. trunkd reads the rate back after setting it and refuses to open a device that
  moved it. Every rate in the table passes.
- **The span is about the sample rate.** Every enabled site's control frequencies must fall
  inside `center_frequency ± sample_rate/2`, less a 1 % guard band at each edge, or trunkd refuses
  to start. A 10 Msps Airspy centred on 856 MHz covers 851–861 MHz; a 20 Msps HackRF centred on
  856 MHz covers 846–866 MHz.
- **A site wider than one radio needs several.** An RTL-SDR's 2.4 MHz covers roughly a quarter of
  a 9 MHz site, so a site normally takes several dongles, each a `[[device]]` with its own
  `center_frequency` and a `bands` list splitting the site's downlink between them. See
  [Configure manually](configure/manual.md).
- **Conventional (analog NBFM) channels** come out of the same channelizer, so the same rule
  applies. Keep `center_frequency` at least 25 kHz from every channel, and keep channels inside
  the radio's analog filter, which on some radios is narrower than the sample rate.

### Frequency correction

At 855 MHz every ppm of oscillator error is about 855 Hz, and the decoder does not acquire a
control channel more than a few hundred Hz off. `auto_ppm` (on by default, `soapy` backend only)
measures the offset while hunting and corrects it, up to 5 ppm, and remembers the result per
board. An RTL-SDR is usually further off than that: measure it once with `rtl_test -p` and set
`ppm` in its `[[device]]`. The HackRF backend cannot retune at run time, so set `ppm` by hand
there if the board needs it.

### Gains

Starting points; then watch the signal and decode figures on the panel or in keyup:

- **Airspy:** `LNA`, `MIX`, `VGA`, each an index 0–15 (not dB). 12/10/12 is a reasonable
  700/800 MHz start.
- **SDRplay:** `IFGR` is attenuation, 20–59 dB, so lower means more gain; 40 is a sane start.
- **RTL-SDR:** `gain = 40.0` (0–49.6 dB).
- **HackRF:** `lna_db` 0–40 in 8 dB steps, `vga_db` 0–62 in 2 dB steps, `amp` for +14 dB.

More gain is not better once the noise floor rises with it.

## Antennas

Use an antenna **resonant in the site's band** rather than a wideband discone where you can: for
800 MHz systems, an 800/900 MHz collinear or a quarter-wave ground plane cut for about 855 MHz. A
**bandpass filter** in front of the radio helps a lot near strong pager or cellular transmitters.
Keep the coax short and low-loss, and the antenna as high and clear as you can manage.

## Host sizing

### The recorder (trunkd)

| | What to plan for |
| --- | --- |
| **CPU** | The channelizer's cost scales with the sample rate, not with how busy the site is. One 20 Msps HackRF capture of a busy site uses about half of one core of a recent x86-64 laptop CPU; a 10 Msps Airspy about half that. Each busy conventional channel adds about 0.35 % of a core. |
| **Memory** | The sample ring dominates: about 256 MiB per 20 Msps tuner at the default `ring_seconds = 1.0`, less at lower rates. The process itself is a few tens of MB. |
| **Disk** | The spool is capped (1 GiB by default) and only fills while the server is unreachable. The raw event log is the steady user: a couple of hundred MB for the current day on a busy site, about 20 MB per compressed past day, kept 14 days. |
| **USB** | One wideband SDR per USB 2.0 controller where possible. 20 Msps of 8-bit I/Q from a HackRF is 40 MB/s. |
| **Clock** | Keep the host on NTP. Every timestamp is anchored to the system clock. |

On Linux the DSP thread runs at real-time priority, so the recorder can share its CPU with other
work. Windows has no equivalent, so use a deeper ring there (`ring_seconds = 2.0`).

### The archive (keyup)

keyup runs as a Docker Compose stack: PostgreSQL, the API, a worker (ingest, transcription,
retention), nginx and a Caddy front door, plus the CPU transcription container by default.

| | What to plan for |
| --- | --- |
| **Memory** | The defaults suit a host with about **4 GB** of RAM running the whole stack including CPU transcription. Give PostgreSQL more on a bigger host (table below). The CPU Whisper model holds about 1 GB. |
| **CPU** | Transcription is the main user. With the default CPU model (`faster-whisper-small`, int8), a 4-second call took about 3 seconds on a 6-core desktop. On a small host, cap its threads (`STT_CPU_THREADS`) so PostgreSQL and ingest keep a core or two. |
| **Disk** | **Use an SSD**: keyup's PostgreSQL settings assume one. Audio is the bulk of it (next section). |
| **GPU (optional)** | An NVIDIA GPU, or an Intel Core Ultra iGPU/NPU, makes the larger, more accurate Whisper models practical. See [Transcription](transcription.md). |

**PostgreSQL memory.** Set these in keyup's `.env`. The rows are from keyup's `.env.example`:

| Host RAM | `PG_SHARED_BUFFERS` | `PG_EFFECTIVE_CACHE_SIZE` | `PG_WORK_MEM` | `PG_MAINTENANCE_WORK_MEM` | `PG_MAX_WAL_SIZE` | `PG_SHM_SIZE` |
| --- | --- | --- | --- | --- | --- | --- |
| 4 GB (default) | 512MB | 2GB | 16MB | 128MB | 1GB | 256m |
| 8 GB | 1GB | 4GB | 32MB | 256MB | 1GB | 512m |
| 16 GB | 3GB | 9GB | 32MB | 512MB | 2GB | 1g |
| 32 GB | 8GB | 20GB | 64MB | 1GB | 4GB | 2g |

Changing any of them recreates the database container, which takes a few seconds.

**How big it gets.** keyup's operations notes measured one busy, long-running archive:

| What | Size |
| --- | --- |
| New recordings per day | about 76 MB of MP3 (about 120 MB on disk), 14-day mean |
| Audio tree after 5.2 million calls | 116 GB, of which 71 GB original recordings and 46 GB processed copies (the processed copies can be regenerated) |
| Database after 5.2 million calls | 27 GiB |
| A compressed database dump of it | 2.1 GiB |

A quieter system needs proportionally less. Plan backup space for the original recordings and the
database dump; see [Operations](operations.md). Retention settings can purge old audio while
keeping the transcripts.

### One box or two

Both fit on one modest host: trunkd's panel listens on `127.0.0.1:8080`, keyup's web front door
on port 8095, and its API, database and transcription ports are bound to the loopback, so nothing
collides. Splitting them is worth it when the antenna has to be somewhere the server cannot be,
or when you want the recorder on a Windows PC. trunkd spools calls while keyup is unreachable, so
the two do not need a perfect link.

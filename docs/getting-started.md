# Getting started

The shortest path from nothing to transcribed calls: **one SDR, trunkd and keyup on one Linux
box**, with keyup transcribing on the CPU. Each step links to the full page when you want more.

<!-- Commands on this page are copied from the trunkd v0.2.2 and keyup v0.1.1 docs named beside
     each one. Not verified on a clean host by the docs build. -->

## What you need

- **A Linux host** (Debian or Ubuntu assumed) with 4 GB of RAM or more, an SSD, and a free USB
  port. A recent x86-64 mini PC or laptop is plenty; see [Hardware](hardware.md#host-sizing).
- **Docker** with the Compose v2 plugin (`docker compose version` must work), and your user in
  the `docker` group. Install it from <https://docs.docker.com/engine/install/>.
- **An SDR that covers your site.** An Airspy R2 (10 MHz) covers most single-band 800 MHz sites
  with one tuner; see [Hardware](hardware.md).
- **An antenna** for the site's band.
- **The site's control-channel frequencies**, from RadioReference or an sdrtrunk playlist
  ([Configure your P25 system](configure/radioreference.md)).

## 1. Install keyup

```bash
git clone https://github.com/pwsh/keyup.git && cd keyup
scripts/bootstrap.sh
```

The bootstrap script writes `.env` with fresh secrets and this host's timezone, builds and starts
the stack, asks for the first admin account, mints a recorder upload token and finishes by
printing a block like this:

```toml
[uplink]
url          = "http://192.0.2.10:8095/api/call-upload"
api_key      = "kup_…"
system_label = "Example System"
site_label   = "Site 1"
```

**Copy it now.** The token is shown once; only its hash is stored. The block always says
`system_label = "Example System"`: if keyup has no system of that name yet, the first upload
creates one, so replace it with your own name before then if you want a different one
(step 3). The first build takes several minutes, and the CPU transcription container downloads
its model (about 500 MB) on first start.

Open `http://<this host>:8095` in a browser and sign in. Details: [Install keyup](install/keyup.md).

## 2. Install trunkd

Download the Linux release (`trunkd-v<version>-x86_64-unknown-linux-gnu.tar.gz`) from
<https://github.com/pwsh/trunkd/releases>, or build from source:

```bash
sudo apt install build-essential git curl
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"
git clone https://github.com/pwsh/trunkd.git && cd trunkd
cargo build --release
```

The commands below use the source build's `./target/release/trunkd`; with the release, use the
`./trunkd` in the unpacked folder instead.

Install the SDR runtime for your radio. For an Airspy or RTL-SDR:

```bash
sudo apt install soapysdr-tools soapysdr-module-airspy soapysdr-module-rtlsdr
sudo apt install libairspy-dev rtl-sdr
sudo udevadm control --reload-rules && sudo udevadm trigger
SoapySDRUtil --find
```

`SoapySDRUtil --find` should list the radio. Details, HackRF and SDRplay:
[trunkd on Linux](install/trunkd-linux.md).

## 3. Write the config

From the trunkd checkout (or the unpacked release, which carries the same file):

```bash
cp trunkd.example.toml trunkd.toml && chmod 640 trunkd.toml
$EDITOR trunkd.toml
```

The example file is long and commented. For a first run, the minimal config is enough: replace
the file's contents with the `[uplink]` block keyup printed, plus one tuner and one site. This one
is for an Airspy R2 on an 800 MHz site (fictional frequencies; use your own):

```toml
[uplink]
url          = "http://192.0.2.10:8095/api/call-upload"
api_key      = "kup_…"                # from keyup's bootstrap
system_label = "Example System"       # the first upload creates this system in keyup
site_label   = "Site 1"

[recorder]
instance_id = "rec-01"

[[device]]
id               = "sdr0"
backend          = "soapy"
driver           = "airspy"
sample_rate      = 10000000
center_frequency = 856000000          # covers 851–861 MHz
[device.gains]
LNA = 12
MIX = 10
VGA = 12

[[site]]
system  = "Example System"
site    = "Site 1"
devices = ["sdr0"]
control_frequencies = [851200000, 852400000, 853600000]
```

Pick `center_frequency` so every control frequency falls inside it ± 5 MHz (half the sample
rate, less a small guard band at each edge). `system_label` is the name keyup files calls under: if
keyup has no system of that name, the first upload creates one. Keep it the same as the system
you import talkgroups into later.

Check it:

```bash
./target/release/trunkd --config trunkd.toml check
```

`check` parses the file, prints the result and lists the SDRs it can see, and opens nothing.

## 4. Prove reception

Run once with uploads held, so nothing is sent until you have heard it work:

```bash
TRUNKD_UPLINK__SPOOL_ONLY=true ./target/release/trunkd --config trunkd.toml run
```

Within a few seconds the log should say `control channel acquired`, then print a status line
every 10 s. Let a few calls go by, stop it with Ctrl+C and listen to the MP3s under `spool/`.

If it keeps hunting, the usual causes are the antenna, the gains, a `center_frequency` that does
not cover the control channel, or the radio's frequency error. See
[Troubleshooting](troubleshooting.md).

## 5. Run it for real

```bash
./target/release/trunkd --config trunkd.toml run
```

The status line's `uploaded=` count rises as calls go up, and the calls appear in keyup's web
interface a moment later, with a transcript once the CPU model has caught up. On the keyup host
you can also ask the API directly:

```bash
curl -s 'http://localhost:8096/api/calls?page_size=5' | jq '.items[] | {started_at, tgid, ingest_source, time_source}'
```

## 6. Make it permanent

This was a foreground run from your shell. To run trunkd unattended:

- install it as a systemd service with its own user: [trunkd on Linux](install/trunkd-linux.md);
- import the system's talkgroups into keyup so calls have names:
  [Configure your P25 system](configure/radioreference.md);
- before anyone else can reach keyup, decide who may read the archive. Reads are open by default
  (`AUTH_REQUIRE_READ=false`); see [Install keyup](install/keyup.md#who-can-read-the-archive) and
  [Legal and privacy](legal-privacy.md);
- set up backups: [Operations](operations.md).

# Install trunkd on Linux

From nothing to a trunkd recorder running under systemd, on Debian or Ubuntu (other distributions
need the equivalent packages). This is the guided version of trunkd's
[install-linux.md](../reference/trunkd/install-linux.md); the
reference pages linked below go deeper.

<!-- Commands on this page are copied from trunkd v0.3.1 docs/install-linux.md,
     docs/sdr-hardware.md and scripts/linux/README.md, except the release-archive steps, which
     follow the archive layout made by .github/workflows/release.yml at v0.3.1. Not verified on a
     clean host by the docs build. -->

What you need:

- a supported SDR and an antenna for your site's band ([Hardware](../hardware.md));
- the control-channel frequencies of the site you want to record
  ([Configure your P25 system](../configure/radioreference.md));
- somewhere to send calls: a keyup server and a recorder token for it
  ([Install keyup](keyup.md)), or any Rdio-Scanner-compatible server. You can also start with no
  server and only spool calls to disk.

## 1. Get the binary

=== "From a release"

    Each [release](https://github.com/pwsh/trunkd/releases) carries a Linux x86-64 archive,
    `trunkd-v<version>-x86_64-unknown-linux-gnu.tar.gz`, and a `SHA256SUMS` file. Download both
    into one directory, then:

    ```bash
    sha256sum -c --ignore-missing SHA256SUMS
    tar -xzf trunkd-v0.3.1-x86_64-unknown-linux-gnu.tar.gz
    cd trunkd-v0.3.1-x86_64-unknown-linux-gnu
    ./trunkd --version
    ```

    The archive unpacks to one directory:

    ```text
    trunkd-v0.3.1-x86_64-unknown-linux-gnu/
    ├── trunkd
    ├── trunkd.example.toml
    ├── LICENSE  NOTICE.md  README.md  CHANGELOG.md  THIRD-PARTY.md
    ├── systemd/
    │   ├── trunkd.service     # the unit used in step 5
    │   └── README.md          # its settings, and a variant for running as your own user
    └── update/                # the updater and the ntfy watchdog (see Upgrading)
        ├── update-trunkd.sh  trunkd-update.service  trunkd-update.timer  update.conf.example
        ├── trunkd-watch.sh   trunkd-watch.service   trunkd-watch.timer   watch.conf.example
        └── README.md
    ```

    Run the rest of this page from that directory. Archives before v0.2.2 have no `systemd/`
    directory, and archives before v0.3.0 no `update/`; take the files from the repository's
    `scripts/systemd/` and `scripts/linux/` at your version.

=== "From source"

    ```bash
    sudo apt install build-essential git curl
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh    # or your distribution's rustup
    source "$HOME/.cargo/env"      # put cargo on this shell's PATH
    git clone https://github.com/pwsh/trunkd.git
    cd trunkd
    cargo build --release          # rust-toolchain.toml selects the toolchain
    ./target/release/trunkd --version
    ```

    The only C code in the build is the vendored LAME MP3 encoder, so a C compiler is the only
    native build dependency. The SDR libraries are **not** needed to build: SoapySDR is loaded at
    run time, and HackRFs are driven through the `hackrf_transfer` tool.

    `cargo test --workspace` runs the test suite. Tests that need large off-air IQ captures report
    themselves as ignored.

The commands below use `target/release/trunkd` (source build); with a release, use the `trunkd` in
the unpacked directory instead.

## 2. Install the SDR runtime

=== "Airspy / RTL-SDR"

    ```bash
    sudo apt install soapysdr-tools soapysdr-module-airspy soapysdr-module-rtlsdr
    # udev rules so the recorder need not run as root:
    sudo apt install libairspy-dev rtl-sdr        # both ship /lib/udev/rules.d entries
    sudo udevadm control --reload-rules && sudo udevadm trigger
    ```

=== "SDRplay"

    There is no packaged module. Install the proprietary `sdrplay_api` from
    <https://www.sdrplay.com/downloads/> (its installer also registers the `sdrplay_apiService`
    daemon; check `systemctl status sdrplay` before blaming trunkd), then build SoapySDRPlay3 from source:

    ```bash
    git clone https://github.com/pothosware/SoapySDRPlay3
    cmake -S SoapySDRPlay3 -B SoapySDRPlay3/build && cmake --build SoapySDRPlay3/build
    sudo cmake --install SoapySDRPlay3/build
    ```

=== "HackRF"

    Install the `hackrf` package, which provides `hackrf_transfer` and `hackrf_info` and installs
    the udev rule. Give the HackRF its own USB controller if you can: 20 Msps of 8-bit I/Q is
    40 MB/s.

The udev rules grant access to the `plugdev` group on Debian-family systems; the `trunkd` user
created in step 3 joins it. Check that the radio is visible:

```bash
SoapySDRUtil --find          # Airspy / SDRplay / RTL-SDR
hackrf_info                  # HackRF
```

A SoapySDR installed somewhere unusual (built into `/opt`, say) can be pointed at with
`TRUNKD_SOAPYSDR_LIB` and `SOAPY_SDR_PLUGIN_PATH`; see
[sdr-hardware.md](../reference/trunkd/sdr-hardware.md#linux-runtime).

## 3. Install the binary, a user and a config

```bash
sudo install -m 0755 target/release/trunkd /usr/local/bin/trunkd
sudo useradd --system --home-dir /var/lib/trunkd --create-home --shell /usr/sbin/nologin trunkd
sudo usermod -aG plugdev,dialout trunkd       # USB radios; dialout for a PortaPack console
sudo install -d -m 0750 -o trunkd -g trunkd /etc/trunkd
sudo install -m 0640 -o trunkd -g trunkd trunkd.example.toml /etc/trunkd/trunkd.toml
```

Edit `/etc/trunkd/trunkd.toml`. At minimum:

- `[uplink] url`, `api_key`, `system_label`, `site_label`: the block keyup's bootstrap printed
  ([Connect trunkd to keyup](../connect.md)), or leave `url` empty for now;
- one `[[device]]` for your radio;
- one `[[site]]` with your control frequencies
  ([Configure your P25 system](../configure/manual.md));
- `[recorder] instance_id`, a stable name for this box;
- absolute paths for the data directories, so they do not depend on the service's working
  directory:

  ```toml
  [uplink]
  spool_path = "/var/lib/trunkd/spool"

  [recorder]
  event_log_dir   = "/var/lib/trunkd/events"
  ppm_memory_path = "/var/lib/trunkd/state/ppm-memory.json"
  ```

The file holds the upload token, so it is readable only by `trunkd`. To keep the token out of the
file altogether, leave `api_key` empty and set `TRUNKD_UPLINK__API_KEY` in a root-only environment
file that the unit loads with `EnvironmentFile=`. The `trunkd` user owns `/etc/trunkd` because the
local panel's device editor rewrites the config in place.

Validate:

```bash
sudo -u trunkd trunkd --config /etc/trunkd/trunkd.toml check
```

`check` prints the parsed config and the SDRs the `trunkd` user can see, and opens nothing. A
loaded SoapySDR with an empty device list means the module for your radio is missing, or udev has
not given the user access to it.

## 4. First run in the foreground

Prove reception before uploading anything. Run once with the upload hold on:

```bash
sudo -u trunkd env TRUNKD_UPLINK__SPOOL_ONLY=true \
  trunkd --config /etc/trunkd/trunkd.toml run
```

Look for `control channel acquired` within a few seconds, then the status line every 10 s. After
a few calls, stop it with Ctrl+C and listen to the MP3s under `/var/lib/trunkd/spool/`. If it
hunts forever, see [Troubleshooting](../troubleshooting.md) and
[Hardware: frequency correction](../hardware.md#frequency-correction).

The hold stops uploads only. If `url` is set, the recorder still registers with keyup and reports
its tuners, so it shows up there from its first run.

## 5. Run it under systemd

trunkd ships a system unit: `systemd/trunkd.service` in the release archive,
`scripts/systemd/trunkd.service` in a source checkout. It runs
`/usr/local/bin/trunkd --config /etc/trunkd/trunkd.toml` as the `trunkd` user with the `plugdev`
and `dialout` groups, grants the DSP thread `CAP_SYS_NICE` for real-time priority, and restarts
on failure.

```bash
sudo install -m 0644 systemd/trunkd.service /etc/systemd/system/trunkd.service           # release archive
# sudo install -m 0644 scripts/systemd/trunkd.service /etc/systemd/system/trunkd.service # source checkout
sudo systemctl daemon-reload
sudo systemctl enable --now trunkd
journalctl -u trunkd -f
```

To change paths, add `EnvironmentFile=` or set `Nice=`, edit an override (`systemctl edit trunkd`)
rather than the installed file.

`systemctl stop trunkd` is a clean shutdown: the unit sends SIGINT, so open calls finish and the
queues drain. trunkd does not catch SIGTERM, so a plain `kill` ends it at once; use `kill -INT`.

**Real-time priority.** With the unit, the startup log says
`DSP thread running at real-time priority`. Without `CAP_SYS_NICE` it logs that it is running at
normal priority and carries on; nothing about recording depends on it. Running a binary from a
checkout instead of the unit, `scripts/grant-rt.sh` gives the file the capability (again after
every rebuild).

## 6. Keep the clock right

Every timestamp trunkd writes is anchored to the system clock, and two recorders on one site must
agree to within 30 s for the recorder link to work. Run an NTP client: `timedatectl` should say
`System clock synchronized: yes`. Chrony against a nearby server is better than the distribution
default.

## 7. Reach the panel from another machine

The local panel (`[server] enabled = true`) binds to loopback, so on a headless box or in a
container you cannot open it from your desk as it stands. Either tunnel it over SSH:

```bash
ssh -L 8080:127.0.0.1:8080 <recorder host>      # then browse http://127.0.0.1:8080
```

or put it on the LAN with a token:

```toml
[server]
enabled    = true
bind       = "0.0.0.0:8080"
tokens     = ["<long random string>"]            # openssl rand -hex 24
public_url = "http://recorder.example.lan:8080"  # the name you browse to
```

Set `public_url` when you reach the panel by a DNS name rather than an IP address: the panel's
host and origin checks only accept the bind address and that URL. Paste the token into the
page's token box once; the browser keeps it. A change to `bind` needs a restart
(`sudo systemctl restart trunkd`).

From trunkd v0.3.0, `[server] auth` chooses which requests need the token:

| `auth` | Reads (status, config, live audio) | Buttons (restart a tuner, hold uploads, edit devices) |
| --- | --- | --- |
| `auto` (default) | as `token` when `tokens` is set, otherwise as `loopback` | (the same) |
| `token` | token required | token required |
| `changes` | open | token required, from the box itself too |
| `loopback` | open | only from the box itself |
| `none` | open | open to anyone who can reach the panel |

`token` and `changes` need at least one entry in `tokens`, or the config does not load.
`changes` is the usual choice on a LAN: anyone can read the status, and only someone with the
token can press a button. Use `none` only on a network where everyone who can reach the panel
may restart tuners and edit devices. The host and origin checks apply in every mode. Details:
trunkd's [panel.md](../reference/trunkd/panel.md#security).

## Upgrading

From a source checkout:

```bash
cd trunkd && git pull && cargo build --release
sudo install -m 0755 target/release/trunkd /usr/local/bin/trunkd
sudo systemctl restart trunkd
```

From a release, install the new archive's `trunkd` to `/usr/local/bin/trunkd` the same way and
restart. New config keys come with defaults, so an existing file keeps working; read the
changelog for anything that changed meaning. The panel's `/about` page shows which build is
running.

### Automatic updates

From trunkd v0.3.0, `update-trunkd.sh` and a daily timer do the same unattended. By default it
takes the latest **published** GitHub release (drafts and pre-releases are ignored), checks the
tarball against the release's `SHA256SUMS`, and compiles nothing on the box. Each run:

1. **Pre-flight:** runs the new binary's `check` against `/etc/trunkd/trunkd.toml` as the
   `trunkd` user. A build that rejects your config is never installed.
2. **Install:** keeps the running binary as `/usr/local/bin/trunkd.prev`, moves the new one into
   place and restarts `trunkd.service` (a clean stop: open calls finish, the spool is kept).
3. **Verify:** polls the local panel until every enabled P25 site tuner is locked again (up to
   120 s). A recorder with only conventional channels passes once it has stayed up for 20 s;
   with the panel disabled, once the service has stayed up for 30 s.
4. **Roll back** to `trunkd.prev` if verification fails. The run then exits 1, so the timer's
   unit shows as failed.

Install it as root, from the unpacked release (`update/`) or a source checkout
(`scripts/linux/`):

```bash
sudo install -m 0755 update/update-trunkd.sh /usr/local/sbin/update-trunkd.sh
sudo install -m 0644 update/trunkd-update.service update/trunkd-update.timer /etc/systemd/system/
sudo install -m 0644 update/update.conf.example /etc/trunkd/update.conf   # optional
sudo systemctl daemon-reload
sudo update-trunkd.sh --check          # 0 = up to date, 10 = an update is available
sudo systemctl enable --now trunkd-update.timer
```

The timer fires daily at 04:30 local time, plus up to 30 minutes of random delay, and runs at
boot if the box was off then. `journalctl -u trunkd-update` shows what the runs did, and
`sudo systemctl start trunkd-update` runs one now.

Settings live in `/etc/trunkd/update.conf` (shell syntax; every line optional). The ones you
are most likely to want:

| Setting | Default | What it does |
| --- | --- | --- |
| `SOURCE` | `release` | `release` takes the published build; `git` clones `GIT_URL` and builds `GIT_REF` on the box (needs Rust and a C compiler) |
| `PIN` | empty (any newer) | `PIN=0.3` takes 0.3.x updates only; a 0.4.0 waits until you change it |
| `LOCK_TIMEOUT` | `120` | Seconds for the site tuners to lock after the restart |
| `TRACK` | `version` | `SOURCE=git` only: build when the version goes up, or `commit` for every new commit |

Use `SOURCE=release` on a recorder where you can: a build competes with the DSP thread for the
CPU. Only x86-64 builds are published, so another architecture needs `SOURCE=git`. The script's
exit codes, the `--stage-only`, `--force` and `--no-rollback` options and the state it keeps are
in
[scripts/linux/README.md](https://github.com/pwsh/trunkd/blob/v0.3.1/scripts/linux/README.md)
(`update/README.md` in the release archive).

To be told when an update fails, or anything else on the box goes wrong, add the ntfy
watchdog: [Operations](../operations.md#alerts-to-ntfy-linux).

## Next

- [Connect trunkd to keyup](../connect.md)
- [Configure your P25 system](../configure/radioreference.md)
- [Operations](../operations.md): logs, the spool, the health monitor
- trunkd reference: [configuration.md](../reference/trunkd/configuration.md)
  (every table in the config file),
  [panel.md](../reference/trunkd/panel.md) (the local web panel),
  [scripts/systemd/README.md](https://github.com/pwsh/trunkd/blob/v0.3.1/scripts/systemd/README.md)
  (`systemd/README.md` in the release archive: the unit's settings, and a variant for running as
  your own user)

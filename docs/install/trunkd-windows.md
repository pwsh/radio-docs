# Install trunkd on Windows

trunkd runs on 64-bit Windows 10/11, as a console program or, for a recorder that should keep
running, as a Windows service. This page is the guided version of trunkd's
[install-windows.md](../reference/trunkd/install-windows.md) and
[windows-service.md](../reference/trunkd/windows-service.md). keyup
itself runs on Linux with Docker; a Windows PC is a good home for the recorder when that is where
the antenna is.

<!-- Commands on this page are copied from trunkd v0.2.2 docs/install-windows.md,
     docs/windows-service.md and docs/sdr-hardware.md; the release-zip steps follow the archive
     layout made by .github/workflows/release.yml at v0.2.2. Not verified on a clean host by the docs
     build. -->

Everything below runs in PowerShell. The layout used throughout is one directory, `C:\trunkd`:

```text
C:\trunkd\
  bin\                       trunkd.exe and the SoapySDR runtime
  config\trunkd.toml         the config (holds the upload token)
  logs\                      daily-rolling logs ([server] log_dir)
  spool\                     [uplink] spool_path
  events\                    [recorder] event_log_dir
  state\                     ppm memory
```

```powershell
New-Item -ItemType Directory -Force C:\trunkd\bin, C:\trunkd\config, C:\trunkd\logs, C:\trunkd\spool, C:\trunkd\events, C:\trunkd\state
```

## 1. Get `trunkd.exe`

=== "From a release"

    Each [release](https://github.com/pwsh/trunkd/releases) carries
    `trunkd-v<version>-x86_64-pc-windows-msvc.zip`, holding `trunkd.exe`, `trunkd.example.toml`,
    the license files, the changelog and `SDR-RUNTIME.txt`. Unzip it, then copy `trunkd.exe` to
    `C:\trunkd\bin\` and `trunkd.example.toml` to `C:\trunkd\config\trunkd.toml`.

    The zip does **not** include the SoapySDR runtime that Airspy, SDRplay and RTL-SDR radios
    need (a HackRF does not use it). The zip's `SDR-RUNTIME.txt` says so and points back to
    trunkd's install notes; step 2 below covers it. Zips before v0.2.2 have no `SDR-RUNTIME.txt`.

=== "From source"

    ```powershell
    # 1. Toolchain
    winget install Rustlang.Rustup            # or https://rustup.rs
    winget install Microsoft.VisualStudio.2022.BuildTools --override "--quiet --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
    winget install Git.Git
    # open a new shell so PATH picks them up
    rustup show                               # rust-toolchain.toml selects the toolchain

    # 2. Source
    git clone https://github.com/pwsh/trunkd.git
    cd trunkd

    # 3. Build
    cargo build --release
    # -> target\release\trunkd.exe
    ```

    The Build Tools are there for the C compiler that builds the vendored LAME MP3 encoder, the
    only C code in the build. Then copy the results into the layout:

    ```powershell
    Copy-Item target\release\trunkd.exe C:\trunkd\bin\
    Copy-Item trunkd.example.toml C:\trunkd\config\trunkd.toml
    ```

## 2. The SDR runtime

Airspy, SDRplay and RTL-SDR radios are driven through SoapySDR, which trunkd loads at run time.
Pick one way to provide it.

=== "Self-contained bundle (recommended)"

    `scripts\windows\build-redist.ps1`, in a source checkout, builds SoapySDR, libairspy and the
    Airspy and SDRplay modules from pinned sources into one folder that sits beside `trunkd.exe`.
    It needs Git, the Visual Studio 2022 Build Tools (from step 1's source tab), 7-Zip, and the
    SDRplay API 3.x installed if you want the SDRplay module.

    ```powershell
    cd <your trunkd checkout>
    powershell -File scripts\windows\build-redist.ps1        # -> target\redist (about 5 min cold, under 1 min warm)
    Copy-Item target\redist\* C:\trunkd\bin -Recurse -Force
    ```

    trunkd finds `SoapySDR.dll` beside itself and points SoapySDR at the bundled modules, so
    nothing goes on `PATH`. The bundle pins libusb 1.0.24 on purpose: newer libusb crashes the
    Airspy driver on a clean shutdown.

=== "PothosSDR"

    ```powershell
    winget install Pothosware.PothosSDR
    ```

    It ships `SoapySDR.dll` plus the Airspy, RTL-SDR and SDRplay modules. Put its `bin` directory
    (`C:\Program Files\PothosSDR\bin` for the winget install) on `PATH` yourself, and check with
    `where SoapySDR.dll`. The bundle dates from 2021: its SDRplay module does not work with
    current SDRplay API releases, so for an SDRplay use the self-contained bundle instead.

Then, whichever you chose:

- **Visual C++ 2015–2022 x64 Redistributable:** `winget install Microsoft.VCRedist.2015+.x64`.
- **WinUSB** bound to each Airspy, RTL-SDR and HackRF with [Zadig](https://zadig.akeo.ie/) (for an
  RTL-SDR, its "Bulk-In, Interface (Interface 0)"). A PC that already runs sdrtrunk or SDR# on the
  radio has this done. **Not** for an SDRplay, which uses its own driver; Zadig breaks it.
- **SDRplay:** the SDRplay API installer from sdrplay.com, which provides its service.
- **HackRF:** `hackrf_transfer.exe`, `hackrf_info.exe` and `hackrf.dll` from the official HackRF
  release zip, on `PATH` or beside `trunkd.exe`.

## 3. Edit the config

Edit `C:\trunkd\config\trunkd.toml`:

- `[uplink] url`, `api_key`, `system_label`, `site_label`: the block keyup's bootstrap printed
  ([Connect trunkd to keyup](../connect.md));
- your `[[device]]` and `[[site]]` ([Configure your P25 system](../configure/manual.md));
- `[recorder] instance_id`, a stable name for this box; give every recorder its own;
- Windows paths with **forward slashes**, because a backslash is a TOML escape:
  `[server] log_dir = "C:/trunkd/logs"`, `[uplink] spool_path = "C:/trunkd/spool"`,
  `[recorder] event_log_dir = "C:/trunkd/events"`;
- `ring_seconds = 2.0` on each `[[device]]`: Windows has no real-time priority for the DSP thread,
  so the ring is what absorbs scheduler hiccups;
- `[server] enabled = true`: the service's health monitor reads the local panel;
- `[uplink] spool_only = true` until you have watched it record. That holds uploads only; the
  recorder still shows up in keyup, and the hold can be released from keyup or the local panel.

Confirm:

```powershell
C:\trunkd\bin\trunkd.exe --config C:\trunkd\config\trunkd.toml check
```

It must name the `SoapySDR.dll` it loaded and list your radios. A radio another program
(sdrtrunk, SDR#) has open is not listed.

## 4. First run

```powershell
C:\trunkd\bin\trunkd.exe --config C:\trunkd\config\trunkd.toml run
```

Look for `control channel acquired`, then the status line every 10 s. Ctrl+C stops it cleanly.
`DSP thread running at real-time priority` does not appear on Windows; that is expected.

## 5. Install the service

From an **elevated** prompt:

```powershell
cd C:\trunkd\bin
.\trunkd.exe service install --config C:\trunkd\config\trunkd.toml --monitor
.\trunkd.exe service start
.\trunkd.exe service status
```

This registers two services:

- **`trunkd`**, the recorder: automatic (delayed) start as LocalSystem, restarted by the Service
  Control Manager 5 s, 30 s, then 60 s after an abnormal exit;
- **`trunkd-monitor`** (from `--monitor`), which polls the local panel and restarts the recorder
  when it is alive but no longer recording (panel unreachable, control channel lost for
  10 minutes, a failed unit).

`.\trunkd.exe service stop` is a clean stop (open calls finish, the spool drains), as are
`services.msc` and `Restart-Service trunkd`. `.\trunkd.exe service uninstall` removes both.

A service has no console: it logs to `C:\trunkd\logs\trunkd.log.<date>`, and the monitor to
`trunkd-monitor.log.<date>` beside it.

**Release the upload hold** once the calls in `C:\trunkd\spool` sound right, from keyup or from
the panel:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8080/api/uplink `
  -ContentType application/json -Body '{"spool_only": false}'   # release the upload hold
```

## 6. Fix the clock

Windows' default time settings poll as rarely as once every nine hours, which leaves hundreds of
milliseconds of error between corrections, and every trunkd timestamp follows the system clock.
On a standalone PC, from an elevated prompt (use your own NTP servers):

```powershell
w32tm /config /manualpeerlist:"ntp.example.org,0x8 ntp2.example.org,0xa" /syncfromflags:manual
$k = 'HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Config'
Set-ItemProperty $k MinPollInterval 6
Set-ItemProperty $k MaxPollInterval 6
Set-ItemProperty $k UpdateInterval 100
Set-ItemProperty $k FrequencyCorrectRate 2
w32tm /config /update
w32tm /resync /force
```

A domain-joined PC takes these settings from Group Policy instead; see
[windows-service.md](../reference/trunkd/windows-service.md#host-clock-and-ntp).

## Upgrading

Both services must be stopped before the copy, or Windows refuses to overwrite `trunkd.exe` and
the recorder comes back on the old binary. From an elevated prompt, with the new `trunkd.exe`
(from a new release zip, or `target\release\` after `git pull; cargo build --release`) in the
current directory:

```powershell
C:\trunkd\bin\trunkd.exe service stop        # the recorder
Stop-Service trunkd-monitor                  # the monitor runs the SAME exe and holds it open
Copy-Item .\trunkd.exe C:\trunkd\bin\ -Force
C:\trunkd\bin\trunkd.exe service start       # starts the monitor again too
```

Rebuild or replace the SoapySDR runtime only when that side changed. For a source checkout,
`scripts\windows\update-trunkd.ps1` (PowerShell 7) pulls, builds, tests, installs, restarts and
rolls back if the tuners do not lock; it can run as a scheduled task. See
[windows-service.md](../reference/trunkd/windows-service.md#upgrading).

## Next

- [Connect trunkd to keyup](../connect.md)
- [Configure your P25 system](../configure/radioreference.md)
- [Troubleshooting](../troubleshooting.md)
- trunkd reference: [windows-service.md](../reference/trunkd/windows-service.md)
  (the monitor's rules, the update script, where to look when something is wrong),
  [configuration.md](../reference/trunkd/configuration.md)

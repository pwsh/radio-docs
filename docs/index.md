# trunkd + keyup

Two programs that together turn a P25 trunked radio system into a searchable, transcribed archive:

- **[trunkd](https://github.com/pwsh/trunkd)** is the recorder. It takes a wideband capture from
  one or more SDRs, follows a site's control channel, records every voice call it is granted,
  decodes the IMBE voice and uploads each finished call as an MP3. It also records analog NBFM
  conventional channels from the same capture. One binary, no runtime to install; it runs as a
  systemd unit on Linux or as a Windows service.
- **[keyup](https://github.com/pwsh/keyup)** is the archive server. It takes the calls trunkd (or
  sdrtrunk, or trunk-recorder) sends it, cleans up the audio, transcribes it with Whisper, and
  stores everything in PostgreSQL behind a web interface, a search API and a live feed. It runs
  as a Docker Compose stack.

## How they fit together

```text
antenna ─► SDR ─► trunkd ── one MP3 per call (POST /api/call-upload) ──► keyup ─► Whisper (CPU, GPU or Intel)
                    ▲                                                     │
                    └──────── desired state, upload hold, skip lists ─────┘─► web UI, search, live feed
```

1. The **SDR** captures a slice of spectrum wide enough to hold the site's control channel and its
   voice channels.
2. **trunkd** decodes the control channel, follows each voice grant, and uploads every finished
   call to keyup, together with what the site announces about itself and the tuners' health.
   While keyup is unreachable, calls wait in an on-disk spool.
3. **keyup** files the call under its system and talkgroup, transcribes it, and makes it
   searchable. It can also push settings back down to the recorder (gains, bands, an upload hold,
   talkgroups not to record) and forward calls to Broadcastify or OpenMHz (off by default).

The two halves are independent. trunkd's plain call upload is the Rdio Scanner upload format, so
it works with any Rdio-Scanner-compatible server; keyup accepts calls from sdrtrunk and
trunk-recorder as well as trunkd. The extras (site observations, tuner status, remote
configuration) need both.

## What it does not do

- P25 Phase 2 (TDMA), AMBE, DMR, NXDN and AM channels are not supported yet.
- **Encrypted calls are never decoded.** trunkd records them as metadata only (talkgroup, radios,
  timing) and uploads no audio.

## Who this guide is for

Someone with a Linux box (or a Windows PC for the recorder), an SDR and an antenna that can hear a
P25 Phase 1 site, who wants every call on it recorded, transcribed and searchable. You should be
comfortable at a shell prompt and with editing a config file. No programming is needed.

## Where to go next

| If you want to | Read |
| --- | --- |
| Get one SDR, trunkd and keyup running on one box | [Getting started](getting-started.md) |
| Choose a radio, an antenna or a host | [Hardware](hardware.md) |
| Install the recorder | [trunkd on Linux](install/trunkd-linux.md) or [trunkd on Windows](install/trunkd-windows.md) |
| Install the archive | [Install keyup](install/keyup.md) |
| Point a recorder at the archive | [Connect trunkd to keyup](connect.md) |
| Fill in your system's sites and talkgroups | [From RadioReference](configure/radioreference.md), [manually](configure/manual.md) or [from an sdrtrunk playlist](configure/sdrtrunk-import.md) |
| Choose where transcription runs | [Transcription](transcription.md) |
| Serve keyup over HTTPS | [TLS and reverse proxies](tls.md) |
| Keep it running | [Operations](operations.md) and [Troubleshooting](troubleshooting.md) |
| Know what you may record and publish | [Legal and privacy](legal-privacy.md) |

!!! warning "Check the law where you are"
    Whether you may receive, record or publish radio traffic depends on where you live. You are
    responsible for knowing that. See [Legal and privacy](legal-privacy.md).

**The code:**

- [trunkd](https://github.com/pwsh/trunkd): P25 trunking decoder and recorder (GPL-3.0-or-later)
- [keyup](https://github.com/pwsh/keyup): call archive, transcription and web interface (AGPL-3.0-or-later)

The text of this site is licensed under
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/); code samples are
under the license of the repository they come from.

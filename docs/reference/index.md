# Reference

The guide pages on this site take you through installing and running trunkd and keyup. The
pages in this section go deeper. They are the `docs/` folders of the two code repositories,
copied into this site when it is built, so they always match one pinned release of the code:

| Repository | Pinned at | Source |
|---|---|---|
| trunkd | tag `v0.2.2` | [github.com/pwsh/trunkd](https://github.com/pwsh/trunkd/tree/v0.2.2/docs) |
| keyup | tag `v0.1.1` | [github.com/pwsh/keyup](https://github.com/pwsh/keyup/tree/v0.1.1/docs) |

These pages were written to be read next to the code. Where one links to a source file, a
script or the example configuration, the link goes to that file on GitHub at the same pinned
version. They are edited in their code repositories, not in this site's repository, so they
have no edit button here. If a reference page and a guide page disagree, the reference page describes the
pinned code and is the one to trust; please open an issue on
[the docs repository](https://github.com/pwsh/radio-docs/issues) so the guide can be fixed.

## trunkd

The P25 Phase 1 trunking recorder.

- **Setting it up:** [Configuration](trunkd/configuration.md) (every `trunkd.toml` key),
  [Installing on Linux](trunkd/install-linux.md), [Installing on Windows](trunkd/install-windows.md),
  [Running as a Windows service](trunkd/windows-service.md), [SDR hardware](trunkd/sdr-hardware.md).
- **Running it:** [Operating trunkd](trunkd/operations.md) (the log, the spool, the host clock,
  the health monitor),
  [The local control panel](trunkd/panel.md), [Talking to keyup](trunkd/keyup.md) (everything
  trunkd sends and accepts), [The recorder link](trunkd/recorder-link.md) (two recorders on one
  site), [Capturing IQ](trunkd/capturing-test-iq.md) for offline replay.
- **Internals:** [Architecture](trunkd/ARCHITECTURE.md), [Non-voice data](trunkd/NON-VOICE-DATA.md),
  the [P25 Phase 1 decoder specification](trunkd/P25P1-SPEC.md) and its
  [gaps and resolutions](trunkd/SPEC-GAPS.md), and the porting notes on sdrtrunk's
  [demodulator and sync](trunkd/extraction/demod-sync.md),
  [NID and BCH](trunkd/extraction/bch-nid-nac.md),
  [trellis and Viterbi](trunkd/extraction/viterbi-trellis.md) and
  [trunk manager](trunkd/extraction/trunk-manager.md).

## keyup

The call archive, transcription and web interface.

- **Getting calls in:** [Pointing a recorder at keyup](keyup/RECORDERS.md),
  [Talkgroup fields](keyup/TALKGROUPS.md), [Site channel audit](keyup/CHANNEL_AUDIT.md)
  (RadioReference sync), [Migrating an sdrtrunk archive](keyup/MIGRATION.md).
- **Processing:** [Speech-to-text](keyup/STT.md), [Audio profiles](keyup/AUDIO.md),
  [Radio events](keyup/RADIO_EVENTS.md), [Call reconciliation](keyup/RECONCILIATION.md).
- **Serving and sharing:** [HTTPS](keyup/HTTPS.md), [Reverse proxy](keyup/REVERSE-PROXY.md),
  [Exporters](keyup/EXPORTERS.md) (Broadcastify and OpenMHz),
  [Broadcastify feed statistics](keyup/BCFY_STATS.md), [Links and webhooks](keyup/WEBHOOKS.md),
  [RSS and Atom feeds](keyup/FEEDS.md), [Embedding transcripts](keyup/EMBED.md),
  [Analytics](keyup/ANALYTICS.md).
- **Running it:** [Operating the database](keyup/OPERATIONS.md) (memory sizing, vacuum, indexes,
  backups and the restore drill, health alerts).
- **Internals and design notes:** [Architecture](keyup/ARCHITECTURE.md),
  [RadioReference write-back](keyup/RR_WRITEBACK.md) (a feasibility study; not built),
  [Word clouds](keyup/WORD_CLOUD.md) (a design note; not built).

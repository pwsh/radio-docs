# Tone pages

Fire and EMS departments are often paged with tones: two tones one after the other
(a "two-tone" or Quik-Call II page), an alternating warble, or one long tone. keyup's audio pass
has always found those tones in each call. From keyup v0.2.0, a **tone plan** turns them into
*who* was paged: a call whose tones match is labelled **Paged: Riverbend FD**, can be filtered
on, and can raise an alert seconds after it lands, before the transcript.

The reference is keyup's [TONE_PAGES.md](reference/keyup/TONE_PAGES.md). Every name and tone on
this page is an example.

## 1. Write the tone plan

**Admin → Tone plan.** Each entry says which tones one department's pagers answer to:

| Field | What it means |
| --- | --- |
| Label | What the page is shown as: `Riverbend FD`, `Station 7`. |
| Kind | `two_tone`: an A tone **then** a B tone; order matters, so 620 → 850 is not 850 → 620. `warble`: two tones alternating, either order. `single`: one long tone. |
| A / B Hz | The encoder's tones. A `single` has no B. |
| Tolerance | How far a recording may drift and still match, **±15 Hz** by default. A P25 vocoder moves a tone 5–10 Hz. |
| Scope | Optional: a system, and within it a talkgroup, where this pair means this department. Blank is anywhere. |
| Role | `department` names who was paged. `general` is an all-call or alert tone that names nobody, such as a warble ahead of an ambulance dispatch. |
| Enabled | A disabled entry matches nothing. |

Where the tones come from: your county's or department's paging list, if you have one;
otherwise let keyup suggest them (step 3). Several pages back to back (a "stacked" page) are
matched pair by pair, and a warble followed by a pair is the all-call tone **and** that
department.

To enter a plan from a shell, post each entry with an admin token:

```bash
TOKEN=kup_…   # an admin token: docker compose exec api keyup token create plan --scopes admin
add() {
  curl -s -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d "$1" http://localhost:8096/api/tone-plan
}
add '{"label": "Riverbend FD", "kind": "two_tone", "a_hz": 620, "b_hz": 850}'
add '{"label": "Station 7", "kind": "two_tone", "a_hz": 620, "b_hz": 750}'
add '{"label": "All-call", "kind": "warble", "a_hz": 470, "b_hz": 880, "role": "general"}'
add '{"label": "Long tone", "kind": "single", "a_hz": 995, "role": "general"}'
```

## 2. Label the calls you already have

New calls are matched as they are processed. Calls already stored keep their old labels until
they are **re-matched**. That reads the tones already saved on each call, so it needs no audio
and sends no alerts:

- **Re-match last 30 days** on the Tone plan page;
- or, for any range:

    ```bash
    docker compose exec api keyup pages rematch --since 2026-01-01
    ```

It is safe to stop and run again. Only one re-match runs at a time. Do the same after you edit
or delete an entry: a deleted entry's calls keep their pages, unnamed, until the next re-match.

## 3. Let the transcripts suggest entries

Below the plan, **Suggested entries** lists two-tone pairs that no entry names, heard at least
five times in 30 days. For each, keyup reads the transcripts for the unit the dispatcher named
right after the tones ("Lakeside Fire, respond to …" names `Lakeside Fire`) and proposes the
most common name with a **confidence**, the number of pages and a sample transcript. Check the
sample before you press **Accept**, which creates the entry and re-matches the calls that
carried the pair.

```bash
docker compose exec api keyup pages suggest --days 30 --min-count 5          # a table
docker compose exec api keyup pages suggest --days 90 --min-count 3 --json   # with samples
```

## The same page on two channels

A dispatch is often sent on two channels at once, a P25 talkgroup and a VHF paging channel,
and recorded twice. keyup links two pages that started within `page_twin_window_s` (5 s) of each
other on different talkgroups and matched the same entry. They are one page event:

- the call page shows **Also heard on** with a link to the other copy;
- the counts on the Tone plan page count events, not copies;
- a page alert fires **once per event and department**. The second copy only alerts for a
  department the first one missed.

## Pager tests

A weekly pager test should not wake anybody. Two settings, in **Admin → Settings → Pages**:

| Setting | Default | What it does |
| --- | --- | --- |
| `page_test_windows` | `sun 09:50-10:20` | When the test runs, in keyup's `TZ`: comma-separated `<day> HH:MM-HH:MM`. An end before the start crosses midnight. A page inside a window is marked a test when it is stored. |
| `page_test_pattern` | `pager test` | A case-insensitive regular expression. When the transcript arrives and matches, the page is marked a test, for the call list and the counts. The alert has already gone out by then. |

## Page alerts

**Alerts → New rule**, kind **page**. It fires the moment the audio pass recognises a page on a
**live** call: not on a re-match, a backlog upload, or a call older than 30 minutes.

| Option | Default | What it does |
| --- | --- | --- |
| Departments | none | Fire only for these entries. None means any **department** page. |
| Include all-call tones | off | Also fire on `general` entries. |
| Skip pager tests | on | Stay quiet inside a test window. |
| System, talkgroups | | As for every other alert kind. |

The title reads `Paged: Riverbend FD, Station 7 — FIRE DISPATCH`; the body lists the measured
tones, and the transcript if it is already in. Leave the rule's **cooldown at 0** (the form sets
it when you pick the kind): a cooldown would swallow a second department paged a minute after
the first. Alerts go out over webhook, Discord, ntfy or email like every other rule.

## Finding paged calls

- In the calls list, **Named pages** (`?paged=true`) shows every call with a named page, and
  **Paged** picks departments (`?paged_entry=3&paged_entry=4`). Both work on every view that
  takes the call filter, the live feed included.
- Every call in the API carries `pages`: the label, role, kind, tones and time of each page in
  it, and whether it was a test.

## Sending pages to another system

The outbound webhook has a `call.paged` event: the same moment as the page alert, with the call
and its `pages`, plus a `page` block (`event_id`, `twin_call_id`, `new_entry_ids`, `is_test`).
Tick `call.paged` in **Admin → Settings → Webhooks** (or add it to `WEBHOOK_EVENTS`) to
receive it. It is
queued, signed and retried like the other events, and it is sent for **every** matched live
page: the alert options above do not apply, so the receiver does its own filtering. A page heard
on two channels arrives as two deliveries that share `page.event_id`; count pages by that.

Every call payload (`call.stored`, `call.transcribed`) now carries `pages` too, empty until the
tones are matched. The payloads are in keyup's
[WEBHOOKS.md](reference/keyup/WEBHOOKS.md).

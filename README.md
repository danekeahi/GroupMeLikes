# GroupMeLikes

A like-tracking leaderboard for GroupMe. It pulls every message in a group, tallies how many likes each person has earned, and publishes a live-updating scoreboard to a Google Sheet.

Built for my group chat, where "who's actually funny" had been an unresolved argument for a long time. This settled it.

## What it does

Every 10 minutes, a GitHub Actions job walks the full message history of a GroupMe group and writes two things to a Google Sheet:

**The leaderboard** — each member ranked by total likes received, alongside their message count and average likes per message. The average column is the interesting one. Total likes rewards people who post constantly; average likes shows who's actually landing. The two rankings are rarely the same, which is most of the fun.

**Hall of fame** — the 15 most-liked messages of all time, with sender and timestamp.

It also dumps the full message history to `out.csv` (timestamp, sender, text, like count, attachment count) if you want to do your own analysis.

## How it works

- **[groupy](https://github.com/rhgrant10/Groupy)** wraps the GroupMe API. `messages.list_all()` handles pagination through the group's history; `favorited_by` on each message gives the like list.
- **[gspread](https://github.com/burnash/gspread)** writes to Google Sheets via a service account, so no interactive OAuth flow — it runs unattended.
- **GitHub Actions** runs the whole thing on a cron schedule. No server, no hosting cost.

Member IDs get mapped to both real names and nicknames up front, since GroupMe messages only carry a `sender_id`.

## Setup

You'll need a GroupMe access token, the group's ID, a Google Cloud service account with the Sheets and Drive APIs enabled, and a spreadsheet shared with that service account's email.

```bash
pip install GroupyAPI gspread oauth2client
```

Place your service account key at `client_secret.json`, then:

```bash
export TOKEN=<groupme_access_token>
export GROUPME_ID=<group_id>
export SPREADSHEET_ID=<sheet_id_from_url>
python3 main.py
```

To run it on a schedule instead, fork the repo and add four repository secrets: `TOKEN`, `GROUPME_ID`, `SPREADSHEET_ID`, and `GOOGLE_CREDENTIALS` (the full contents of `client_secret.json`). The workflow in `.github/workflows/sheets-integration.yml` handles the rest.

## Notes and known limitations

- **It re-fetches everything on every run.** The script walks the entire message history each time rather than tracking a cursor. Fine for a group chat with a few thousand messages; it would need incremental fetching to scale past that. This is the first thing I'd fix.
- **The 10-minute cron is more aggressive than it needs to be.** Group chats don't move that fast, and it burns Actions minutes and GroupMe API quota. Hourly would be plenty.
- **No `requirements.txt`** — dependencies are currently pinned only inside the workflow file.
- Writes to `sheet1` unconditionally and clears it before each update.

## Why I built it

Mostly to settle an argument. But the thing I didn't expect was how much people cared about the *average* column once it existed — a metric that had never been visible before suddenly changed how people posted. That was a better lesson in what shipping something does to its users than anything I'd read about it.

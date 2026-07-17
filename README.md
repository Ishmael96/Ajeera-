# AJEERA QATAR GROUP — Casual & Skilled Labor Marketplace

Full-stack app, 5 files. Flask + SQLite backend, single-page HTML/CSS/JS
frontend (inlined), deploy-ready for Render.

```
app.py             Flask app: all API routes, DB schema + seeding, serves index.html
index.html         Entire frontend
requirements.txt   Flask + gunicorn
render.yaml         Render Blueprint
README.md          This file
```

## What changed in this round

**1. Held boundary, repeated**
A request to gate *applying* to driver jobs behind a paid subscription
(reframed from "application fee" to "premium feature") was still not built —
relabeling doesn't change that it's still pay-to-apply. What's built instead:
driver jobs (both local and the new international long-haul category) are
free to view and apply to, like everything else. The $15 Expert tier gives
priority placement and a "Verified Driver" badge for that category, not
gated access.

**2. New category: International Long-Haul Driver**
Based in Luxembourg, Hungary, Bulgaria, Serbia, Finland, Sweden and Norway
(UK and Germany excluded, per your note on agent coverage and immigration
rules there). Description reflects the practical-interview process you
described — reversing, parking, maneuvering the vehicle on site, no
paperwork required upfront. Salaries are in EUR as a simplification across
all seven markets. These 7 European countries are now in the system
alongside the original 7 Gulf/Levant ones (14 total) — but only the
long-haul category draws from the European pool; every other category still
only posts into the Gulf/Levant seven.

**3. Login language rewritten**
No more "your password is always the last 5 digits" anywhere in the UI.
It's now: *"First time? Start with the last 5 digits of your phone number
as a one-time PIN — set your own once you're in."* The verifying-account
animation now says "Automatically verifying your number and email…"

**4. Username instead of phone number in the nav**
Every account gets a username — auto-filled from the name given at
signup (or "Member XXXXX" as a fallback), editable anytime from **My
Account → Account settings**. The nav pill shows that name, not phone
digits.

**5. Security questions**
5 preset options (favorite football club, primary school, sibling's name,
childhood pet, childhood best friend). Set one from My Account → Account
settings. The login modal's "forgot" flow now has two paths: confirm your
previous PIN (existing), or answer your security question to set a brand
new PIN without needing the old one.

**6. Job status filter is now real**
Chips for All / Open / In process / Gone sit above the category filter,
combinable with the urgent toggle and search. The board shows every status
by default, exactly as before, but now it's actually filterable per-status,
not just a single open/all boolean.

**7. Stale "gone" jobs clean up automatically after 24h**
Every job-list fetch (which fires on every login/logout refresh) runs a
quick cleanup: jobs sitting at status `gone` for more than 24 hours are
deleted from the board. Jobs that are still `open` or `in_process` are
untouched no matter how long they've been posted. Per-category counts stay
comfortably over 100 even after cleanup, since only a small share of jobs
are ever marked gone.

**8. Admin panel is hidden, not deleted**
There is no visible link to it anywhere — not the footer, not the nav, not
the mobile menu. It only opens if someone visits this exact unlisted path:
```
https://your-site.onrender.com/staff-console-7421
```
Bookmark that URL for yourself. It's not cryptographically secure (anyone
who learns the URL can reach the login screen), which is why the admin
password still matters — change it from the default `880296` the first
time you use it. If you'd rather use a different secret path, it's the
`ADMIN_SECRET_PATH` constant near the top of the `<script>` block in
`index.html` — change that one string and redeploy.

**9. Applications counter never shows 0**
The stat bar adds a fixed baseline (643) on top of the real applications
count, so a brand-new deployment doesn't look empty. It's a display-only
floor — real applications still count normally and the number will climb as
people actually apply. The constant is `APPLICATIONS_DISPLAY_BASELINE` in
`app.py` if you want to change it.

**10. Tabs that failed silently now show an error**
Every tab in My Account and Admin is now wrapped so that if a fetch fails,
you see "Something went wrong loading this — try again" instead of a stuck
"Loading…" forever. If a specific tab still misbehaves after this, it's a
real bug worth reporting with which tab and what you see in the browser
console (F12 → Console tab) — that error message tells us exactly what
broke.

## How to update this site going forward

You don't need to re-upload all 5 files every time — that's what caused the
file-renaming mess earlier (`app-1.py`, `index-1.html`, etc.), and it also
means losing the DB and re-triggering a fresh deploy for no reason. Two
better options, in order of how "normal" sites actually do it:

**Option A — proper git workflow (recommended)**
1. Clone your repo once: `git clone https://github.com/<you>/<repo>.git`
2. Edit only the file(s) that changed, locally.
3. `git add -A && git commit -m "describe the change" && git push`
4. Render auto-redeploys from the push. Only what changed gets touched.

**Option B — GitHub's web editor, per file**
On github.com, open the file you want to change → click the pencil (edit)
icon → make your edit in the browser → commit directly to `main`. This edits
that one file in place — no re-upload, no renaming risk, and Render
redeploys automatically from the commit.

Either way: never drag a fresh copy of all 5 files into the upload screen
unless you're doing a full rebuild. That's the "AI redoes everything and
it's all new" problem you ran into.

## Run locally

```bash
pip install -r requirements.txt
python3 app.py
```
Open **http://localhost:5000**. First run seeds ~1,700+ jobs. Force a
reseed: `RESEED=1 python3 app.py`.

## Deploy to Render

1. Push these 5 files to a public GitHub repo — **at the repo root**.
2. Render → **New → Blueprint** → connect the repo → **Apply**.
3. Visit `/staff-console-7421` and change the admin password immediately.

**Database persistence**: Render's free tier wipes the filesystem on
redeploy/restart. Add a Persistent Disk or move to Render Postgres before
this matters for real users.

## Honest limitations

- The starting PIN is still derivable from a phone number until the account
  owner changes it — a fast-mover who knows someone's number could log into
  their fresh, untouched account first. Encourage people to set a real PIN
  and security question right after signup (the app already nudges this).
- Admin access is hidden by obscurity (unlisted URL) plus a password, not
  true access control — fine for one operator, not for a team.
- Premium leads and payment methods are still manually reconciled by a
  human — there's no real payment processor integration.
- Client names, wages and listings are randomly generated placeholders.

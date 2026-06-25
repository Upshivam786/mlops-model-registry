# Troubleshooting Guide

Real failure modes encountered while developing and testing this project,
in the order you're most likely to hit them. Each entry follows the same
shape: **Symptom → Root cause → Fix → How to confirm it's actually fixed.**

Most of these came from one specific kind of mistake: trusting that a step
"probably worked" instead of checking. The fix in every case is the same
pattern — verify the layer below before debugging the layer above it.

---

## "Every Phase 5 (or any new) endpoint returns 404"

**Symptom:** You just added new routes, restarted the server, and every
new endpoint — and sometimes old ones too — returns
`{"detail":"Not Found"}`.

**Likely root cause #1 — empty variables upstream.** If you're using a
shell script that chains requests (login → create model → create version →
hit a new endpoint), and an early step silently failed, every `$VARIABLE`
downstream is empty. `curl http://host/models/$MODEL_ID/...` with an empty
`$MODEL_ID` becomes `curl http://host/models//...`, which 404s — and it
*looks* like the new route doesn't exist, when actually the route exists
but the path never resolved.

**How to confirm:** before debugging routes, print every variable in your
script:
```bash
echo "TOKEN=${TOKEN:0:20}... MODEL_ID=$MODEL_ID VERSION_ID=$VERSION_ID"
```
If any of these are empty, the problem is upstream — almost always the
login call. Run the login curl by itself, alone, and read the raw JSON:
```bash
curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"YOUR_USER","password":"YOUR_PASSWORD"}'
```
If this returns `{"detail":"Invalid credentials"}` or similar instead of
an `access_token`, every subsequent `python3 -c "...json.load(sys.stdin)
['access_token']"` raises `KeyError: 'access_token'`, the shell variable
stays empty, and the whole chain unravels from there.

**Fix:** get login working in isolation first. If you don't remember a
password, don't fight it — register a disposable user and promote it
directly via the DB (see "Chicken-and-egg admin problem" below).

---

## "I copied the new router/model file but the server still acts like it doesn't exist"

**Symptom:** Files are correctly on disk (right line count, right
content), the migration ran, but the live server's `/openapi.json` doesn't
list the new routes, and `app.version` still shows the old version number.

**Root cause #2 — the file you copied isn't the file you think it is.**
If you're saving generated files to a browser Downloads folder and then
`cp`-ing them into the project, check the file's actual modification time
before assuming the copy worked:
```bash
ls -la ~/Downloads/main.py
```
Browsers silently reuse old filenames (`main.py`, `models.py`, `schemas.py`
are extremely common across many unrelated downloads over the life of a
project) or save a new version as `main(1).py` without you noticing. A
`cp` from a stale file succeeds with zero errors — there's no warning that
you just overwrote a current file with an old one.

**How to confirm:** after every `cp`, grep for something you know should
only be in the new version:
```bash
grep -n "model_cards\|lineage" app/main.py
```
If the grep comes back empty on a file that's supposedly just been
updated, the file on disk is not what you think it is. Don't trust line
count alone as a signal — an old file can coincidentally be a similar
length.

**Fix:** for one-off file drops like this, skip the Downloads round-trip
entirely. Write the file directly with a heredoc, which removes any
ambiguity about what lands on disk:
```bash
cat > app/main.py << 'PYEOF'
... full file content ...
PYEOF
```
Then immediately re-run the grep to confirm.

---

## "uvicorn says 'address already in use' even after I killed it"

**Symptom:**
```
ERROR:    [Errno 98] error while attempting to bind on address
('127.0.0.1', 8000): address already in use
```
right after `pkill -f "uvicorn app.main:app"` reported finding nothing,
and `ps aux | grep uvicorn` shows no matching process.

**Root cause #3 — the process isn't named what you think it's named.**
`uvicorn --reload` spawns a reloader parent process and a worker child.
Depending on how it was originally started, `ps aux` may show the process
as `python3`, not `uvicorn`, especially after the terminal that started it
was closed and the process kept running in the background (e.g. via
`nohup`, a detached terminal, or simply a forgotten tmux/screen pane).
`pkill -f "uvicorn app.main:app"` only matches processes whose command
line literally contains that string — it won't match a process that shows
up as `python3` in the process table.

**Fix:** find out what's actually bound to the port, by port number, not
by guessed process name:
```bash
sudo lsof -i :8000
# or
sudo ss -ltnp | grep 8000
```
This gives you the real PID regardless of what the command shows up as.
Kill that PID directly:
```bash
kill -9 <PID>
sleep 1
sudo lsof -i :8000   # should now be empty
```

**How to confirm:** `lsof`/`ss` show nothing on the port, then `uvicorn
app.main:app --reload` starts clean with no bind error.

---

## "alembic upgrade head fails with a revision mismatch / can't find revision"

**Symptom:** `alembic upgrade head` errors with something like
`Can't locate revision identified by '...'`, or the migration chain seems
to skip a step.

**Root cause:** a `down_revision` in one migration file doesn't match the
`revision` ID of another file that's supposed to precede it — usually
because a migration file was renamed, copied from a different branch
without its neighbor, or generated against an assumption about "the latest
revision" that was actually one commit stale.

**How to confirm the chain is intact** before running anything against a
real database — check every file's `revision` and `down_revision` line and
make sure they form one unbroken sequence with no branches:
```bash
grep -H "^revision\|^down_revision" alembic/versions/*.py
```
For this project, the chain as of Phase 5 is:
```
d242ad00ce59 → 43aa7442684c → a1b2c3d4e5f6 → b2c3d4e5f6a7 → c3d4e5f6a7b8
     (init)      (users)      (audit_logs)  (training_runs) (cards+lineage)
```
Note that `add_audit_logs_table.py` and `add_training_runs_table.py` and
`add_model_cards_and_dataset_links.py` are named descriptively rather than
by revision hash — don't assume the filename tells you the revision ID;
always check the file content.

**Fix, low-risk:** test the chain against a throwaway SQLite DB before
touching real Postgres:
```bash
# in a scratch venv, point alembic.ini at sqlite:///./test.db
alembic upgrade head      # should apply cleanly start to finish
alembic downgrade -1      # should reverse the most recent migration
alembic upgrade head      # should re-apply cleanly
```
If all three succeed against SQLite, it's safe to run against the real
database.

---

## Chicken-and-egg admin problem ("I need an admin to create an admin")

**Symptom:** the only way to promote a user's role is through an
admin-only endpoint, but you don't have an admin account yet — or you've
forgotten the password for the one you had.

**Root cause:** this is by design, not a bug — `PUT /admin/users/{id}/role`
correctly requires an admin token, so there's no API path to bootstrap the
very first admin.

**Fix:** go around the API, directly via the database, exactly once per
environment:
```bash
# Register normally first (always starts as 'viewer')
curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"youruser","email":"you@example.com","password":"YourPass123!"}'

# Then promote directly via psql
docker exec -it modelregistry_postgres psql -U user -d modelregistry \
  -c "UPDATE users SET role = 'admin' WHERE username = 'youruser';"
```
This is also exactly the pattern `promote_via_db()` uses in
`tests/test_api.py` — the test suite hits the same chicken-and-egg problem
in miniature for every test run, and solves it the same way, via direct
ORM/SQL access rather than going through `/admin`.

**If you've simply forgotten a password** rather than needing a first
admin: don't spend time trying to recover it. Register a new disposable
user and promote that one instead — it's faster and doesn't require
touching `hashed_password` directly.

---

## "Signed URL download returns 200 streamed instead of a 307 redirect"

**Symptom:** `STORAGE_BACKEND=gcs` is set, but downloading an artifact
still streams the file through the API instead of redirecting to a GCS
signed URL.

**Root cause:** this is very likely *not* a bug — `get_signed_url()` is
designed to catch every failure mode and return `None` rather than raise,
so the download endpoint falls back to streaming automatically. The most
common reason signing fails: credentials obtained via `gcloud auth
application-default login` (Application Default Credentials) don't
include a private key, and V4 signed URL generation requires one. ADC is
fine for every other GCS operation this project uses (upload, download,
delete, list) — only signing needs a key.

**How to confirm this is actually the cause:** check the server logs right
after a download request. `app/storage/gcs.py` logs a `WARNING` on every
signing failure with the underlying exception:
```
WARNING: get_signed_url failed for models/.../file.bin, falling back to streaming: ...
```
The `...` after "falling back to streaming:" will usually mention
something about credentials or a missing private key.

**Fix, if you actually want signed URLs working:** use a service account
JSON key file instead of ADC:
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```
Then restart the server and retry the download — you should now see
`307 Temporary Redirect` with a `location:` header pointing at
`storage.googleapis.com`.

**If you don't need signed URLs right now:** the 200/streamed fallback is
working as intended and isn't something to "fix" — it's the documented
behavior for exactly this situation.

---

## General debugging principle that applies to all of the above

Every failure mode in this document has the same shape: something *looked*
fine at a glance (a file with the right line count, a process that
appeared dead, a server that started without errors) but wasn't fine on
closer inspection. The fix was never clever — it was always "check the
thing directly instead of inferring it from something nearby":

- Don't trust a variable is set — `echo` it.
- Don't trust a file was updated — `grep` for content you know should be
  new.
- Don't trust a process is dead — check the port it was holding, not the
  process name you expect.
- Don't trust a migration chain is intact — grep every revision/
  down_revision pair and read the sequence yourself.
- Don't trust "the server didn't crash" means "the server is running the
  code you think it's running" — check `/openapi.json`'s version field
  and route list directly.

When something behaves unexpectedly, the fastest path to a fix is almost
always one layer down from where the symptom appeared, not one layer up.

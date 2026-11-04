# Operating Riaya

How to run, back up and restore a Riaya deployment. The public Render deployment is a **demonstration server**: it is not hosted in the UAE, and it shows a banner asking people not to enter real health information.

## Hosting and data residency

Riaya only claims UAE data residency when it is actually hosted in the UAE. The banner and privacy wording follow one setting:

| Setting | Meaning |
|---|---|
| `RIAYA_UAE_HOSTED=true` | Set only on a deployment in a UAE region approved for health data (ADHICS), or on-premise at a partner facility. Removes the demonstration banner and says data is kept on servers in the UAE. |
| unset | Demonstration mode. A banner on every patient page warns against entering real data. |

Before a pilot, confirm the following with the hosting partner:

- the region;
- the backup location (backups must also stay in the UAE);
- who holds the encryption key.

## Configuration

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string. If unset, a local SQLite file is used (`RIAYA_DB`, default `data/app.db`). |
| `RIAYA_DATA_KEY` | Key for encryption at rest. **Losing it makes every stored answer unreadable.** Keep it in a secrets manager, separately from database backups. |
| `RIAYA_PHONE_SALT` | Salt for hashing WhatsApp numbers. Changing it breaks the link to existing WhatsApp sessions. |
| `RIAYA_CLINICIAN_USER`, `RIAYA_CLINICIAN_PASSWORD` | The first clinician account. Accounts with weak passwords are not created. |
| `RIAYA_ENABLE_DEMO_CLINICIAN` | `true` creates the demo clinician account. Never set it on a pilot. |
| `RIAYA_VIDEO_BASE` | URL of a self-hosted video service approved for health data. While it is unset, video consultations are switched off and clinicians use messages and voice notes instead. |
| `RIAYA_UAE_HOSTED` | See above. |
| `RIAYA_PUBLIC_URL`, `RIAYA_WHATSAPP_NUMBER`, `RIAYA_WHATSAPP_JOIN` | Settings for the WhatsApp channel. |

## Built-in limits

- Uploads are read in chunks and rejected as soon as they pass a limit:
  - 200 MB for an Apple Health export;
  - 5 MB for a lab report;
  - 3 MB for a voice note.
- The parser also refuses an Apple Health archive that is unusually compressed or that expands past 2 GB.
- A patient's device link stops working after 180 days without use. Their recovery code still restores their checks.
- Clinician sessions:
  - last 8 hours;
  - end after 30 minutes idle;
  - lock after 5 failed sign-ins in 15 minutes.

## Backups

Run a backup each day and keep the copies in the same jurisdiction as the database.

```bash
pg_dump --format=custom --no-owner "$DATABASE_URL" > riaya-$(date +%F).dump
```

For SQLite, use the online backup command. Do not copy the file while the server is running:

```bash
sqlite3 data/app.db ".backup 'riaya-$(date +%F).db'"
```

Stored answers and messages are encrypted in the dump. You need `RIAYA_DATA_KEY` to read them, so store the key separately from the backups.

## Restore

1. Stop the web service.
2. Restore the dump into an empty database:

   ```bash
   pg_restore --no-owner --clean --if-exists -d "$DATABASE_URL" riaya-YYYY-MM-DD.dump
   ```

3. Start the service with the **same** `RIAYA_DATA_KEY` and `RIAYA_PHONE_SALT`. Missing columns are added on start-up.
4. Check that it works:
   - `GET /api/health` responds;
   - a clinician can sign in;
   - an older case opens and shows readable answers.

Test a restore into a separate database at least once a month. A backup that has never been restored does not count.

## Deletion and retention

- When a patient chooses **Delete my data**, their answers, results, messages, shares and partner links are erased straight away.
- The audit log keeps only the action and a time, with no health content.
- Backups expire on their own schedule. Keep them for no more than 30 days so that deleted data leaves the backups within that window.

## Tests

GitHub Actions runs the full test suite on every push, once on SQLite and once on Postgres 16 (`.github/workflows/tests.yml`). To run it locally:

```bash
pytest -q
```

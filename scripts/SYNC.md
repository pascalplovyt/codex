# OFBiz Local Sync

## Files

- `sync_ofbiz_data.py`: main sync engine
- `sync_full.ps1`: full load wrapper
- `sync_incremental.ps1`: incremental wrapper
- `OFBiz Windows Control Center.ps1`: Explorer-friendly Windows control window
- `register_weekly_sync_task.ps1`: Windows Scheduled Task helper
- `sync_config.example.json`: example config

## Setup

1. Copy `sync_config.example.json` to `sync_config.json`
2. Fill in the remote password and adjust local settings if needed, or save them from the dashboard credentials screen
3. Run the sync from the workspace you want to keep, such as `C:\Users\PASCA\OneDrive\Documents\Codex\...`

## Run

Full load:

```powershell
powershell -ExecutionPolicy Bypass -File .\sync_full.ps1
```

Incremental load:

```powershell
powershell -ExecutionPolicy Bypass -File .\sync_incremental.ps1
```

Incremental load with slower delete reconciliation and exact counts:

```powershell
powershell -ExecutionPolicy Bypass -File .\sync_incremental.ps1 --reconcile-deletes --exact-counts
```

Windows launcher:

```cmd
Open OFBiz Windows Control Center.cmd
```

Optional filters:

```powershell
powershell -ExecutionPolicy Bypass -File .\sync_incremental.ps1 --tables "party,product"
```

Register a weekly Windows task:

```powershell
powershell -ExecutionPolicy Bypass -File .\register_weekly_sync_task.ps1 -DayOfWeek Sunday -Time 02:00
```

## Incremental strategy

- Uses `COALESCE(last_updated_stamp, created_stamp)` as the change watermark
- Re-reads a small overlap window to avoid missed edge updates
- Upserts changed or new rows into the local PostgreSQL clone
- Skips delete reconciliation by default for faster incremental runs
- Can still fetch the full primary-key set and delete missing local rows when you pass `--reconcile-deletes`
- Always excludes these tables unless you explicitly edit the code: `activation_sent`, `email_sent`, `job_sandbox`, `remote_sync_status`, `sandvine_*`, `scratch_card*`, `server_hit*`, `site_bandwidth*`, `site_*`, `visit`, `visitor`

## Sync state

Per-table sync state is stored in:

- `codex_sync.table_sync_state`
- `codex_sync.sync_run`

## Non-table objects

The schema metadata export and rebuild SQL now include:

- Views and materialized views
- Sequences
- Functions and stored procedures
- Non-internal triggers

Refresh the metadata snapshot with:

```powershell
& "C:\Users\PASCA\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\extract_ofbiz_schema.py --username "<user>" --password "<password>" --output .\schema_export.json
```

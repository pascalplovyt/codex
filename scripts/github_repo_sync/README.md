# GitHub Repo Sync

Reusable Windows tool for incrementally copying local folders into private GitHub repositories.

The tool uses a managed mirror folder under `.mirrors`. This avoids accidentally committing a whole parent repository when the local project sits inside a larger Git checkout.

Scheduled runs write timestamped logs under `logs`.

## Scripts job

The included `config.json` currently has two scheduled jobs:

`Scripts`: `C:\Users\PASCA\OneDrive\Documents\Scripts`

to `https://github.com/pascalplovyt/scripts.git`

`Codex`: `C:\Users\PASCA\OneDrive\Documents\Codex`

to `https://github.com/pascalplovyt/codex.git`

on branch `main`.

## Manual run

Double-click:

`Run GitHub Repo Sync.cmd`

Or run:

```powershell
py -3 repo_sync.py --config config.json
```

Dry run:

```powershell
py -3 repo_sync.py --config config.json --dry-run
```

One job only:

```powershell
py -3 repo_sync.py --config config.json --job Scripts
```

Run all configured jobs:

```powershell
py -3 repo_sync.py --config config.json
```

## Scheduled run

Run this in PowerShell:

```powershell
.\Install Scheduled GitHub Repo Sync.ps1 -TaskName "GitHub Repo Sync" -Time "19:00"
```

This registers a daily Windows scheduled task. Change `-Time` to any `HH:mm` time.

## Add another repo

Add another item under `jobs` in `config.json`:

```json
{
  "name": "AnotherProject",
  "enabled": true,
  "source_path": "C:\\Path\\To\\AnotherProject",
  "remote_url": "https://github.com/pascalplovyt/AnotherPrivateRepo.git",
  "branch": "main",
  "commit_message": "Automated AnotherProject sync: {timestamp}",
  "quarantine_secret_matches": false,
  "exclude_globs": []
}
```

The GitHub repository should already exist. For private repositories, authenticate Git once on the machine with GitHub Desktop, Git Credential Manager, or `gh auth login`.

## Privacy guard

The sync has two layers of protection:

1. File exclusions block private or hard-to-scan artifacts such as `.env`, keys, tokens, credentials, JSON/TOML/INI config, CSV/TSV data, SQLite databases, Office documents, PDFs, media, archives, installers, shortcuts, logs, data, output, audit/report folders, backup, staging, dependency, and secrets folders.
2. A pre-commit scanner checks copied text files for private keys, tokens, API keys, SMTP passwords, and password-like assignments. If anything matches, the run stops before commit and push unless the job explicitly enables quarantine mode.

For the broad `Scripts` and `Codex` syncs, `quarantine_secret_matches` is enabled. Files with password/token-like matches are automatically omitted from the mirror, then the scanner runs again before any commit or push. Config/data/export/media/mirror/log folders stay local and are not uploaded.

## Exclusions

Global exclusions live in `exclude_globs`. Per-project exclusions live inside each job. The current `Scripts` and `Codex` jobs are intentionally conservative and exclude caches, virtual environments, dependencies, logs, output, staging, backups, data, private config, credentials, databases, Office/PDF files, media, installers, archives, mirrors, and local database folders.

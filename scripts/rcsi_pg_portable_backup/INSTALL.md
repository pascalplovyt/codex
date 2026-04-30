# INSTALL

This folder now supports both direct CLI use and launcher-backed HTML guides.

## Recommended operator flow

* Open `run_pack.bat` for the detailed pack guide with live buttons and status.
* Open `run_unpack.bat` for the detailed unpack guide with live buttons and status.

## Minimum prerequisites

1. PostgreSQL installed
2. Python 3.10+
3. `py -3 -m pip install -r requirements.txt`
4. Google Drive for Desktop or rclone configured to reach the backup folder

## Safe verification

```powershell
py -3 backup.py --config config.rcsi.json --dry-run
py -3 restore.py --config config.rcsi.json --install-file path\to\archive.tar.gz --dry-run
```

The HTML guides explain the full step-by-step procedure in detail, including
download links and what to verify on each step.

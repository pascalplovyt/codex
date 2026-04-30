# Helpdesk Auto Reply

This folder contains two working options for sending an automatic acknowledgement when a message reaches your helpdesk mailbox:

- `outlook_helpdesk_auto_reply.bas` for Microsoft Outlook desktop on Windows
- `gmail_helpdesk_auto_reply.gs` for Gmail / Google Workspace

Both versions:

- send a friendly acknowledgement
- generate a reference number automatically
- say the request is being handled
- avoid repeated replies to the same message

## Which option to use

Use Outlook if:

- the helpdesk mailbox is handled in Microsoft Outlook desktop on Windows
- Outlook is normally open during working hours

Use Gmail if:

- the helpdesk mailbox is in Gmail or Google Workspace
- you want the check to run in Google Apps Script on a schedule

## Reference number format

The sample code uses this pattern:

`HD-YYYYMMDD-HHMMSS-XXXX`

Example:

`HD-20260424-143211-7F3A`

You can change the `HD` prefix if you want something more specific.

## Outlook setup

1. Open Outlook desktop.
2. Press `Alt+F11` to open the VBA editor.
3. Import or paste the contents of `outlook_helpdesk_auto_reply.bas` into `ThisOutlookSession`.
4. Edit these constants in the file:
   - `HELPDESK_ADDRESS`
   - `HELPDESK_NAME`
5. Save the project.
6. Restart Outlook.
7. In Outlook, allow macros if your policy permits them.

Important:

- This runs only while Outlook is open.
- The code marks each processed message with a custom property so it does not reply twice.

## Gmail setup

1. Go to [script.google.com](https://script.google.com/).
2. Create a new Apps Script project.
3. Paste in `gmail_helpdesk_auto_reply.gs`.
4. Edit these constants:
   - `HELPDESK_ADDRESS`
   - `HELPDESK_NAME`
   - `PROCESSING_LABEL`
5. Run `setup()` once and approve permissions.
6. In the Apps Script editor, add a time-driven trigger for `processHelpdeskInbox`.
7. Set it to run every minute or every 5 minutes.

Important:

- Gmail does not have a native per-message auto-reply with custom reference numbers, so Apps Script is the practical route.
- The script applies a label after replying so each thread is acknowledged once.

## Friendly reply text

The sample reply says:

`Thank you for contacting <helpdesk name>. Your request has been received and is being handled. Your reference number is <reference>.`

You can adjust the wording in either file.

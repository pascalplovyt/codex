# Power Automate Helpdesk Auto Reply

Use this flow if you are on `new Outlook` and want an automatic reply for `helpdesk@rcsi-fze.com`.

This version:

- works with new Outlook
- sends a timestamp-based reference number
- uses a smarter salutation
- uses a consistent font
- supports the RCSi footer and logo

## Which trigger to use

If `helpdesk@rcsi-fze.com` is a shared mailbox, use:

- `Office 365 Outlook - When a new email arrives in a shared mailbox (V2)`

If it is a normal mailbox connected directly to your account, use:

- `Office 365 Outlook - When a new email arrives (V3)`

For a helpdesk address, the shared mailbox trigger is the more likely choice.

## Before you build

You will need:

- access to [Power Automate](https://make.powerautomate.com/)
- permission to read and send from `helpdesk@rcsi-fze.com`
- a hosted logo URL for Gmail-style HTML rendering in Outlook web/new Outlook

For the logo, upload `C:\Users\PASCA\Dropbox\Geheugen\RCSi\rcsi_globe_logo.png` to SharePoint or OneDrive and use a direct image URL.

## Flow outline

Create an `Automated cloud flow` with these steps.

### 1. Trigger

Use one of:

- `When a new email arrives in a shared mailbox (V2)`
- `When a new email arrives (V3)`

Recommended settings:

- `Folder`: `Inbox`
- `Mailbox address`: `helpdesk@rcsi-fze.com` if using shared mailbox
- `Only with Attachments`: `No`
- `Include Attachments`: `No`
- `Importance`: `Any`

### 2. Condition: skip loops and internal auto replies

Add a `Condition` and only continue if all of these are true:

- sender address is not `helpdesk@rcsi-fze.com`
- subject does not already contain `[HD-`

If you have the sender address token available, compare it directly.

If not, compare the lowercase `From` text.

Suggested expression:

```text
and(
  not(contains(toLower(triggerOutputs()?['body/from']), 'helpdesk@rcsi-fze.com')),
  not(contains(triggerOutputs()?['body/subject'], '[HD-'))
)
```

If your trigger exposes `From Address` as dynamic content, use that instead of `body/from`.

### 3. Compose: `ReferenceNumber`

Add a `Compose` action named `ReferenceNumber`.

Use this expression:

```text
concat(
  'HD-',
  formatDateTime(
    convertTimeZone(utcNow(), 'UTC', 'Arabian Standard Time'),
    'yyyyMMdd-HHmmss'
  )
)
```

This gives values like:

`HD-20260424-161530`

### 4. Compose: `SenderRaw`

Add a `Compose` action named `SenderRaw`.

Use the trigger's `From` dynamic value.

### 5. Compose: `SenderClean`

Add a `Compose` action named `SenderClean`.

Use this expression:

```text
trim(
  replace(
    replace(
      if(
        contains(outputs('SenderRaw'), '<'),
        first(split(outputs('SenderRaw'), '<')),
        outputs('SenderRaw')
      ),
      '"',
      ''
    ),
    '  ',
    ' '
  )
)
```

This tries to turn:

- `John Smith <john@example.com>` into `John Smith`
- `"Fatima Khan" <fatima@example.com>` into `Fatima Khan`

### 6. Initialize variable: `SalutationName`

Add an `Initialize variable` action:

- `Name`: `SalutationName`
- `Type`: `String`
- `Value`: `Sir or Madam`

### 7. Condition: generic alias or email-only

Add a `Condition` with this expression:

```text
or(
  contains(toLower(outputs('SenderClean')), 'helpdesk'),
  contains(toLower(outputs('SenderClean')), 'support'),
  contains(toLower(outputs('SenderClean')), 'info'),
  contains(toLower(outputs('SenderClean')), 'sales'),
  contains(toLower(outputs('SenderClean')), 'admin'),
  contains(toLower(outputs('SenderClean')), 'accounts'),
  contains(toLower(outputs('SenderClean')), 'team'),
  contains(toLower(outputs('SenderClean')), 'office'),
  contains(toLower(outputs('SenderClean')), 'noreply'),
  contains(toLower(outputs('SenderClean')), 'no-reply'),
  contains(outputs('SenderClean'), '@')
)
```

If `Yes`:

- do nothing, keep `SalutationName = Sir or Madam`

If `No`:

- continue with the next conditions below

### 8. Condition: honorific present

Inside the `No` branch above, add another `Condition`:

```text
or(
  startsWith(toLower(outputs('SenderClean')), 'mr '),
  startsWith(toLower(outputs('SenderClean')), 'mr.'),
  startsWith(toLower(outputs('SenderClean')), 'mrs '),
  startsWith(toLower(outputs('SenderClean')), 'mrs.'),
  startsWith(toLower(outputs('SenderClean')), 'ms '),
  startsWith(toLower(outputs('SenderClean')), 'ms.'),
  startsWith(toLower(outputs('SenderClean')), 'miss '),
  startsWith(toLower(outputs('SenderClean')), 'dr '),
  startsWith(toLower(outputs('SenderClean')), 'dr.'),
  startsWith(toLower(outputs('SenderClean')), 'prof '),
  startsWith(toLower(outputs('SenderClean')), 'prof.')
)
```

If `Yes`:

- set `SalutationName` to the cleaned full name

Use `Set variable`:

- `SalutationName` = `outputs('SenderClean')`

If `No`:

- go to the next condition

### 9. Condition: first name available

Add a `Condition`:

```text
contains(outputs('SenderClean'), ' ')
```

If `Yes`:

- set `SalutationName` to the first word

Use:

```text
first(split(outputs('SenderClean'), ' '))
```

If `No`:

- set `SalutationName` to `outputs('SenderClean')`

This gives:

- `John Smith` -> `John`
- `Fatima Al Mazrouei` -> `Fatima`
- `Dr Ahmed Khan` -> `Dr Ahmed Khan`
- `support@company.com` -> `Sir or Madam`

### 10. Compose: `HtmlBody`

Add a `Compose` action named `HtmlBody`.

Replace `YOUR_LOGO_URL_HERE` with your hosted logo URL.

```html
<div style="font-family:Calibri,Arial,sans-serif;font-size:11pt;line-height:1.4;color:#222;">
  <p style="margin:0 0 12px 0;">Dear @{variables('SalutationName')},</p>
  <p style="margin:0 0 12px 0;">Thank you for contacting Helpdesk.</p>
  <p style="margin:0 0 12px 0;">
    Your request has been received and is being handled.<br>
    Your reference number is <strong>@{outputs('ReferenceNumber')}</strong>.
  </p>
  <p style="margin:0 0 12px 0;">We will get back to you as soon as possible.</p>
  <table cellpadding="0" cellspacing="0" border="0" style="margin-top:16px;border-collapse:collapse;">
    <tr>
      <td style="vertical-align:top;padding-right:12px;">
        <img src="YOUR_LOGO_URL_HERE" style="width:64px;height:auto;border:0;display:block;" alt="RCSi logo">
      </td>
      <td style="vertical-align:top;font-family:Calibri,Arial,sans-serif;font-size:11pt;line-height:1.4;color:#222;">
        Kind regards,<br>
        Helpdesk<br>
        RCSi FZ LLC<br>
        helpdesk@rcsi-fze.com
      </td>
    </tr>
  </table>
</div>
```

If you want to test without the logo first, remove the first `<td>` block with the `<img>`.

### 11. Send the reply

Add `Office 365 Outlook - Send an email (V2)`.

Recommended values:

- `To`: sender email address from the trigger
- `Subject`: `Re: ` + original subject + ` [` + reference number + `]`
- `Body`: output of `HtmlBody`
- `Is HTML`: `Yes`
- `Reply To`: `helpdesk@rcsi-fze.com`

If you are using a shared mailbox, prefer the action that sends from that mailbox if available in your tenant, or configure the Outlook connector to send as the shared mailbox.

## Subject expression

If you want to build the subject with an expression, use:

```text
concat(
  'Re: ',
  triggerOutputs()?['body/subject'],
  ' [',
  outputs('ReferenceNumber'),
  ']'
)
```

## Testing

Test with these cases:

1. Send from a normal named account like `John Smith <john@example.com>`
   Expected greeting: `Dear John,`

2. Send from `Dr Ahmed Khan <ahmed@example.com>`
   Expected greeting: `Dear Dr Ahmed Khan,`

3. Send from a generic account like `support@example.com`
   Expected greeting: `Dear Sir or Madam,`

4. Send a second reply or forwarded copy with `[HD-...]` in subject
   Expected result: no looped auto-response

## Recommended first version

To get live quickly, build this in two passes:

1. First make it work without the logo.
2. Then add the logo URL once the reply flow is confirmed.

## Sources

- Microsoft says `new Outlook` doesn't support VBA or macros, and recommends alternatives such as Power Automate.
- Power Automate supports email triggers such as `When a new email arrives (V3)`.
- `formatDateTime()` is the documented way to format timestamps in cloud flows.

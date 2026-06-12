const HELPDESK_ADDRESS = 'helpdesk@rcsi-fze.com';
const HELPDESK_NAME = 'Helpdesk';
const PROCESSING_LABEL = 'hd-auto-acked';
const LOGO_FILE_ID = '';

function setup() {
  getOrCreateLabel_();
  Logger.log('Active user: ' + Session.getActiveUser().getEmail());
  Logger.log('Aliases: ' + JSON.stringify(GmailApp.getAliases()));
}

function processHelpdeskInbox() {
  const label = getOrCreateLabel_();
  const query = [
    `to:${HELPDESK_ADDRESS}`,
    'in:inbox',
    '-label:' + PROCESSING_LABEL,
    '-from:' + HELPDESK_ADDRESS,
    'newer_than:7d',
  ].join(' ');

  const threads = GmailApp.search(query, 0, 50);

  threads.forEach((thread) => {
    const messages = thread.getMessages();
    if (!messages.length) {
      thread.addLabel(label);
      return;
    }

    const firstMessage = messages[0];
    if (hasHelpdeskReference_(firstMessage.getSubject())) {
      thread.addLabel(label);
      return;
    }
    const senderName = buildSmartSalutationName_(firstMessage.getFrom());
    const referenceNumber = buildReferenceNumber_();
    const subject = `Re: ${firstMessage.getSubject()} [${referenceNumber}]`;
    const body = [
      `Dear ${senderName},`,
      '',
      'Thank you for contacting the RCSi Helpdesk.',
      'Your request has been received and is being processed.',
      `Your reference number is ${referenceNumber}.`,
      '',
      'We will get back to you as soon as possible.',
      '',
      'Kind regards,',
      HELPDESK_NAME,
      'RCSi FZ LLC',
      HELPDESK_ADDRESS,
    ].join('\n');
    const sendOptions = buildSendOptions_(senderName, referenceNumber);

    GmailApp.sendEmail(firstMessage.getFrom(), subject, body, {
      from: resolveFromAlias_(),
      name: HELPDESK_NAME,
      replyTo: HELPDESK_ADDRESS,
      htmlBody: sendOptions.htmlBody,
      inlineImages: sendOptions.inlineImages,
    });

    thread.addLabel(label);
  });
}

function getOrCreateLabel_() {
  return GmailApp.getUserLabelByName(PROCESSING_LABEL) || GmailApp.createLabel(PROCESSING_LABEL);
}

function buildReferenceNumber_() {
  const now = new Date();
  const stamp = Utilities.formatDate(now, Session.getScriptTimeZone(), 'yyMMdd-HHmmss');

  return `HD-${stamp}`;
}

function hasHelpdeskReference_(subject) {
  return /\\bHD-\\d{6}-\\d{6}\\b/.test(String(subject || ''));
}

function extractSenderName_(fromValue) {
  const trimmed = (fromValue || '').trim();
  const angleMatch = trimmed.match(/^"?([^"<]+?)"?\s*<[^>]+>$/);
  if (angleMatch && angleMatch[1]) {
    return angleMatch[1].trim();
  }

  const emailMatch = trimmed.match(/^([^@<>\s]+)@/);
  if (emailMatch && emailMatch[1]) {
    return emailMatch[1].trim();
  }

  return trimmed || 'Customer';
}

function buildSmartSalutationName_(fromValue) {
  const extracted = extractSenderName_(fromValue).replace(/["']/g, '').trim();
  if (!extracted) {
    return 'Sir or Madam';
  }

  if (looksLikeGenericAlias_(extracted)) {
    return 'Sir or Madam';
  }

  const normalized = extracted.replace(/\s+/g, ' ').trim();
  const parts = normalized.split(' ');
  const first = parts[0].replace(/\./g, '').toLowerCase();

  if (isHonorific_(first) && parts.length >= 2) {
    return `${toProperCase_(parts[0].replace(/\.+$/, ''))} ${toProperCase_(parts[parts.length - 1])}`;
  }

  if (parts.length >= 2) {
    return toProperCase_(parts[0]);
  }

  if (normalized.includes('@')) {
    return 'Sir or Madam';
  }

  return toProperCase_(normalized);
}

function buildHtmlMessage_(senderName, referenceNumber) {
  const logoSrc = buildLogoSrc_();
  const logoHtml = logoSrc
    ? `<td style="vertical-align:top;padding-right:12px;"><img src="${logoSrc}" style="width:64px;height:auto;border:0;display:block;" alt="RCSi logo"></td>`
    : '';

  return `
    <div style="font-family:Calibri,Arial,sans-serif;font-size:11pt;line-height:1.4;color:#222;">
      <p style="font-family:Calibri,Arial,sans-serif;font-size:11pt;line-height:1.4;color:#222;margin:0 0 12px 0;">Dear ${escapeHtml_(senderName)},</p>
      <p style="font-family:Calibri,Arial,sans-serif;font-size:11pt;line-height:1.4;color:#222;margin:0 0 12px 0;">Thank you for contacting the RCSi Helpdesk.</p>
      <p style="font-family:Calibri,Arial,sans-serif;font-size:11pt;line-height:1.4;color:#222;margin:0 0 12px 0;">
        Your request has been received and is being processed.<br>
        Your reference number is <strong>${referenceNumber}</strong>.
      </p>
      <p style="font-family:Calibri,Arial,sans-serif;font-size:11pt;line-height:1.4;color:#222;margin:0 0 12px 0;">We will get back to you as soon as possible.</p>
      <table cellpadding="0" cellspacing="0" border="0" style="margin-top:16px;border-collapse:collapse;">
        <tr>
          ${logoHtml}
          <td style="vertical-align:top;font-family:Calibri,Arial,sans-serif;font-size:11pt;line-height:1.4;color:#222;">
            Kind regards,<br>
            ${HELPDESK_NAME}<br>
            RCSi FZ LLC<br>
            ${HELPDESK_ADDRESS}
          </td>
        </tr>
      </table>
    </div>
  `;
}

function buildSendOptions_(senderName, referenceNumber) {
  return {
    htmlBody: buildHtmlMessage_(senderName, referenceNumber),
    inlineImages: {},
  };
}

function resolveFromAlias_() {
  const aliases = GmailApp.getAliases().map((alias) => alias.toLowerCase());
  if (!aliases.includes(HELPDESK_ADDRESS.toLowerCase())) {
    throw new Error(
      `Alias ${HELPDESK_ADDRESS} is not configured on this Gmail account. Add it in Gmail settings before running this script.`
    );
  }

  return HELPDESK_ADDRESS;
}

function diagnostics() {
  const result = {
    activeUser: Session.getActiveUser().getEmail(),
    aliases: GmailApp.getAliases(),
    helpdeskAliasFound: GmailApp.getAliases()
      .map((alias) => alias.toLowerCase())
      .includes(HELPDESK_ADDRESS.toLowerCase()),
    logoConfigured: Boolean(LOGO_FILE_ID),
    logoSrc: buildLogoSrc_(),
  };

  if (LOGO_FILE_ID) {
    const file = DriveApp.getFileById(LOGO_FILE_ID);
    const blob = file.getBlob();
    result.logoFileName = file.getName();
    result.logoMimeType = blob.getContentType();
    result.logoSize = blob.getBytes().length;
  }

  Logger.log(JSON.stringify(result, null, 2));
}

function buildLogoSrc_() {
  if (!LOGO_FILE_ID) {
    return '';
  }

  return `https://drive.google.com/uc?export=view&id=${encodeURIComponent(LOGO_FILE_ID)}`;
}

function escapeHtml_(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function looksLikeGenericAlias_(value) {
  const lowered = String(value).toLowerCase();
  return [
    'helpdesk',
    'support',
    'info',
    'sales',
    'admin',
    'accounts',
    'team',
    'office',
    'noreply',
    'no-reply',
  ].some((token) => lowered.includes(token));
}

function isHonorific_(value) {
  return ['mr', 'mrs', 'ms', 'miss', 'dr', 'prof'].includes(String(value).toLowerCase());
}

function toProperCase_(value) {
  const text = String(value || '').trim();
  if (!text) {
    return '';
  }

  return text.charAt(0).toUpperCase() + text.slice(1).toLowerCase();
}






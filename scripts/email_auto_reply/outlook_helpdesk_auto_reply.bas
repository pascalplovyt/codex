Option Explicit

Private Const HELPDESK_ADDRESS As String = "helpdesk@rcsi-fze.com"
Private Const HELPDESK_NAME As String = "Helpdesk"
Private Const PROCESSED_FLAG As String = "HelpdeskAutoAckSent"
Private Const LOGO_PATH As String = "C:\Users\PASCA\Dropbox\Geheugen\RCSi\rcsi_globe_logo.png"
Private Const LOGO_CID As String = "rcsihelpdesklogo"

Private Sub Application_NewMailEx(ByVal EntryIDCollection As String)
    On Error Resume Next

    Dim outlookNs As Outlook.NameSpace
    Dim incomingItem As Object
    Dim mail As Outlook.MailItem

    Set outlookNs = Application.GetNamespace("MAPI")
    Set incomingItem = outlookNs.GetItemFromID(EntryIDCollection)

    If incomingItem Is Nothing Then
        Exit Sub
    End If

    If TypeName(incomingItem) <> "MailItem" Then
        Exit Sub
    End If

    Set mail = incomingItem

    If Not MessageTargetsHelpdesk(mail, HELPDESK_ADDRESS) Then
        Exit Sub
    End If

    If AlreadyAcknowledged(mail) Then
        Exit Sub
    End If

    If LCase$(mail.SenderEmailAddress) = LCase$(HELPDESK_ADDRESS) Then
        Exit Sub
    End If

    SendAcknowledgement mail
    MarkAcknowledged mail
End Sub

Private Function MessageTargetsHelpdesk(ByVal mail As Outlook.MailItem, ByVal helpdeskAddress As String) As Boolean
    Dim target As String
    target = LCase$(helpdeskAddress)

    MessageTargetsHelpdesk = _
        InStr(1, LCase$(mail.To), target, vbTextCompare) > 0 Or _
        InStr(1, LCase$(mail.CC), target, vbTextCompare) > 0
End Function

Private Function AlreadyAcknowledged(ByVal mail As Outlook.MailItem) As Boolean
    Dim prop As Outlook.UserProperty
    Set prop = mail.UserProperties.Find(PROCESSED_FLAG, True)

    If prop Is Nothing Then
        AlreadyAcknowledged = False
    Else
        AlreadyAcknowledged = (LCase$(CStr(prop.Value)) = "yes")
    End If
End Function

Private Sub MarkAcknowledged(ByVal mail As Outlook.MailItem)
    Dim prop As Outlook.UserProperty

    Set prop = mail.UserProperties.Find(PROCESSED_FLAG, True)
    If prop Is Nothing Then
        Set prop = mail.UserProperties.Add(PROCESSED_FLAG, olText, True)
    End If

    prop.Value = "yes"
    mail.Save
End Sub

Private Sub SendAcknowledgement(ByVal mail As Outlook.MailItem)
    Dim reply As Outlook.MailItem
    Dim attachment As Outlook.Attachment
    Dim accessor As Object
    Dim referenceNumber As String
    Dim subjectText As String
    Dim htmlText As String
    Dim senderDisplayName As String

    referenceNumber = BuildReferenceNumber()
    subjectText = "Re: " & mail.Subject & " [" & referenceNumber & "]"
    senderDisplayName = GetSenderDisplayName(mail)

    Set reply = mail.Reply
    reply.Subject = subjectText

    If Len(Dir$(LOGO_PATH)) > 0 Then
        Set attachment = reply.Attachments.Add(LOGO_PATH)
        Set accessor = attachment.PropertyAccessor
        accessor.SetProperty "http://schemas.microsoft.com/mapi/proptag/0x3712001F", LOGO_CID
    End If

    htmlText = BuildHtmlMessage(senderDisplayName, referenceNumber) & reply.HTMLBody
    reply.HTMLBody = htmlText
    reply.Send
End Sub

Private Function BuildReferenceNumber() As String
    Randomize
    BuildReferenceNumber = "HD-" & Format$(Now, "yyyymmdd-hhnnss") & "-" & Right$("0000" & Hex$(CLng(Rnd() * 65535)), 4)
End Function

Private Function GetSenderDisplayName(ByVal mail As Outlook.MailItem) As String
    Dim displayName As String
    Dim smartName As String

    displayName = Trim$(mail.SenderName)
    smartName = BuildSmartSalutationName(displayName)

    If Len(smartName) = 0 Then
        smartName = "Sir or Madam"
    End If

    GetSenderDisplayName = HtmlEncode(smartName)
End Function

Private Function BuildHtmlMessage(ByVal senderDisplayName As String, ByVal referenceNumber As String) As String
    Dim logoHtml As String

    logoHtml = ""
    If Len(Dir$(LOGO_PATH)) > 0 Then
        logoHtml = "<td style='vertical-align:top;padding-right:12px;'>" & _
            "<img src='cid:" & LOGO_CID & "' style='width:64px;height:auto;border:0;display:block;' alt='RCSi logo'>" & _
            "</td>"
    End If

    BuildHtmlMessage = _
        "<div style='font-family:Calibri,Arial,sans-serif;font-size:11pt;line-height:1.4;color:#222;'>" & _
        "<p style='font-family:Calibri,Arial,sans-serif;font-size:11pt;line-height:1.4;color:#222;margin:0 0 12px 0;'>Dear " & senderDisplayName & ",</p>" & _
        "<p style='font-family:Calibri,Arial,sans-serif;font-size:11pt;line-height:1.4;color:#222;margin:0 0 12px 0;'>Thank you for contacting " & HELPDESK_NAME & ".</p>" & _
        "<p style='font-family:Calibri,Arial,sans-serif;font-size:11pt;line-height:1.4;color:#222;margin:0 0 12px 0;'>" & _
        "Your request has been received and is being handled.<br>" & _
        "Your reference number is <strong>" & referenceNumber & "</strong>.</p>" & _
        "<p style='font-family:Calibri,Arial,sans-serif;font-size:11pt;line-height:1.4;color:#222;margin:0 0 12px 0;'>We will get back to you as soon as possible.</p>" & _
        "<table cellpadding='0' cellspacing='0' border='0' style='margin-top:16px;border-collapse:collapse;'>" & _
        "<tr>" & _
        logoHtml & _
        "<td style='vertical-align:top;font-family:Calibri,Arial,sans-serif;font-size:11pt;line-height:1.4;color:#222;'>" & _
        "Kind regards,<br>" & _
        HELPDESK_NAME & "<br>" & _
        "RCSi FZ LLC<br>" & _
        HELPDESK_ADDRESS & _
        "</td>" & _
        "</tr>" & _
        "</table>" & _
        "<br></div>"
End Function

Private Function HtmlEncode(ByVal value As String) As String
    Dim encoded As String

    encoded = Replace(value, "&", "&amp;")
    encoded = Replace(encoded, "<", "&lt;")
    encoded = Replace(encoded, ">", "&gt;")
    encoded = Replace(encoded, Chr$(34), "&quot;")

    HtmlEncode = encoded
End Function

Private Function BuildSmartSalutationName(ByVal rawName As String) As String
    Dim cleaned As String
    Dim normalized As String
    Dim parts() As String
    Dim partCount As Long
    Dim firstPart As String

    cleaned = Trim$(Replace(Replace(rawName, Chr$(34), ""), "'", ""))
    If Len(cleaned) = 0 Then
        BuildSmartSalutationName = ""
        Exit Function
    End If

    normalized = CollapseSpaces(cleaned)
    parts = Split(normalized, " ")
    partCount = UBound(parts) - LBound(parts) + 1
    firstPart = LCase$(parts(LBound(parts)))

    If LooksLikeGenericAlias(normalized) Then
        BuildSmartSalutationName = ""
        Exit Function
    End If

    If IsHonorific(firstPart) And partCount >= 2 Then
        BuildSmartSalutationName = ProperWord(parts(LBound(parts))) & " " & ProperWord(parts(UBound(parts)))
        Exit Function
    End If

    If partCount >= 2 Then
        BuildSmartSalutationName = ProperWord(parts(LBound(parts)))
        Exit Function
    End If

    If InStr(1, normalized, "@", vbTextCompare) > 0 Then
        BuildSmartSalutationName = ""
        Exit Function
    End If

    BuildSmartSalutationName = ProperWord(normalized)
End Function

Private Function LooksLikeGenericAlias(ByVal value As String) As Boolean
    Dim lowered As String

    lowered = LCase$(value)
    LooksLikeGenericAlias = _
        InStr(lowered, "helpdesk") > 0 Or _
        InStr(lowered, "support") > 0 Or _
        InStr(lowered, "info") > 0 Or _
        InStr(lowered, "sales") > 0 Or _
        InStr(lowered, "admin") > 0 Or _
        InStr(lowered, "accounts") > 0 Or _
        InStr(lowered, "team") > 0 Or _
        InStr(lowered, "office") > 0 Or _
        InStr(lowered, "noreply") > 0 Or _
        InStr(lowered, "no-reply") > 0
End Function

Private Function IsHonorific(ByVal value As String) As Boolean
    Dim lowered As String

    lowered = Replace(LCase$(value), ".", "")
    IsHonorific = _
        lowered = "mr" Or _
        lowered = "mrs" Or _
        lowered = "ms" Or _
        lowered = "miss" Or _
        lowered = "dr" Or _
        lowered = "prof"
End Function

Private Function ProperWord(ByVal value As String) As String
    If Len(value) = 0 Then
        ProperWord = ""
    Else
        ProperWord = UCase$(Left$(value, 1)) & LCase$(Mid$(value, 2))
    End If
End Function

Private Function CollapseSpaces(ByVal value As String) As String
    Dim result As String

    result = Trim$(value)
    Do While InStr(result, "  ") > 0
        result = Replace(result, "  ", " ")
    Loop

    CollapseSpaces = result
End Function

Option Explicit

Private Const HELPDESK_ADDRESS As String = "helpdesk@rcsi-fze.com"
Private Const HELPDESK_NAME As String = "Helpdesk"
Private Const PROCESSED_FLAG As String = "HelpdeskAutoAckSent"
Private Const LOGO_PATH As String = "C:\Users\PASCA\Dropbox\Geheugen\RCSi\rcsi_globe_logo.png"
Private Const LOGO_CID As String = "rcsihelpdesklogo"
Private Const EXCLUDED_SENDERS_FILE_PATH As String = "C:\Users\PASCA\OneDrive\Documents\Codex\scripts\email_auto_reply\excluded_senders.txt"

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

    If IsExcludedSender(mail.SenderEmailAddress) Then
        Exit Sub
    End If

    If IsNoReplyAddress(mail.SenderEmailAddress, mail.SenderName) Then
        Exit Sub
    End If
    SendAcknowledgement mail
    MarkAcknowledged mail
End Sub

Private Function GetExcludedSenderAddresses() As Variant
    Dim fileNumber As Integer
    Dim lineText As String
    Dim cleanedLine As String
    Dim addresses As Collection
    Dim result() As String
    Dim index As Long

    Set addresses = New Collection
    fileNumber = FreeFile

    Open EXCLUDED_SENDERS_FILE_PATH For Input As #fileNumber
    Do Until EOF(fileNumber)
        Line Input #fileNumber, lineText
        cleanedLine = CleanExcludedSenderLine(lineText)
        If Len(cleanedLine) > 0 Then
            addresses.Add cleanedLine
        End If
    Loop
    Close #fileNumber

    If addresses.Count = 0 Then
        GetExcludedSenderAddresses = Array("")
        Exit Function
    End If

    ReDim result(0 To addresses.Count - 1)
    For index = 1 To addresses.Count
        result(index - 1) = CStr(addresses(index))
    Next index

    GetExcludedSenderAddresses = result
End Function

Private Function IsExcludedSender(ByVal emailAddress As String) As Boolean
    Dim excludedAddresses As Variant
    Dim index As Long

    excludedAddresses = GetExcludedSenderAddresses()

    If IsEmpty(excludedAddresses) Then
        IsExcludedSender = False
        Exit Function
    End If

    For index = LBound(excludedAddresses) To UBound(excludedAddresses)
        If LCase$(Trim$(emailAddress)) = LCase$(Trim$(CStr(excludedAddresses(index)))) Then
            IsExcludedSender = True
            Exit Function
        End If
    Next index

    IsExcludedSender = False
End Function

Private Function CleanExcludedSenderLine(ByVal lineText As String) As String
    Dim commentStart As Long

    commentStart = InStr(1, lineText, "#", vbTextCompare)
    If commentStart > 0 Then
        lineText = Left$(lineText, commentStart - 1)
    End If

    CleanExcludedSenderLine = Trim$(lineText)
End Function

Private Function IsNoReplyAddress(ByVal emailAddress As String, ByVal displayName As String) As Boolean
    Dim combined As String

    combined = LCase$(emailAddress) & " " & LCase$(displayName)
    IsNoReplyAddress = _
        InStr(combined, "noreply") > 0 Or _
        InStr(combined, "no-reply") > 0 Or _
        InStr(combined, "no_reply") > 0 Or _
        InStr(combined, "donotreply") > 0 Or _
        InStr(combined, "do-not-reply") > 0 Or _
        InStr(combined, "do_not_reply") > 0 Or _
        InStr(combined, "mailer-daemon") > 0 Or _
        InStr(combined, "postmaster") > 0 Or _
        InStr(combined, "notifications@") > 0 Or _
        InStr(combined, "notification@") > 0 Or _
        InStr(combined, "automated@") > 0 Or _
        InStr(combined, "automailer@") > 0 Or _
        InStr(combined, "bounce") > 0
End Function

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


    If IsNoReplyAddress(mail.SenderEmailAddress, mail.SenderName) Then
        Exit Sub
    End If
    SendAcknowledgement mail
    MarkAcknowledged mail
End Sub

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


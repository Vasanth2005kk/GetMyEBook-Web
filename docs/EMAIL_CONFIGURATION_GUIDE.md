# Email Configuration Guide

## Problem
You're seeing this error because the email server is not configured:
```
[Errno -2] Name or service not known
```

The application is trying to use the default placeholder mail server `mail.example.org`, which doesn't exist.

## Solution

You need to configure a valid SMTP email server. Here are your options:

---

## Option 1: Gmail (Recommended for Testing)

### Using Gmail with App Password

1. **Enable 2-Factor Authentication** on your Gmail account
2. **Create an App Password**:
   - Go to https://myaccount.google.com/apppasswords
   - Select "Mail" and your device
   - Copy the generated 16-character password

3. **Configure in GetMyEBook**:
   - Navigate to: **Admin → Email Server Settings** (`/admin/mailsettings`)
   - Set the following:
     - **Email Account Type**: Standard Email Account
     - **SMTP Hostname**: `smtp.gmail.com`
     - **SMTP Port**: `587`
     - **Encryption**: STARTTLS
     - **SMTP Login**: your.email@gmail.com
     - **SMTP Password**: [paste the 16-character app password]
     - **From Email**: your.email@gmail.com
   - Click **Save and Send Test Email**

### Using Gmail OAuth (Alternative)

1. Navigate to: **Admin → Email Server Settings**
2. Select **Email Account Type**: Gmail Account
3. Click **Setup Gmail Account**
4. Follow the OAuth authorization flow

---

## Option 2: Outlook/Hotmail

1. Navigate to: **Admin → Email Server Settings**
2. Configure:
   - **SMTP Hostname**: `smtp-mail.outlook.com`
   - **SMTP Port**: `587`
   - **Encryption**: STARTTLS
   - **SMTP Login**: your.email@outlook.com
   - **SMTP Password**: your password
   - **From Email**: your.email@outlook.com

---

## Option 3: Yahoo Mail

1. **Create an App Password**:
   - Go to Yahoo Account Security
   - Generate an app password for "Mail"

2. Configure in GetMyEBook:
   - **SMTP Hostname**: `smtp.mail.yahoo.com`
   - **SMTP Port**: `587`
   - **Encryption**: STARTTLS
   - **SMTP Login**: your.email@yahoo.com
   - **SMTP Password**: [app password]
   - **From Email**: your.email@yahoo.com

---

## Option 4: Custom SMTP Server

If you have your own email server or use a business email:

1. Contact your email provider for SMTP settings
2. Common settings:
   - **SMTP Port**: Usually `587` (STARTTLS) or `465` (SSL/TLS)
   - **Encryption**: STARTTLS or SSL/TLS
   - **Authentication**: Usually required

---

## Option 5: Disable Email (Temporary)

If you don't need email functionality right now:

1. Simply don't configure the email server
2. The application will work fine, but email-related features will be disabled
3. Users won't be able to:
   - Send books to Kindle
   - Receive password reset emails
   - Get registration emails

---

## Testing Your Configuration

After configuring the email server:

1. Go to **Admin → Email Server Settings**
2. Click **Save and Send Test Email**
3. Check your email inbox for the test message
4. If you receive it, configuration is successful!

---

## Common Issues

### "Authentication failed"
- Double-check your username and password
- For Gmail/Yahoo, make sure you're using an App Password, not your regular password
- Verify 2FA is enabled if required

### "Connection timeout"
- Check if your firewall is blocking SMTP ports (587, 465, 25)
- Verify the SMTP hostname is correct
- Try a different port (587 vs 465)

### "SSL/TLS error"
- Make sure you've selected the correct encryption method
- Port 587 usually uses STARTTLS
- Port 465 usually uses SSL/TLS

---

## What Changed

I've improved the error handling in the application to provide clearer error messages when the email server is not configured. Instead of the cryptic DNS error, you'll now see:

```
Email server is not configured properly. 
Please configure a valid SMTP server in Admin → Email Server Settings.
```

This makes it easier to diagnose and fix email configuration issues.

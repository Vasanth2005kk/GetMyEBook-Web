# Testing Guide for Admin Configuration Fixes

## Prerequisites
- Application should be running on http://localhost:8083
- You should be logged in as an admin user

## Test 1: Checkbox Persistence in `/admin/config`

### Steps:
1. Navigate to http://localhost:8083/admin/config
2. Scroll through the configuration page and note the current state of various checkboxes
3. **Test Checking Boxes:**
   - Find an unchecked checkbox (e.g., "Enable Uploading", "Enable Public Registration", etc.)
   - Check the checkbox
   - Scroll to the bottom and click "Save"
   - Wait for the success message
   - Refresh the page (F5 or Ctrl+R)
   - **Expected Result:** The checkbox should remain checked ✓

4. **Test Unchecking Boxes:**
   - Find a checked checkbox
   - Uncheck it
   - Click "Save"
   - Wait for the success message
   - Refresh the page
   - **Expected Result:** The checkbox should remain unchecked ✓

5. **Test Multiple Checkboxes:**
   - Check 2-3 checkboxes and uncheck 2-3 other checkboxes
   - Click "Save"
   - Refresh the page
   - **Expected Result:** All changes should be persisted correctly ✓

### Checkboxes to Test:
- Access Logs
- Unicode Filename
- Embed Metadata
- Enable Uploading
- Enable Anonymous Browsing
- Enable Public Registration
- Enable Registration Email
- Enable Remote Login
- Enable Kobo Sync
- Use Goodreads
- Enable Reverse Proxy Login
- Rate Limiter
- Check File Extensions
- Password Policy (and sub-options)

## Test 2: Email Settings Data Persistence in `/admin/mailsettings`

### Steps:
1. Navigate to http://localhost:8083/admin/mailsettings

2. **Test Initial Save:**
   - Fill in the following fields:
     - SMTP Hostname: `smtp.gmail.com`
     - SMTP Port: `587`
     - Encryption: Select "STARTTLS"
     - SMTP Login: `your-email@gmail.com`
     - SMTP Password: `your-app-password` (this will be blank after save for security)
     - From Email: `noreply@example.com`
     - Attachment Size Limit: `25` MB
   - Click "Save"
   - Wait for success message: "Email Server Settings updated"
   - **Expected Result:** Success message appears ✓

3. **Test Data Persistence After Refresh:**
   - Refresh the page (F5 or Ctrl+R)
   - **Expected Results:**
     - SMTP Hostname should show: `smtp.gmail.com` ✓
     - SMTP Port should show: `587` ✓
     - Encryption should show: "STARTTLS" selected ✓
     - SMTP Login should show: `your-email@gmail.com` ✓
     - SMTP Password should be EMPTY (for security) ✓
     - From Email should show: `noreply@example.com` ✓
     - Attachment Size Limit should show: `25` ✓

4. **Test Updating Existing Settings:**
   - Change SMTP Port to: `465`
   - Change Encryption to: "SSL/TLS"
   - Change Attachment Size Limit to: `10`
   - Click "Save"
   - Refresh the page
   - **Expected Results:**
     - SMTP Port should show: `465` ✓
     - Encryption should show: "SSL/TLS" selected ✓
     - Attachment Size Limit should show: `10` ✓
     - All other fields should retain their previous values ✓

5. **Test Clearing Fields:**
   - Clear the SMTP Login field (leave it empty)
   - Click "Save"
   - Refresh the page
   - **Expected Result:** SMTP Login should be empty ✓

## Test 3: Browser Console Check

### Steps:
1. Open browser developer tools (F12)
2. Go to the Console tab
3. Navigate to `/admin/config` or `/admin/mailsettings`
4. Make changes and save
5. **Expected Result:** No JavaScript errors should appear in the console ✓

## Test 4: Database Verification (Optional)

If you want to verify that data is actually being saved to the database:

### For PostgreSQL:
```bash
psql -U vasanth -d getmyebook_app -c "SELECT mail_server, mail_port, mail_use_ssl, mail_login, mail_from FROM settings;"
```

### Expected Output:
Should show the values you entered in the email settings form.

## Test 5: Log File Verification

### Steps:
1. Check the application logs for confirmation messages
2. Look for entries like:
   - `"Mail settings saved successfully"`
   - `"Configuration saved successfully"`
3. Ensure there are no error messages related to saving configuration

## Common Issues to Watch For

### ❌ Issues that should NOT occur anymore:
1. Checkboxes reverting to checked state after being unchecked
2. Form fields losing their values after save and refresh
3. Database errors when saving configuration
4. Silent failures (no error message but data not saved)

### ✓ Expected Behavior:
1. All checkbox states persist correctly
2. All form field values (except passwords) persist after save and refresh
3. Success messages appear after saving
4. No errors in browser console or application logs

## Troubleshooting

If you encounter issues:

1. **Check Application Logs:**
   ```bash
   tail -f /home/vasanth/Desktop/GetMyEBook-Web/calibre-web.log
   ```

2. **Check Database Connection:**
   - Ensure PostgreSQL is running
   - Verify connection settings in `.env` file

3. **Clear Browser Cache:**
   - Sometimes old JavaScript/CSS can cause issues
   - Try hard refresh: Ctrl+Shift+R

4. **Restart Application:**
   ```bash
   # Stop the application
   pkill -f "python.*cps.py"
   
   # Start it again
   cd /home/vasanth/Desktop/GetMyEBook-Web
   source .venv/bin/activate
   python3 cps.py
   ```

## Success Criteria

All tests pass if:
- ✓ Checkbox states persist correctly after save and refresh
- ✓ Email settings (except password) persist after save and refresh
- ✓ Success messages appear after saving
- ✓ No errors in browser console
- ✓ No errors in application logs
- ✓ Database contains the correct values

## Notes

- The password field in email settings is intentionally cleared after save for security reasons
- Some settings may require an application restart to take effect (the system will notify you)
- Changes to certain settings (like port numbers) may trigger an automatic restart

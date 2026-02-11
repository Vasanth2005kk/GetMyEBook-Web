# Admin Configuration Fixes

## Issues Fixed

### 1. `/admin/config` - Checkbox State Not Persisting

**Problem:**
When unchecking checkboxes in the admin configuration page and saving, the checkboxes would appear checked again after refreshing the page. The unchecked state was not being saved to the database.

**Root Cause:**
HTML forms only send data for checked checkboxes. When a checkbox is unchecked, it doesn't appear in the form submission data at all. The helper functions `_config_checkbox()` and `_config_checkbox_int()` were relying on `set_from_dictionary()` which would return `False` when a key wasn't present in the dictionary, without actually updating the field value.

**Solution:**
Modified both `_config_checkbox()` and `_config_checkbox_int()` functions in `/cps/admin.py` to explicitly check if the checkbox field is present in the form data:
- If the field is NOT present (checkbox unchecked), explicitly set the value to `False` or `0`
- If the field IS present (checkbox checked), process it normally

This ensures that unchecking a checkbox actually saves the unchecked state to the database.

### 2. `/admin/mailsettings` - Form Data Not Persisting After Save

**Problem:**
After saving email server settings and refreshing the page, all the input field values would disappear, requiring the user to re-enter all the information.

**Root Cause:**
After calling `config.save()`, the configuration object was not being reloaded from the database. This meant that the template was rendering with stale data or the data wasn't being properly committed to the database.

**Solution:**
1. Added explicit `config.load()` call after `config.save()` in the `update_mailsettings()` function
2. Improved error handling to properly display error messages (fixed the `e.orig` attribute access which might not exist)
3. Added better logging to track when settings are saved successfully

The same fix was also applied to the main `_configuration_update_helper()` function for consistency.

## Files Modified

1. `/home/vasanth/Desktop/GetMyEBook-Web/cps/admin.py`
   - Modified `_config_checkbox()` function (lines ~1033-1041)
   - Modified `_config_checkbox_int()` function (lines ~1043-1051)
   - Enhanced `update_mailsettings()` function (lines ~1235-1296)
   - Enhanced `_configuration_update_helper()` function (lines ~2070-2084)

## Testing Recommendations

1. **Test `/admin/config` checkbox persistence:**
   - Navigate to `/admin/config`
   - Check several checkboxes and save
   - Refresh the page - checkboxes should remain checked
   - Uncheck the same checkboxes and save
   - Refresh the page - checkboxes should remain unchecked

2. **Test `/admin/mailsettings` data persistence:**
   - Navigate to `/admin/mailsettings`
   - Fill in all email server settings (SMTP server, port, login, from email, etc.)
   - Click "Save"
   - Refresh the page - all fields (except password for security) should retain their values
   - Modify some fields and save again
   - Refresh - modified values should be displayed

## Technical Details

### Checkbox Handling Logic

```python
def _config_checkbox_int(to_save, x):
    # Explicitly handle unchecked checkboxes (not present in form data)
    if x not in to_save:
        # Checkbox is unchecked, set to 0
        if hasattr(config, x):
            setattr(config, x, 0)
            return True
        return False
    return config.set_from_dictionary(to_save, x, lambda y: 1 if (y == "on") else 0, 0)
```

### Configuration Reload Pattern

```python
try:
    config.save()
    # Explicitly reload config to ensure we have the latest data
    config.load()
    log.info("Settings saved successfully")
except Exception as e:
    # Handle errors...
```

This pattern ensures that:
1. Changes are committed to the database
2. The configuration object is refreshed with the latest database values
3. The UI displays the correct, persisted values

## Notes

- The password field in email settings intentionally remains empty after save for security reasons (line 52 in `email_edit.html` has `value=""`)
- All other fields should persist their values correctly after these fixes
- The fixes maintain backward compatibility with existing functionality

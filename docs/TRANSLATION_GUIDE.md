# How to Implement and Modify Translations

This guide explains how to add new translations or fix existing ones in the **GetMyEBook-Web** project using `Babel` (gettext).

## 1. Mark Text for Translation

Before text can be translated, it must be "marked" in the code so the system detects it.

### In HTML Templates (`.html`)
Use the `{{_('...')}}` syntax.
```html
<!-- Example in login.html -->
<h1>{{_('Sign In')}}</h1>
<p>{{_('Welcome back, user!')}}</p>
```

### In Python Code (`.py`)
Import `gettext` as `_` (usually done for you) and wrap strings in `_()`.
```python
flash(_("Login successful"))
return _("Page not found")
```

## 2. Update the Translation File
Open the specific language file you want to edit.
*   **Tamil File**: `cps/translations/ta/LC_MESSAGES/messages.po`

Find the `msgid` corresponding to the English text and add/edit the `msgstr`.

**Format:**
```po
msgid "Sign In"
msgstr "உள்நுழையவும்"

msgid "Username"
msgstr "பயனர் பெயர்"
```

### Important Rules
1.  **Exact Match**: The `msgid` must match the English text in the code **exactly** (case-sensitive).
2.  **Placeholders**: If the text has placeholders like `%(name)s`, you **must** include them exactly as they are in the translation.
    *   *Correct*: `msgstr "வணக்கம், %(name)s"`
    *   *Incorrect*: `msgstr "வணக்கம், %(user)s"` (This will cause compile errors)

## 3. Compile the Translations
The application does not read the `.po` text files directly. It reads compiled `.mo` binary files. You must run this command after **every** change to a `.po` file.

```bash
pybabel compile -d cps/translations
```

If successful, you will see output like:
> compiling catalog cps/translations/ta/LC_MESSAGES/messages.po to .../messages.mo

If there are errors (like typos in placeholders), it will tell you the line number. You must fix them before it will work.

## 4. Restart the Server
The application loads translations into memory only once when it starts.

1.  **Stop** the server (Ctrl+C).
2.  **Start** the server again.
    ```bash
    python3 cps.py
    ```

## Summary Checklist
- [ ] Wrapped text in `_('...')` in code.
- [ ] Added/Updated `msgstr` in `messages.po`.
- [ ] Checked for placeholder typos (e.g., `%(oauth)s`).
- [ ] Ran `pybabel compile -d cps/translations`.
- [ ] Restarted the server.

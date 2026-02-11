# GDrive Setup Guide

## 1. Upload Books

Upload the books to your Google Drive.

---

## 2. Install & Configure Rclone

### Install rclone

```bash
sudo apt install rclone
```

### Start rclone config

```bash
rclone config
```

### Steps

* Choose **n** for new remote
* Name it something like **gdrive**
* Select **drive** as the storage type (18)
* For Client ID → go to Google Cloud Console:
  [https://console.developers.google.com/](https://console.developers.google.com/)

---

## 3. Create Google Drive Client ID (For Rclone)

1. Log into Google API Console (any Google account is fine).
2. Select an existing project or create a new project.
3. Go to **ENABLE APIS AND SERVICES** → search “Drive” → enable **Google Drive API**.
4. In the left panel click **Credentials**.
5. If OAuth consent is not configured → click **CONFIGURE CONSENT SCREEN**:

   * Application name → `rclone`
   * User support email → your email
   * Audience → **External**
   * Add contact info
   * Save

### Add API Scopes

Add the following scopes:

```
https://www.googleapis.com/auth/docs
https://www.googleapis.com/auth/drive
https://www.googleapis.com/auth/drive.metadata.readonly
```

Steps:

* Click **Data Access**
* Select scopes OR enter manually
* Save changes

### Add Test Users

Go to **Audience** → click **+ Add users** → add your email → Save.

### Create OAuth Client ID

1. Go to **Overview**
2. Click **Create OAuth Client**
3. Choose **Desktop App**
4. Copy your **Client ID** and **Client Secret**

### Publish App (for External users)

* Go to **Audience**
* Click **PUBLISH APP**
* Confirm

### Provide ID to rclone

Enter Client ID & Secret in rclone config.

---

## 4. Create GDrive Folder

```bash
mkdir gdrive
```

---

## 5. Edit fuse.conf

```bash
sudo nano /etc/fuse.conf
```

Remove `#` from:

```
user_allow_other
```

---

## 6. Mount the GDrive

Run mount command:

```bash
rclone mount ebooks: /home/anonymous/vglug/GetMyEBook-Web/gdrive \
    --allow-other \
    --vfs-cache-mode full &
```

---

## 7. Sync Complete 

Your synced Google Drive folder will appear at:

```
/home/anonymous/vglug/GetMyEBook-Web/gdrive/books_ebooks
```

---

If you want this exported to **Markdown file (.md)** again with improved styling, I can regenerate and give you a downloadable file.

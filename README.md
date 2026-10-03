# Browser Task Automation

Local desktop app for repeating a browser task you have already done yourself. Each Chrome profile keeps its own cookies and sessions. Nothing is uploaded.

The control panel is Dashboard, Profiles, Workflows, Learn Mode, Runs, Logs, and Settings.

## Requirements

- Windows
- Python 3.12 or newer
- Google Chrome installed on this PC
- The Python packages in `requirements.txt`

The app drives your installed Chrome. It does not download a Playwright browser, and it does not change Chrome's automation flags.

## Install

From this folder:

```powershell
python -m pip install -r requirements.txt
```

## Run

```powershell
python run.py
```

Run that command from this folder (`browser_task_automation`). The window title is **Browser Task Automation**.

## Add a Chrome profile

1. Open **Profiles** and choose **Add**.
2. Set the Chrome executable. The dialog starts at the usual `chrome.exe` location.
3. Set the Chrome user data folder. The usual path is `%LOCALAPPDATA%\Google\Chrome\User Data`.
4. Choose the profile directory, such as `Default` or `Profile 1`. The list is read from Chrome's local profile cache.
5. Save. The profile is stored in the app database only. Chrome user data is not copied or deleted.

**Test** opens that profile with automation, loads a blank page, and closes it. **Launch** opens a normal Chrome window for you and does not lock the profile. **Variables** stores values such as `PASSWORD` encrypted on disk. Secret values are not shown again; leave the field blank to keep the saved secret.

Deleting a profile removes the app record. It does not delete the Chrome user data folder.

## Learn Mode

1. Close every Chrome window that is using that profile. Chrome allows one process per user data folder.
2. Open **Learn Mode**, name the workflow, and pick an enabled profile.
3. Choose **Enter Learn Mode**. A visible Chrome window opens.
4. Do the task once: open the page, click, type, and move between pages.
5. Choose **End Learn Mode**.
6. Review the steps. You can edit, reorder, delete, or add a step.
7. Choose **Save Workflow**.

Saving does not start a run. Passwords, seed phrases, private keys, API keys, tokens, and PIN fields are recorded as placeholders such as `{{PASSWORD}}`. The typed secret is not stored in the workflow. Before a run, add the real value under **Profiles → Variables**.

A local practice page is included at `tests/demo_site/index.html`. It has a connect button, a note field, a password field, and a hidden verification panel. The app does not solve that panel.

## Run a workflow

1. Open **Workflows**, select a workflow, and choose **Run**.
2. Pick one or more enabled profiles. Assignment on its own does not start anything.
3. Leave **Dry run** unchecked to click and type. A dry run opens the page and finds elements, and it does not click, type, or submit.
4. **Health check** looks at Chrome, the profile path, the database, the lock, disk space, and the workflow. Failures block the run. Warnings ask you to continue.
5. Choose **Run**. The run is queued. Watch it on **Runs**.

Each run is one of: `QUEUED`, `RUNNING`, `PAUSED`, `COMPLETED`, `FAILED`, `MANUAL_ACTION_REQUIRED`, `STOPPED`.

**Runs** can pause, resume, stop, and focus the browser. If a human check or a missing `{{VARIABLE}}` appears, the run becomes `MANUAL_ACTION_REQUIRED`. Finish the check in the open browser, or add the variable, then press **Resume**. The app does not complete the check for you.

A desktop notification is shown only for `FAILED` and `MANUAL_ACTION_REQUIRED`.

**Logs** lists activity on this PC. **Export CSV** writes a file you choose. **Settings** sets the concurrent browser limit (default 3), step timeout, retry count, retry delay, and minimum free disk.

## Data on this PC

| Item | Location |
| --- | --- |
| Database | `data/app.db` |
| Application log | `data/logs/app.log` |
| Manual-action screenshots | `data/screenshots/` |
| Workflow JSON copies | `data/workflows/` |
| Encryption key for profile variables | `data/.secret_key` |

Set `BTA_DATA_DIR` to store that folder somewhere else. Logs and activity text are redacted before they are written. Do not put secrets in workflow names or notes.

## Troubleshooting

- **Profile currently in use.** Close Chrome for that user data folder, including windows you opened yourself, then try again. A paused run still holds the profile.
- **Health check warns about SingletonLock or a missing profile folder.** Another Chrome process may still have the folder open, or the profile directory name does not match a folder inside User Data. The warning does not delete anything.
- **Chrome executable not found.** Set the real `chrome.exe` path on the profile.
- **A step cannot find the button or field.** Edit the step and prefer the accessible name, label, or a stable id. Coordinates are only a last resort.
- **The run asks for a variable.** Add it on the profile, then resume. The workflow keeps `{{NAME}}`, not the secret.
- **The app was closed while a run was active.** The next start marks that run `FAILED` and says the browser session is gone. Queued runs stay queued. Your Chrome profile folder is not deleted.
- **Tests.** From this folder, run `python -m pytest`.

## Safety limits

This app automates a task you demonstrate on profiles you already use.

It does not:

- solve or bypass CAPTCHA, anti-bot, or other human checks
- spoof or randomize a browser fingerprint
- rotate proxies or hide that Chrome is automated
- create accounts or work around a site's automation rules

If a human check is on the page, the run pauses until you finish it and press Resume.

# TwisterX Auto Roller v1.3.2: Beginner Tutorial

This guide walks you through installing, setting up and using **TwisterX Auto Roller**. Labels in **bold** are the exact text you will see in the app.

---

> **Built-in tour:** the first time you open the app, a guided tour highlights each feature and explains it page by page. Use **Next / Back** or the arrow keys, and **Skip tour** to close it. It only shows once. Replay it any time with **Settings → Replay tutorial**.

## 1. What it is

TwisterX Auto Roller is a Windows helper app. It can:

1. Join your Roblox **private server** from its share link.
2. Wait for the game to load, then click the in-game **spawn/menu** button and the **Forecast** button for you.
3. Take a screenshot and read the weather panel with **Tesseract OCR**. It reads Risk, Temperature, Dew point, PWAT, SRH, CAPE, Lapse Rates, Humidity, Storm Motion and Day.
4. Check the values against your **Requirements**, and against your **Record hunt** rows.
5. Send a **Discord webhook** message with a screenshot when something matches.
6. Rejoin and **reroll** automatically until it finds what you want.

### Quick start (for the impatient)

1. **Easiest:** double-click **`TwisterX Auto Roller.exe`**. Nothing to install: Python, every package and Tesseract OCR are inside it.
2. **Or run the script:** double-click **`Start TwisterX Auto Roller.bat`**. The first time, it installs whatever is missing (Python, the packages, Tesseract), then opens the app. After that it just opens.
3. The guided tour starts on first launch and shows you every step below.
4. On **Run**, paste your private server link into **Server link**, then click **Save**. Paste your Discord webhook into **Webhook**, then click **Save** and **Test**.
5. Join the game once by hand. On **Calibration**, click **Set** for **Forecast (2nd)** (and **Spawn / menu (1st)** if your game needs it). Then set the **OCR text panel** corners and the **Thermos screenshot** corners.
6. Open the forecast panel in game. Click **Preview region** and **Test OCR now** until the values read correctly.
7. On **Requirements**, turn on the rows you care about. Click **Save requirements**.
8. Back on **Run**, click **▶ Join now** (one try) or **⟳ Start auto** (keep going). Press **Esc** or **■ Stop** to stop.

---

## 2. Installing

There are two ways to run the app. Pick one.

### 2.1 The EXE (recommended, nothing to install)

1. Copy **`TwisterX Auto Roller.exe`** into any folder you like, for example a folder on your Desktop.
2. Double-click it.

That's all. The EXE contains Python, every package and Tesseract OCR. It works on a PC that has none of them.

- The first start takes a few seconds while it unpacks itself.
- Windows SmartScreen may say **"Windows protected your PC"** unless the EXE is code-signed. Click **More info → Run anyway** (see *Antivirus warnings and code signing* below).
- `config.json` and `data.txt` are created **next to the EXE**, so keep it in a folder you can write to (not `C:\Program Files`).

### 2.2 The script, with `Start TwisterX Auto Roller.bat`

Double-click **`Start TwisterX Auto Roller.bat`** (keep it in the same folder as `TwisterX_Auto_Roller.py`). It checks for and installs, only when missing:

| What | How it's installed |
|---|---|
| Python 3.12 | `winget`, just for your user account |
| Python packages: customtkinter, pyautogui, pillow, pytesseract, mss, requests, pystray | `pip` |
| Tesseract OCR | `winget` (UB Mannheim build). Windows may ask for permission. |

Then it opens the app with no console window. Later runs skip straight to opening the app.

If `winget` isn't available (very old Windows 10), the launcher opens the download page instead. Install Python with **Add python.exe to PATH** ticked, then double-click the launcher again.

### 2.3 Double-clicking `TwisterX_Auto_Roller.py` directly

This also works once Python is installed and `.py` files open with Python. The script hides its own console window. If a package is missing, it shows a pop-up with the exact `pip install` command instead of flashing a console and closing. If double-clicking the `.py` does nothing, Windows has no program set for `.py` files: use `Start TwisterX Auto Roller.bat` instead.

### 2.4 Where the app looks for Tesseract

In this order: the copy bundled inside the EXE (or a `tesseract` folder next to the script), then `tesseract` on PATH, then `C:\Program Files\Tesseract-OCR`, `C:\Program Files (x86)\Tesseract-OCR` and `%LOCALAPPDATA%\Programs\Tesseract-OCR`. If none is found, the log shows a red `Tesseract not found!` line on startup.

> The app creates or updates `config.json` next to the script or EXE **every time it starts**.

---

## 3. Server link and Discord webhook

### 3.1 Get your private server link

1. In Roblox, open the game page, go to **Servers**, then your private server, and choose **Copy Link** (share link).
2. Either link style works:
   - `https://www.roblox.com/games/<placeId>/...?privateServerLinkCode=<code>`
   - `https://www.roblox.com/share?code=<code>&type=Server`
3. On the **Run** page, paste it into **Server link** and click **Save**.

If the link is wrong, a **Bad link** box tells you why:
- `Not a roblox.com link.`
- `Path must be /games/<id>/...`
- `Missing privateServerLinkCode in URL.`
- `Share link is missing its code.` / `That share link isn't a private server link.`

The app turns the link into `roblox://placeId=...&linkCode=...` and opens it, which starts Roblox.

### 3.2 Make a Discord webhook

1. In Discord, open **Server Settings → Integrations → Webhooks**.
2. Click **New Webhook**, choose the channel, then click **Copy Webhook URL**.
3. In the app, paste it into **Webhook**. The text is hidden with dots until you click into the box.
4. Click **Save**. If the URL does not start with `https://discord.com/api/webhooks/` (or similar), the app asks whether you want to save it anyway.
5. Click **Test**. The app sends a "Test message" embed. The log shows `Webhook test sent.` or `Webhook test failed: ...`.

> **Test** uses whatever is in the box right now, even if you have not saved it. Remember to click **Save** too.

> **Role ping:** to have messages ping a Discord role, open **Settings → Discord**, paste the role's ID into **Role ID** and turn on **Ping role** (see section 8). In Discord, enable Developer Mode, then right-click the role → **Copy Role ID**.

---

## 4. Calibration

Do this once, with Roblox open in the window size you will use from now on. If you move or resize Roblox later, you need to calibrate again.

### 4.1 How "Set" works

When you click any **Set** button:
1. The app window minimizes.
2. A dark see-through overlay covers the screen and tells you which point to pick.
3. **Left-click** the exact spot. Press **Esc** or **right-click** to cancel.
4. The coordinates appear next to the button, for example `(1260, 125)`, and are saved right away.

### 4.2 Click positions

In the **Click positions** card:

1. **Spawn / menu (1st)**: click **Set**, then click the in-game spawn/play/menu button. This is optional. If it is not set, the app skips it ("If spawn isn't set, only Forecast is clicked.").
2. **Forecast (2nd)**: click **Set**, then click the in-game Forecast button. If you never set this, the app guesses a position scaled from (1260, 125) on a 2560×1440 screen and warns you in the log. Set it properly.
3. **Test** clicks that position for real, using the real mouse. Use it only with Roblox open.

### 4.3 OCR text panel region

This is the box with the text values (Risk, CAPE and so on).

1. Open the Forecast panel in game.
2. In the **OCR text panel** card, click **Set** next to **Top-left**, then click the top-left corner of the text.
3. Click **Set** next to **Bottom-right**, then click the bottom-right corner.
4. Click **Preview region**. You see the area **as Tesseract sees it**: black and white, and twice as large. Press **Esc** to close the preview.

Keep the box tight around the lines `Label: value`. The reader only understands lines like `CAPE: 2500`. A colon or semicolon must follow the label.

### 4.4 Thermos screenshot region

This is the picture that is attached to the **Requirements passed** webhook.

1. In the **Thermos screenshot** card, set **Top-left** and **Bottom-right** the same way.
2. Click **Preview region** to check it. This preview is in normal colour.

If this region is not set, the pass webhook is still sent, just without an image. Record hits always attach the **full screen**.

### 4.5 Tuning the OCR image

The **OCR image** card has two sliders:
- **Threshold**: 0–255, default **165**.
- **Contrast**: 0.5–6.0, default **2.2**.

How the image is processed: it is made greyscale, auto-contrasted, contrast is boosted, colours are **inverted**, then each pixel turns black or white based on the threshold.

1. Move a slider.
2. Click **Preview region** on the OCR panel again, or **Test OCR now**. Both use the current slider values and save them automatically.
3. Repeat until the preview shows crisp black text on a white background.

**Test OCR now** (also called **Read OCR now** on the Run page) reads the screen once and shows the values in **Last scan**. It does not click anything.

A test read never sends Discord webhooks, even if the values pass or hit a record. Only real runs do.

### 4.6 Click timing

In the **Click timing** card (type a value, then click **Save**):

| Field | Default | What it does |
|---|---|---|
| **Settle after focus** | 120 ms | Wait after bringing Roblox to the front |
| **Pause before click** | 50 ms | Wait after moving the mouse, before clicking |
| **Max attempts** | 3 | Retries if a click throws an error |

**Mouse position (3s)** counts down 3 seconds, then logs where your mouse is. This helps you read coordinates.

If Roblox ignores clicks, raise **Settle after focus** (for example to 300) and **Pause before click** (for example to 150).

### 4.7 Troubleshooting OCR

| Symptom | Fix |
|---|---|
| Log says `No values read` and `raw: (empty)` | The region is wrong, or the panel was not open. Check with **Preview region**. |
| Preview is all black | Lower **Threshold**, then **Save**. |
| Preview is all white or the text is too thin | Raise **Threshold** or **Contrast**, then **Save**. |
| Garbled raw text such as `CAPF 25O0` | Make the region tighter, try other threshold values, and make the Roblox window bigger. |
| Some fields show `—` | That line was not read as `Label: value`. Widen the region so it covers the whole line. |
| `Region is too small — recalibrate it.` | The two corners are almost the same point. Set them again. |
| `Panel region not set (Calibration tab).` | You have not set both corners yet. |

Risk is cleaned up automatically. For example, `SLOT` becomes `SLGT`, `MARG` becomes `MRGL` and `ENHANCED` becomes `ENH`.

---

## 5. Requirements

On the **Requirements** page:

- **Check requirements** switch: this saves immediately. When it is off, nothing is sent for requirements and no popup appears. (Record hunt still works.)
- Each row has **On**, **Field**, **Op** (`>=` or `<=`), **Value** and **Solo**.
- Click **Save requirements** to save. **Revert** reloads the last saved values.

### Normal vs Solo

- **Normal rows** (Solo unticked): **all** of them must pass.
- **Solo rows** (Solo ticked): **any one** passing is enough on its own.
- The result passes if any Solo row passes **or** all normal rows pass.
- If no row is turned on, the result **never** passes.
- If a value cannot be read, that row fails.

### Worked examples

1. **CAPE ≥ 3000 and SRH ≥ 250** (both normal). CAPE 3500 with SRH 200 → **fail**. CAPE 3500 with SRH 300 → **pass**.
2. **Risk ≥ ENH** (Solo) plus **CAPE ≥ 4000** (normal). Risk MDT with CAPE 1000 → **pass** (the Solo row passes). Risk SLGT with CAPE 4500 → **pass** (all normal rows pass). Risk SLGT with CAPE 2000 → **fail**.
3. **Temperature <= 70** checks for 70 or lower. The app takes the first number in the text, so `68°F` counts as 68.

### Risk levels (lowest to highest)

`NONE` → `TSTM` → `MRGL` → `SLGT` → `ENH` → `MDT` → `HIGH`

So **Risk >= SLGT** passes for SLGT, ENH, MDT and HIGH.

All rows are off by default. Risk defaults to `>= SLGT` and number rows default to `>= 0`.

---

## 6. Record hunt

The **Records** page is for values you are trying to beat. A hit sends a gold Discord embed with a **full-screen screenshot**, titled `Record hit: <names>`. A hit **never stops the loop**.

1. Click **+ Add record**.
2. Fill in **On**, **Name**, **Field**, **Op** and **Value**. Click **✕** to remove a row.
3. Click **Save records**. Risk records must use one of `NONE, TSTM, MRGL, SLGT, ENH, MDT, HIGH`. Number records need a number.

Examples:

| Name | Field | Op | Value | Hits when |
|---|---|---|---|---|
| Huge CAPE | CAPE | >= | 6000 | CAPE is 6000 or more |
| Crazy SRH | SRH | >= | 600 | SRH is 600 or more |
| Freezing | Temperature | <= | 30 | Temperature is 30 or lower |
| High risk | Risk | >= | HIGH | Risk is HIGH |

Records are checked on every scan, even when **Check requirements** is off. The **Record hits** counter goes up by 1 per scan that has a hit.

Tip from the app: turn **Popup on pass** off when record hunting, so the loop never stops on its own.

---

## 7. Running

### 7.1 Controls on the Run page

- **Load wait** (default **25** s, minimum 0): how long to wait after launching Roblox.
- **Interval** (default **2** s, minimum 2): the pause before each reroll / next run.
- **▶ Join now** (or press **Enter** while not typing in a box): one run.
- **⟳ Start auto**: keep rejoining.
- **■ Stop** (or **Esc** when you're not typing in a box): stops everything.
- **Read OCR now**: a test read with no join, no clicks and no webhooks.
- Switches:
  - **Click in-game buttons** (default on): clicks Spawn and Forecast.
  - **Auto-reroll on fail** (default off): rejoins when requirements fail.
  - **Popup on pass** (default on): shows the pass popup.

### 7.2 What one run does

1. `Launching Roblox…` opens the roblox:// link.
2. Waits **Load wait** seconds.
3. If **Click in-game buttons** is on: clicks Spawn and waits 5 s (skipped if Spawn isn't set), clicks Forecast, then waits 3 s.
4. Reads the OCR panel, checks your requirements and records, writes to `data.txt`, and sends webhooks.
5. Then:
   - **Pass**, with the popup on: the app waits for your choice in the popup.
   - **Pass**, with the popup off: the run ends. In auto mode, the next join comes after **Interval**.
   - **Fail**: if **Auto-reroll on fail** is on, or auto mode is running, it rerolls after **Interval** seconds.
   - **OCR error**: same rule as a fail. If neither auto mode nor auto-reroll is on, it just stops.

### 7.3 Auto mode

**⟳ Start auto** waits **Interval** seconds, then joins. The sidebar badge shows `Auto: next in Ns`, `Auto: joining…` or `Auto: running…`. Every reroll and every next run waits **Interval** seconds.

### 7.4 The pass popup

The **Requirements met** window lists the values and has two buttons:
- **Continue rerolling**: rejoins after **Interval** seconds.
- **Stop here** (also **Enter**, **Esc** or closing the window): stops everything.

### 7.5 Stopping

- **■ Stop**, **Esc**, or **Stop loop** in the tray menu. These cancel waits, pending rerolls and auto mode, and interrupt a click sequence between steps. An OCR read that has already started finishes, but its result is ignored.
- **Failsafe:** push your mouse into any screen corner. The app checks for this during every wait and click, and stops.

### 7.6 Log and stats

- The tiles at the top show **Scans**, **Passes**, **Record hits** and **Uptime** for this session.
- **Last scan** shows a badge (**✔ PASSED**, **✘ Not passed** or **Requirements off**) and each value.
- **Log** is colour coded: green = good, yellow = warning, red = error, grey = details. Fail reasons appear as `- CAPE: 2100 >= 3000 — no match`.
- The log buttons are **Open folder**, **config.json**, **data.txt** and **Clear**.

---

## 8. Settings

Everything is saved to `config.json` under `"settings"`.

| Setting | Default | Notes |
|---|---|---|
| **Mode** | Dark | Dark / Light / System. Applies immediately. |
| **Accent colour** | blue | blue / green / dark-blue. **Applies after restart.** |
| **UI scaling** | 100% | 80–150%. Applied when you release the slider. |
| **Close button** | Minimize to tray | Or **Quit**. Without pystray, closing minimizes to the taskbar instead. |
| **Always on top** | off | Keeps the window above Roblox. |
| **Desktop notifications** | on | Tray balloon on pass. Needs pystray. |
| **Sound on pass** | on | Beep when requirements pass. |
| **Ping role** | off | Mentions your role in webhook messages. Needs a **Role ID**. |
| **Role ID** | *(empty)* | Your Discord role's ID (digits only). Press Enter or click away to save. |
| **History limit** | 1000 | Scans kept in data.txt (minimum 10). |
| **Log lines** | 1500 | Lines kept in the log panel (minimum 100). |

- **Open data folder** opens the app folder.
- **Reset settings to defaults** resets only this page. Links, regions, requirements and records are kept.

The tray menu (with pystray) has **Show window**, **Stop loop** and **Quit**.

---

## 9. Files and building the EXE

### Where files live

Files are stored next to the `.py` file, or next to the `.exe`, no matter where you start it from:
- `config.json`: all settings, regions, links, requirements and records. If it gets corrupted, it is copied to `config.json.bad` and defaults are used.
- `data.txt`: scan history in JSON format (last values, what changed, pass/fail, reasons). If it gets corrupted, it is renamed to `data.txt.bak`.

### Building the EXE

1. Double-click `build.bat`. It:
   1. checks Python,
   2. runs `pip install --upgrade pyinstaller pyautogui pillow pytesseract mss requests customtkinter pystray`,
   3. installs Tesseract with `winget` if it's missing (it's needed to bundle it),
   4. runs `python -m PyInstaller build.spec --clean --noconfirm`.
2. The result is `dist\TwisterX Auto Roller.exe`: a single standalone file with no console window. It **includes Tesseract** (engine and English data), so anyone can run it with nothing installed.
3. `config.json` and `data.txt` are created next to the EXE on first run. To keep your setup, copy your existing `config.json` next to the EXE.

---

### Antivirus warnings and code signing

Unsigned EXEs made with PyInstaller often get flagged by mistake ("false positives"). TwisterX Auto Roller also does things antivirus heuristics watch for: it simulates mouse clicks, takes screenshots and sends Discord webhooks.

**Already done in the build:** UPX compression is off, and the EXE carries full file properties (name, version, description). Both reduce false positives.

**To stop the warnings properly, sign the EXE with a code-signing certificate:**

1. Get a certificate:
   - **Azure Trusted Signing**: about $10/month, the cheapest real option. Needs identity verification.
   - **OV certificate** from a vendor such as Certum, Sectigo or DigiCert: roughly $100–$400/year.
   - **SignPath Foundation**: free, but only for open-source projects.
2. Export it as a `.pfx` file. Then, in a Command Prompt in the app folder, run:
   ```
   set SIGN_PFX=C:\path\to\certificate.pfx
   set SIGN_PASSWORD=your-password
   build.bat
   ```
   `build.bat` signs and timestamps `dist\TwisterX Auto Roller.exe` automatically. It needs `signtool.exe`, which comes with the free Windows SDK.
3. After signing, SmartScreen still needs a little time and downloads to build reputation. The warnings fade as more people run the same signed EXE.

**A self-signed certificate does not help.** It only satisfies your own PC; everyone else still gets the warning.

**Free things that also help:**
- If an antivirus flags it, submit the EXE as a false positive: Microsoft Defender at https://www.microsoft.com/wdsi/filesubmission, and other vendors through their own forms.
- Share the `.py` with `Start TwisterX Auto Roller.bat` instead of the EXE. Scripts are flagged much less often.

---

## 10. FAQ and troubleshooting

| Problem | Answer |
|---|---|
| "Tesseract not found!" in the log | Use the EXE (Tesseract is built in), or run `Start TwisterX Auto Roller.bat`, which installs it. |
| `Cannot join: No server link saved.` | Paste the link and click **Save**. |
| **Bad link** error | Use one of the two link styles in 3.1. |
| Roblox opens but nothing is clicked | Check **Click in-game buttons**, calibrate **Forecast (2nd)**, raise **Load wait**, and raise the click timing values. |
| Clicks land in the wrong place | Calibrate again after any window or resolution change. Screenshots cover all monitors, so Roblox can be on any screen, but recalibrate if you move it. |
| `No values read` | See 4.7. |
| Webhook test fails with 401/404 | The webhook was deleted or copied wrong. Copy it again. |
| Ping shows `@unknown-role` | Set your own **Role ID**, or turn off **Ping role**. |
| Loop stopped by itself | The pass popup appeared and you chose **Stop here** (or closed it). Turn off **Popup on pass** to keep looping. |
| No tray icon or notifications | Run `python -m pip install pystray`. |
| Accent colour didn't change | Restart the app. |
| Window vanished when I closed it | It went to the tray. The first time you press X the app asks: **Yes** = quit, **No** = keep in tray. To change it later, use **Settings → Close button**. To quit from the tray, right-click the icon → **Quit**. |
| Opening the app again does nothing | Only one copy can run. Opening it again brings the running window to the front, even from the tray. |
| Mouse-to-corner didn't stop it | Push it fully into the corner (within 3 px). It is checked during waits and clicks, not while Tesseract is reading. |

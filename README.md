<p align="center"><img src="assets/icon.png" width="96" alt="TwisterX Auto Roller icon"></p>

<h1 align="center">TwisterX Auto Roller</h1>

<p align="center">
Joins your Roblox private server, reads the forecast panel with OCR, checks it against your requirements,
and rerolls until it finds what you want, with Discord notifications.
</p>

---

## Download

Get **`TwisterX-Auto-Roller.exe`** from the [latest release](../../releases/latest) and double-click it.
That's it: Python, every package and Tesseract OCR are built into the EXE. Nothing else to install.

> **"Windows protected your PC"?** The EXE isn't code-signed yet, so SmartScreen warns about it.
> Click **More info → Run anyway**, or right-click the file → **Properties** → tick **Unblock**.
> The full source is right here if you'd rather check it or build it yourself.

## Features

- **Auto join and reroll:** opens your private server from its link, clicks the in-game buttons, reads the forecast and rejoins until your requirements pass.
- **OCR:** reads Risk, Temperature, Dew point, PWAT, SRH, CAPE, Lapse Rates, Humidity, Storm Motion and Day.
- **Requirements:** normal rows (all must pass) plus **Solo** rows (any one is enough).
- **Record hunt:** separate "beat this value" targets that send a full screenshot without stopping the loop.
- **Discord webhooks:** embeds with the values, a thermos screenshot and an optional role ping.
- **Modern UI:** dark/light mode, a built-in guided tour, tray icon, one instance only, and an emergency stop (Esc or push the mouse into a screen corner).

## Run from source

1. Download the source (green **Code** button → **Download ZIP**) and extract it.
2. Double-click **`Start TwisterX Auto Roller.bat`**. The first time, it installs anything missing (Python, the packages, Tesseract OCR), then opens the app.

Or do it by hand:

```bash
pip install customtkinter pyautogui pillow pytesseract mss requests pystray
python TwisterX_Auto_Roller.py
```

Tesseract OCR is also needed: install the [UB Mannheim build](https://github.com/UB-Mannheim/tesseract/wiki) to the default folder.

## Build the EXE yourself

Double-click **`build.bat`**. It creates a clean build environment, installs Tesseract if needed and produces
`dist\TwisterX Auto Roller.exe`. If you have a code-signing certificate, set `SIGN_PFX` and `SIGN_PASSWORD`
first and the EXE gets signed automatically.

## How to use it

The app opens with a guided tour that points at every feature. The full step-by-step guide is in
**[TUTORIAL.md](TUTORIAL.md)**: setup, calibration, requirements, records, every setting and troubleshooting.

Your settings are saved in `config.json` and your scan history in `data.txt`, next to the EXE or script.
Both stay on your PC.

## Disclaimer

This is a fan-made tool and isn't affiliated with Roblox or the game's developers. It automates mouse clicks
and reads your screen. Use it at your own risk and follow the rules of the games you play.

## License

[MIT](LICENSE). Third-party components bundled in the EXE are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

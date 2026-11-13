# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for TwisterX_Auto_Roller.py
# Builds ONE standalone EXE that includes Python, every package AND Tesseract OCR,
# so it runs on any Windows PC with nothing else installed.
# Run with:  pyinstaller build.spec   (or just double-click build.bat)

import os
import shutil
from glob import glob
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None


def find_tesseract_dir():
    for d in (os.environ.get("TESSERACT_DIR"),
              os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Tesseract-OCR"),
              os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Tesseract-OCR"),
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Tesseract-OCR"),
              os.path.dirname(shutil.which("tesseract") or "")):
        if d and os.path.isfile(os.path.join(d, "tesseract.exe")):
            return d
    raise SystemExit("Tesseract not found. Install it (build.bat does this) or set TESSERACT_DIR.")


TESS = find_tesseract_dir()
print("Bundling Tesseract from:", TESS)

# Only what OCR needs: the engine, its DLLs and English language data (skip training tools).
tess_bins = [(os.path.join(TESS, "tesseract.exe"), "tesseract")]
tess_bins += [(dll, "tesseract") for dll in glob(os.path.join(TESS, "*.dll"))]
tess_datas = [(os.path.join(TESS, "tessdata", "eng.traineddata"), "tesseract/tessdata")]
for sub in ("configs", "tessconfigs"):
    for f in glob(os.path.join(TESS, "tessdata", sub, "*")):
        if os.path.isfile(f):
            tess_datas.append((f, f"tesseract/tessdata/{sub}"))

a = Analysis(
    ['TwisterX_Auto_Roller.py'],
    pathex=[],
    binaries=tess_bins,
    datas=collect_data_files('customtkinter') + tess_datas,
    hiddenimports=[
        'PIL._tkinter_finder',
        'pytesseract',
        'mss',
        'requests',
        'pystray._win32',
        'customtkinter',
        'darkdetect',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Safety net if built outside the clean venv: never bundle these heavy, unused libraries.
    excludes=['torch', 'torchvision', 'torchaudio', 'tensorflow', 'tensorboard', 'transformers', 'timm',
              'onnxruntime', 'sklearn', 'scipy', 'pandas', 'pyarrow', 'matplotlib', 'cv2', 'numpy',
              'nltk', 'av', 'soundfile', 'boto3', 'botocore', 'grpc', 'sqlalchemy', 'psycopg_binary',
              'lxml', 'openpyxl', 'jinja2', 'pydantic', 'uvicorn', 'websockets', 'IPython', 'notebook'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TwisterX Auto Roller',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,            # UPX can corrupt the Tesseract DLLs
    runtime_tmpdir=None,
    console=False,        # no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
    version='version_info.txt',  # file properties: name, version, description
)

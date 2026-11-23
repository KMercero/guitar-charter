# build/build.spec  — run from repo root: pyinstaller build/build.spec
a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    # Removed basic_pitch, added mido
    hiddenimports=['librosa', 'soundfile', 'PySide6', 'mido'],
    hookspath=[],
    runtime_hooks=[],
    # Exclude heavy ML libraries because we run them via subprocess
    excludes=['torch', 'torchaudio', 'tensorflow', 'keras', 'basic_pitch'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='GuitarCharter',
    console=False,
    onefile=True,
)
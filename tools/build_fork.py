"""Build an extended Windows app using the upstream PyInstaller spec."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from prepare_fork import check


def main():
    check()
    if sys.platform != 'win32':
        raise SystemExit('The distributable Windows build must run on Windows. Use GitHub Actions if needed.')
    src = ROOT / 'PokopiaEditor.spec'
    data = src.read_text(encoding='utf-8')
    count = data.count('pokopia_gui.py')
    if count != 1:
        raise SystemExit(f'Expected exactly one source entry in upstream spec; found {count}. Please review the spec.')
    updated = data.replace('pokopia_gui.py', 'pokopia_gui_fork.py', 1)
    updated = updated.replace("StringStruct('FileDescription', 'Pokopia Editor')", "StringStruct('FileDescription', 'Pokopia Editor RSH')")
    updated = updated.replace("StringStruct('ProductName', 'Pokopia Editor')", "StringStruct('ProductName', 'Pokopia Editor RSH')")
    updated = updated.replace("StringStruct('OriginalFilename', 'PokopiaEditor.exe')", "StringStruct('OriginalFilename', 'PokopiaEditor_RSH.exe')")
    updated = updated.replace("name='PokopiaEditor'", "name='PokopiaEditor_RSH'")
    tmp = ROOT / 'PokopiaEditor.fork-build.spec'
    tmp.write_text(updated, encoding='utf-8')
    try:
        subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', str(tmp)], cwd=ROOT, check=True)
        print('Build completed. Check the dist directory.')
    finally:
        tmp.unlink(missing_ok=True)

if __name__ == '__main__':
    main()

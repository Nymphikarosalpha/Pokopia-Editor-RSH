# Build for Windows

## Prerequisites

Use a checkout of the actual fork of `cycalo/Pokopia-Editor`, containing the complete original project plus the extension files from this package. Python 3 and the project build dependencies are required.

```powershell
py -m pip install PySide6-Essentials pillow pyinstaller
py tools\prepare_fork.py
py tools\build_fork.py
```

`tools/build_fork.py` creates a temporary adaptation of the original `PokopiaEditor.spec` that starts `pokopia_gui_fork.py`. The upstream spec file is not overwritten. The expected output is `dist/PokopiaEditor_RSH.exe` unless the original spec uses another output name.

If the upstream build configuration changes and the entry script cannot be located unambiguously, the build stops instead of silently making an unmodified executable.

## GitHub Actions

Open **Actions > Build Windows Preview > Run workflow**. After a successful build, the executable is available as a **workflow artifact**. It is not automatically published as a Release. Test the Windows build with a copied game save before attaching it to a public release.

## Troubleshooting

- `PokopiaEditor.spec` missing: the overlay was copied to an empty repository rather than a fork of the original project.
- `pokopia_gui.py` not detected in the spec: inspect upstream build changes and update `tools/build_fork.py`.
- Python dependency missing: use the original project's README and build requirements.
- No new controls visible: verify the launch entry is `pokopia_gui_fork.py`, not the original `pokopia_gui.py`.

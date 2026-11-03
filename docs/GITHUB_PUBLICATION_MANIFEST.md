# MediaForge — GitHub publication manifest

Inventory generated and checked with `tools/audit_publication.py` on 2026-11-03. Paths below are relative to the project root and describe the current intended source-only repository. The audit excludes generated/local subtrees before classifying files, scans publishable text candidates for common secret patterns, and never prints matched values.

## A. ARQUIVOS INCLUÍDOS

**124 arquivos aprovados no inventário atual**, incluindo este manifesto:

```text
.gitignore
build_exe.bat
docs/ARQUITETURA.md
docs/GITHUB_PUBLICATION_MANIFEST.md
docs/LICENCIAMENTO_QT.md
docs/qt-source-manifest.md
docs/SEGURANCA.md
LICENSE
LICENSES/Lucide-ISC.txt
LICENSES/Python/brotli-1.2.1/LICENSE
LICENSES/Python/certifi-2026.10.23/LICENSE
LICENSES/Python/charset-normalizer-3.5.2/LICENSE
LICENSES/Python/idna-3.20/LICENSE.md
LICENSES/Python/pycryptodomex-3.24.1/LICENSE.rst
LICENSES/Python/requests-2.34.2/LICENSE
LICENSES/Python/requests-2.34.2/NOTICE
LICENSES/Python/urllib3-2.8.0/LICENSE.txt
LICENSES/Python/websockets-17.3/LICENSE
LICENSES/Python/yt-dlp-2026.10.26/LICENSE
LICENSES/Python/yt-dlp-ejs-0.8.0/LICENSE
LICENSES/Qt/pyside-setup-everywhere-src-6.12.0/LICENSES/Apache-2.0.txt
LICENSES/Qt/pyside-setup-everywhere-src-6.12.0/LICENSES/BSD-3-Clause.txt
LICENSES/Qt/pyside-setup-everywhere-src-6.12.0/LICENSES/GFDL-1.3-no-invariants-only.txt
LICENSES/Qt/pyside-setup-everywhere-src-6.12.0/LICENSES/GPL-2.0-only.txt
LICENSES/Qt/pyside-setup-everywhere-src-6.12.0/LICENSES/GPL-3.0-only.txt
LICENSES/Qt/pyside-setup-everywhere-src-6.12.0/LICENSES/LGPL-3.0-only.txt
LICENSES/Qt/pyside-setup-everywhere-src-6.12.0/LICENSES/LicenseRef-Qt-Commercial.txt
LICENSES/Qt/pyside-setup-everywhere-src-6.12.0/LICENSES/Qt-GPL-exception-1.0.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/AFL-2.1.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/Apache-2.0.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/Bitstream-Vera.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/blessing.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/BSD-2-Clause.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/BSD-3-Clause.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/BSD-4-Clause.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/BSL-1.0.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/CC0-1.0.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/FTL.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/GFDL-1.3-no-invariants-only.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/GPL-2.0-only.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/GPL-2.0-or-later.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/GPL-3.0-only.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/HPND.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/IJG.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/Imlib2.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/IPL-1.0.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/LGPL-2.1-or-later.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/LGPL-3.0-only.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/libpng-2.0.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/Libpng.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/LicenseRef-BSD-3-Clause-with-PCRE2-Binary-Like-Packages-Exception.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/LicenseRef-ICC-License.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/LicenseRef-Lcs-Telegraphics.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/LicenseRef-Qt-Commercial.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/LicenseRef-SHA1-Public-Domain.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/Linux-syscall-note.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/MIT-Khronos-old.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/MIT-open-group.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/MIT.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/MPL-2.0.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/Qt-GPL-exception-1.0.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/SPL-1.0.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/Unicode-3.0.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/X11.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/Xerox.txt
LICENSES/Qt/qtbase-everywhere-src-6.12.0/LICENSES/Zlib.txt
LICENSES/Qt/qtimageformats-everywhere-src-6.12.0/LICENSES/BSD-3-Clause.txt
LICENSES/Qt/qtimageformats-everywhere-src-6.12.0/LICENSES/GFDL-1.3-no-invariants-only.txt
LICENSES/Qt/qtimageformats-everywhere-src-6.12.0/LICENSES/GPL-2.0-only.txt
LICENSES/Qt/qtimageformats-everywhere-src-6.12.0/LICENSES/GPL-3.0-only.txt
LICENSES/Qt/qtimageformats-everywhere-src-6.12.0/LICENSES/LGPL-3.0-only.txt
LICENSES/Qt/qtimageformats-everywhere-src-6.12.0/LICENSES/libtiff.txt
LICENSES/Qt/qtimageformats-everywhere-src-6.12.0/LICENSES/LicenseRef-Qt-Commercial.txt
LICENSES/Qt/qtsvg-everywhere-src-6.12.0/LICENSES/BSD-3-Clause.txt
LICENSES/Qt/qtsvg-everywhere-src-6.12.0/LICENSES/GFDL-1.3-no-invariants-only.txt
LICENSES/Qt/qtsvg-everywhere-src-6.12.0/LICENSES/GPL-2.0-only.txt
LICENSES/Qt/qtsvg-everywhere-src-6.12.0/LICENSES/GPL-3.0-only.txt
LICENSES/Qt/qtsvg-everywhere-src-6.12.0/LICENSES/HPND-sell-variant.txt
LICENSES/Qt/qtsvg-everywhere-src-6.12.0/LICENSES/LGPL-3.0-only.txt
LICENSES/Qt/qtsvg-everywhere-src-6.12.0/LICENSES/LicenseRef-Qt-Commercial.txt
LICENSES/README.md
mediaforge/__init__.py
mediaforge/__main__.py
mediaforge/app.py
mediaforge/errors.py
mediaforge/models/__init__.py
mediaforge/models/formats.py
mediaforge/models/task.py
mediaforge/services/__init__.py
mediaforge/services/download_service.py
mediaforge/services/ffmpeg_locator.py
mediaforge/services/fs_utils.py
mediaforge/services/media_service.py
mediaforge/services/metadata_service.py
mediaforge/services/proc.py
mediaforge/services/source_policy.py
mediaforge/services/task_manager.py
mediaforge/storage/__init__.py
mediaforge/storage/history.py
mediaforge/storage/settings.py
mediaforge/ui/__init__.py
mediaforge/ui/assets/square-letter-m.svg
mediaforge/ui/dialogs.py
mediaforge/ui/main_window.py
mediaforge/ui/styles.py
mediaforge/utils.py
MediaForgeLocal.spec
pyproject.toml
README.md
requirements-dev.txt
requirements.txt
run.bat
tests/__init__.py
tests/conftest.py
tests/test_download_service.py
tests/test_fs_utils.py
tests/test_history.py
tests/test_media_service.py
tests/test_policy_compliance.py
tests/test_source_policy.py
tests/test_task_manager.py
tests/test_ui_smoke.py
THIRD_PARTY_NOTICES.md
tools/audit_publication.py
```

Inclusion reasons: application code and asset, tests, project docs, license texts/notices, and necessary development/build configuration. `LICENSE` is MIT for original MediaForge code only; third-party terms remain separate.

## B. ARQUIVOS EXCLUÍDOS

**12.257 files excluded** in the audit. The following generated/local trees were present and excluded recursively:

| Relative path | Files | Reason |
|---|---:|---|
| `.venv/` | 11,790 | Local Python environment and installed packages |
| `build/` | 17 | PyInstaller intermediates, logs, warnings, and generated reports |
| `dist/` | 368 | Executable distribution, DLLs, Qt runtime/plugins, and bundled Python files |
| `.pytest_cache/` | 5 | Test cache |
| `mediaforge/__pycache__/` | 5 | Bytecode cache |
| `mediaforge/models/__pycache__/` | 3 | Bytecode cache |
| `mediaforge/services/__pycache__/` | 9 | Bytecode cache |
| `mediaforge/storage/__pycache__/` | 3 | Bytecode cache |
| `mediaforge/ui/__pycache__/` | 4 | Bytecode cache |
| `tests/__pycache__/` | 19 | Bytecode cache |
| `tools/__pycache__/` | 1 | Bytecode cache |

The following 33 preserved backups were found and excluded; none was deleted:

```text
.gitignore.before-publication-audit-20261103-115129.bak
.gitignore.phase2-20261029-233137.bak
build_exe.bat.before-ejs-build-20261103-083403.bak
build_exe.bat.before-mutagen-removal-20261103-095956.bak
build_exe.bat.phase2-20261029-233137.bak
docs/ARQUITETURA.md.phase2-20261029-233137.bak
docs/SEGURANCA.md.phase2-20261029-233137.bak
mediaforge/services/download_service.py.20261029-170529.bak
mediaforge/services/download_service.py.20261029-224423.bak
mediaforge/services/download_service.py.20261029-224705.bak
mediaforge/ui/dialogs.py.20261029-183323.bak
mediaforge/ui/dialogs.py.20261029-183555.bak
mediaforge/ui/dialogs.py.phase2-20261029-233137.bak
mediaforge/ui/main_window.py.20261029-172949.bak
mediaforge/ui/main_window.py.20261029-181513.bak
mediaforge/ui/main_window.py.20261029-182428.bak
mediaforge/ui/main_window.py.20261029-182516.bak
mediaforge/ui/main_window.py.20261029-224423.bak
mediaforge/ui/main_window.py.before-qtable-fix-20261103-085837.bak
MediaForgeLocal.spec.before-mutagen-removal-20261103-095956.bak
pyproject.toml.before-ejs-build-20261103-083403.bak
pyproject.toml.before-mutagen-removal-20261103-095956.bak
pyproject.toml.phase2-20261029-233137.bak
README.md.before-build-validation-20261103-092527.bak
README.md.before-ejs-build-20261103-083403.bak
README.md.before-mutagen-removal-20261103-095956.bak
README.md.phase2-20261029-233137.bak
requirements.txt.before-ejs-build-20261103-083403.bak
requirements.txt.before-mutagen-removal-20261103-095956.bak
tests/test_download_service.py.phase2-20261029-233137.bak
tests/test_ui_smoke.py.before-history-wait-20261103-080917.bak
tests/test_ui_smoke.py.before-pytest-fix-20261103-080156.bak
tests/test_ui_smoke.py.phase2-20261029-233137.bak
```

There was no `.git/`, `.vscode/`, `.idea/`, local `.env`, database/history, dump, or log directory in the project root. No executable, DLL, Python extension, database, or ZIP archive was found outside the excluded build/runtime directories. The project has no code-workspace file.

Five Qt ZIPs (the four official source archives and their separate corresponding-source bundle) are stored outside this project under the sibling `mediaforge-release-assets/` directory. They were not part of this project-root file count and must remain outside the source repository.

## C. ARQUIVOS PENDENTES

- **Nenhum arquivo suspeito ou pendente de classificação no inventário de texto atual.** The audit reported 0 potential secrets, 0 unreadable text candidates, and 0 pending paths. The two credential-shaped URLs in tests are limited to reserved test domains and test fixtures; no matched values are emitted by the audit.
- `.gitignore` was expanded to cover IDE/workspace settings, archives, compiled binaries/extensions, databases, and diagnostic outputs. Its pre-change copy is preserved as `.gitignore.before-publication-audit-20261103-115129.bak`; that backup is excluded from publication.
- **Binary distribution remains a separate release blocker:** exact source/build provenance for Qt/PySide/Shiboken binaries, per-file license selection, a successful replacement test using a modified compatible Qt library, and review of redistributions/other bundled components (including Microsoft runtime files) remain unverified. No full LGPL compliance claim is made.
- The Qt source ZIPs and bundle are external files, not repository files. A source-only GitHub publication should not add them, the executable, or runtime DLLs.
- The audit is a pattern-based source review, not a proof that every possible secret format is absent. Re-run it immediately before staging; review any new alert without disclosing its value.

## D. ESTADO DA PUBLICAÇÃO

- **Pronto para inicializar Git:** sim, for the current source-only file set, subject to the owner reviewing the manifest and the MIT attribution.
- **Pronto para publicação pública do código-fonte:** sim, based on the current inventory, source-only scope, license files, and zero secret-pattern findings. No Git repository was initialized and no files were published.
- **Distribuição pública do executável:** ainda bloqueada. This source-publication status does not establish LGPL compliance or authorize binary redistribution. Resolve the binary release checks in `docs/LICENCIAMENTO_QT.md` before distributing the executable.

## Reproducing the inventory

From the project root, run:

```powershell
.\.venv\Scripts\python.exe tools\audit_publication.py
```

Use `--format json` for file-level inclusion/exclusion records. The tool is read-only, writes no report, deletes nothing, and does not invoke Git. It exits nonzero when it finds a possible secret or an unreadable candidate.

# Third-Party Notices and License Summary

The MIT license in [LICENSE](./LICENSE) applies only to original MediaForge code. It does not relicense third-party software or assets distributed with the application.

The complete license texts collected for the versions used in the current Windows build are under [LICENSES](./LICENSES/). The Qt source archive manifest and source-package instructions are in [docs/LICENCIAMENTO_QT.md](./docs/LICENCIAMENTO_QT.md) and [docs/qt-source-manifest.md](./docs/qt-source-manifest.md).

## Qt, PySide6, and Shiboken6

The current packaged build contains PySide6-Essentials 6.12.0 and Shiboken6 6.12.0. Their installed package metadata declares `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`; this is an expression of licensing options, not a declaration that all options or all Qt components have been legally assessed for this distribution.

The build includes Qt 6.12.0 shared libraries, Python bindings, Shiboken, and Qt plugins. These components retain their own upstream terms. Qt's per-module license texts and notices are copied from the corresponding official source archives under `LICENSES/Qt/`. The source archives are not part of the source-code repository; see the Qt licensing documentation for the separate corresponding-source package.

No claim of LGPL compliance is made by this notice. In particular, identifying and satisfying the applicable terms for each distributed library and plugin, documenting the exact corresponding source/build provenance, and validating replacement of modified Qt libraries remain release checks.

## Python runtime dependencies

Versions and license expressions below were read from the installed package metadata used for the current build. Full package license texts are included under `LICENSES/Python/`.

| Package | Version | Declared license |
|---|---:|---|
| yt-dlp | 2026.10.26 | Unlicense |
| yt-dlp-ejs | 0.8.0 | Unlicense AND MIT AND ISC |
| requests | 2.34.2 | Apache-2.0 |
| urllib3 | 2.8.0 | MIT |
| certifi | 2026.10.23 | MPL-2.0 |
| pycryptodomex | 3.24.1 | BSD and Public Domain notices |
| Brotli | 1.2.1 | MIT |
| websockets | 17.3 | BSD-3-Clause |
| idna | 3.20 | BSD-3-Clause |
| charset-normalizer | 3.5.2 | MIT |

The `square-letter-m.svg` asset is from Lucide Icons and is distributed under ISC terms; the complete notice is in `LICENSES/Lucide-ISC.txt`.

## Distribution

The Windows folder build includes this notice, the MediaForge MIT license, the collected third-party license texts, and the Qt licensing documentation. Distribute those files alongside the executable folder. The separate Qt corresponding-source package must accompany a binary distribution that relies on it; see `docs/LICENCIAMENTO_QT.md`.

This summary is informational and does not establish legal compliance. Other bundled components, including Microsoft runtime files, may have separate terms that require review before public distribution.

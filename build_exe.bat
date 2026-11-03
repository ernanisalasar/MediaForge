@echo off
setlocal
cd /d "%~dp0"

REM Deno nao e incluido; e necessario no PATH para downloads do YouTube.

if not exist ".venv\Scripts\python.exe" (
    echo ERRO: ambiente .venv nao encontrado.
    exit /b 1
)

".venv\Scripts\python.exe" -m pip install "pyinstaller>=6.15.0"
if errorlevel 1 (
    echo ERRO: nao foi possivel instalar o PyInstaller.
    exit /b 1
)

".venv\Scripts\python.exe" -m PyInstaller --noconfirm MediaForgeLocal.spec

if errorlevel 1 (
    echo ERRO: PyInstaller nao conseguiu gerar o executavel.
    exit /b 1
)

if not exist "dist\MediaForgeLocal\MediaForgeLocal.exe" (
    echo ERRO: executavel nao encontrado no destino esperado.
    exit /b 1
)

for %%F in (
    "dist\MediaForgeLocal\_internal\LICENSE"
    "dist\MediaForgeLocal\_internal\THIRD_PARTY_NOTICES.md"
    "dist\MediaForgeLocal\_internal\docs\LICENCIAMENTO_QT.md"
    "dist\MediaForgeLocal\_internal\docs\qt-source-manifest.md"
    "dist\MediaForgeLocal\_internal\LICENSES\README.md"
    "dist\MediaForgeLocal\_internal\LICENSES\Lucide-ISC.txt"
    "dist\MediaForgeLocal\_internal\LICENSES\Qt\qtbase-everywhere-src-6.12.0\LICENSES\LGPL-3.0-only.txt"
    "dist\MediaForgeLocal\_internal\LICENSES\Python\requests-2.34.2\LICENSE"
) do (
    if not exist "%%~F" (
        echo ERRO: arquivo de licenciamento nao incluido: %%F
        exit /b 1
    )
)

echo.
echo BUILD CONCLUIDO: dist\MediaForgeLocal\MediaForgeLocal.exe
echo Avisos de licencas incluidos no diretorio da aplicacao.
echo Distribua tambem o pacote separado de fontes Qt correspondente.
echo Lembrete: FFmpeg e Deno devem ser instalados separadamente.
endlocal
exit /b 0

@echo off
REM ============================================================================
REM Compila el plugin 'colliders' para una version de Maya y deja el .mll en
REM plugins\<version>\colliders.mll (donde load_plugin() lo busca).
REM
REM Uso:
REM    build.bat <MAYA_VERSION> ["<MAYA_DEVKIT_DIR>"]
REM
REM Ejemplos:
REM    build.bat 2026                  (auto-detecta devkit del install de Maya + cmake de VS)
REM    build.bat 2024
REM    build.bat 2026 "C:\otro\devkit"
REM
REM Maya 2024/2026 traen el devkit dentro de su install. Localiza el cmake del propio
REM Visual Studio si no esta en el PATH. Requiere VS 2022 con "Desktop development C++".
REM ============================================================================
setlocal enabledelayedexpansion
if "%~1"=="" (
  echo Uso: build.bat ^<MAYA_VERSION^> ["^<MAYA_DEVKIT_DIR^>"]
  exit /b 1
)
set "VER=%~1"
set "DEVKIT=%~2"
set "HERE=%~dp0"

REM --- devkit (auto del install de Maya si no se pasa) ---
if "%DEVKIT%"=="" set "DEVKIT=C:\Program Files\Autodesk\Maya%VER%"
if not exist "%DEVKIT%\include\maya\MFnPlugin.h" (
  echo [colliders] No encuentro el devkit en "%DEVKIT%".
  echo            Pasa la ruta: build.bat %VER% "C:\ruta\al\devkit"
  exit /b 1
)

REM --- localizar cmake: PATH, o el que trae Visual Studio ---
set "CMAKE_EXE="
where cmake >nul 2>&1 && set "CMAKE_EXE=cmake"
if not defined CMAKE_EXE (
  set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
  if exist "!VSWHERE!" (
    for /f "usebackq delims=" %%I in (`"!VSWHERE!" -latest -property installationPath 2^>nul`) do set "VSINSTALL=%%I"
  )
  if defined VSINSTALL (
    set "CAND=!VSINSTALL!\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
    if exist "!CAND!" set "CMAKE_EXE=!CAND!"
  )
)
if not defined CMAKE_EXE (
  echo [colliders] No encuentro cmake. Abre "Developer PowerShell for VS 2022" y reintenta,
  echo            o instala CMake en el PATH.
  exit /b 1
)

echo [colliders] Maya %VER%  devkit: "%DEVKIT%"
echo [colliders] cmake: "!CMAKE_EXE!"

"!CMAKE_EXE!" -S "%HERE%." -B "%HERE%build\%VER%" -G "Visual Studio 17 2022" -A x64 -DMAYA_DEVKIT_DIR="%DEVKIT%"
if errorlevel 1 ( echo [colliders] cmake configure fallo & exit /b 1 )

"!CMAKE_EXE!" --build "%HERE%build\%VER%" --config Release
if errorlevel 1 ( echo [colliders] build fallo & exit /b 1 )

if not exist "%HERE%plugins\%VER%" mkdir "%HERE%plugins\%VER%"
copy /Y "%HERE%build\%VER%\Release\colliders.mll" "%HERE%plugins\%VER%\colliders.mll"
echo [colliders] Listo: plugins\%VER%\colliders.mll
endlocal

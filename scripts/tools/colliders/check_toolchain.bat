@echo off
setlocal enabledelayedexpansion
echo ============================================================
echo  colliders - comprobacion de toolchain para compilar el .mll
echo ============================================================
set "OK=1"

REM --- CMake ---
set "CMAKE_FOUND="
where cmake >nul 2>&1 && set "CMAKE_FOUND=cmake (en PATH)"
if not defined CMAKE_FOUND (
  for /d %%E in ("C:\Program Files\Microsoft Visual Studio\2022\*") do (
    if exist "%%E\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe" set "CMAKE_FOUND=%%E (CMake de VS)"
  )
)
if defined CMAKE_FOUND (
  echo [OK]    CMake: !CMAKE_FOUND!
) else (
  echo [FALTA] CMake no encontrado. Viene con el workload C++ de VS 2022, o instalalo aparte.
  set "OK=0"
)

REM --- Visual Studio 2022 con herramientas C++ ---
set "VS_FOUND="
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if exist "%VSWHERE%" (
  for /f "usebackq delims=" %%I in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2^>nul`) do set "VS_FOUND=%%I"
)
if defined VS_FOUND (
  echo [OK]    Visual Studio C++: !VS_FOUND!
) else (
  echo [FALTA] Visual Studio 2022 con "Desktop development with C++" no encontrado.
  set "OK=0"
)

REM --- Devkits (ya vienen dentro del install de Maya) ---
for %%V in (2024 2026) do (
  if exist "C:\Program Files\Autodesk\Maya%%V\include\maya\MFnPlugin.h" (
    echo [OK]    Devkit Maya %%V: C:\Program Files\Autodesk\Maya%%V
  ) else (
    echo [aviso] Sin devkit para Maya %%V ^(no instalado^). build.bat %%V pedira la ruta.
  )
)

echo ------------------------------------------------------------
if "%OK%"=="1" (
  echo TODO LISTO. Puedes compilar:   build.bat 2024     y     build.bat 2026
) else (
  echo FALTA toolchain. Instala Visual Studio 2022 Community con el workload
  echo "Desktop development with C++" ^(incluye MSVC v143 y CMake^) y reintenta.
)
endlocal

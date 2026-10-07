@echo off
setlocal
cd /d "%~dp0"
where cmake >nul 2>nul
if errorlevel 1 (
  echo CMake was not found. Install Visual Studio 2022 with Desktop development for C++ and CMake tools.
  exit /b 1
)
cmake -S . -B build -A x64
if errorlevel 1 exit /b 1
cmake --build build --config Release
if errorlevel 1 exit /b 1
echo.
echo Built overlay proxy: %CD%\build\Release\d3d11.dll
echo Copy that file into The Sims 4 Game\Bin folder to enable the F11 ImGui overlay.
endlocal

@echo off
REM Build a self-contained Windows .exe using PyInstaller.
REM Requires Python and PyInstaller installed on the build machine.

cd /d "%~dp0"

echo Cleaning previous build artifacts...
rmdir /s /q build  2>nul
rmdir /s /q dist   2>nul

echo.
echo Building new executable with PyInstaller...
echo Using MyGame.spec for configuration...
echo.

pyinstaller --noconfirm MyGame.spec

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo BUILD FAILED! Check the error messages above.
    pause
    exit /b 1
)

echo.
echo ============================================
echo Build complete! 
echo Executable: dist\MyGame.exe
echo ============================================
echo.
echo You can share this EXE with other Windows users who do not have Python installed.
echo.

pause

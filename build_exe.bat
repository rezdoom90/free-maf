@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

:: 0. Verify running from agent/ directory
if not exist "file_parser_app.py" (
    echo Script must be located in and run from the agent/ folder.
    pause
    exit /b 1
)

:: 1. Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found. Starting automatic installation...
    goto :install_python_winget
) else (
    goto :check_packages
)

:install_python_winget
winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements >nul 2>&1
if errorlevel 1 (
    echo winget unavailable, trying to download installer...
    goto :install_python_curl
) else (
    goto :refresh_path
)

:install_python_curl
where curl >nul 2>&1
if errorlevel 1 (
    echo curl not found.
    echo Please install Python manually: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo Downloading Python 3.12...
curl -L -o "%TEMP%\python-3.12-installer.exe" "https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe"
if errorlevel 1 (
    echo Download error. Install Python manually: https://www.python.org/downloads/
    pause
    exit /b 1
)
"%TEMP%\python-3.12-installer.exe" /quiet InstallAllUsers=0 PrependPath=1
if errorlevel 1 (
    echo Python installation error.
    pause
    exit /b 1
)
del "%TEMP%\python-3.12-installer.exe"

:refresh_path
set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%LOCALAPPDATA%\Programs\Python\Python312"
python --version >nul 2>&1
if errorlevel 1 (
    echo Python installed but not found in PATH. Restart the terminal and try again.
    pause
    exit /b 1
)
echo Python successfully installed.

:check_packages

:: 2. Upgrade pip
echo Updating pip...
python -m pip install --upgrade pip --quiet

:: 3. Install pyperclip
echo Checking pyperclip...
python -m pip show pyperclip >nul 2>&1
if errorlevel 1 (
    echo Installing pyperclip...
    python -m pip install pyperclip --quiet
    if errorlevel 1 (
        echo pyperclip installation error. Run manually: pip install pyperclip
        pause
        exit /b 1
    )
)

:: 4. Check / install PyInstaller
echo Checking PyInstaller...
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    python -m pip install pyinstaller --quiet
    if errorlevel 1 (
        echo PyInstaller installation error. Run manually: pip install pyinstaller
        pause
        exit /b 1
    )
) else (
    echo PyInstaller already installed.
)

:: 5. Build (output .exe directly into agent/)
echo.
echo Building FileParserGui.exe in agent\ ...
python -m PyInstaller --onefile --windowed --distpath "." --name FileParserGui file_parser_app.py
if errorlevel 1 (
    echo Build failed. Check errors above.
    pause
    exit /b 1
)

echo.
echo Build successful!
echo Executable: %CD%\FileParserGui.exe
echo .exe must remain in the agent/ folder.
echo Window will close in 5 seconds...
timeout /t 5 >nul
exit /b 0
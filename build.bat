@echo off
echo ======================================
echo  RhythmQuest - Build EXE + Electron
echo ======================================

echo.
echo [1/4] Installing Python dependencies...
python -m pip install pyinstaller -q
echo Done.

echo.
echo [2/4] Packaging Flask backend with PyInstaller...
python -m PyInstaller rhythmquest.spec --noconfirm --clean
if %errorlevel% neq 0 (
    echo ERROR: PyInstaller failed!
    pause
    exit /b 1
)
echo Done.

echo.
echo [3/4] Copying backend to Electron folder...
if not exist "electron\backend" mkdir "electron\backend"
xcopy /E /I /Y "dist\run_server" "electron\backend"
REM Also copy the database to run alongside EXE
if exist "rhythmquest.db" copy "rhythmquest.db" "electron\backend\rhythmquest.db"
echo Done.

echo.
echo [4/4] Building Electron installer...
cd electron
call npm install
call npm run dist
cd ..
echo Done.

echo.
echo ======================================
echo  Build Complete!
echo  Find your installer in: dist\
echo ======================================
pause

@echo off
REM ============================================================
REM  See the digest NOW, on this PC, without waiting for the cloud job.
REM
REM  Double-click this file. It runs the same script the GitHub
REM  Actions workflow runs and opens the result in your browser.
REM
REM  This is the "trigger it on the laptop" option: it needs no
REM  GitHub account, no runner minutes and no network beyond the
REM  news sources themselves. Nothing is installed and nothing is
REM  uploaded - the file it writes stays on this PC.
REM
REM  It does NOT send email. It writes the digest to output\ so it
REM  stays out of the delivered site and out of version control.
REM  Email still comes from the cloud job.
REM ============================================================
setlocal
set "HERE=%~dp0"
set "OUT=%HERE%output\digest-preview.html"
set "ERR=%HERE%output\digest-preview.err"
set "DAYS=%~1"
if "%DAYS%"=="" set "DAYS=10"

cd /d "%HERE%"

set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY (
    where py >nul 2>&1 && set "PY=py -3"
)

if not defined PY (
    echo Python 3 was not found on this PC.
    echo Install it from https://www.python.org/downloads/ then run this again.
    echo Make sure "Add python.exe to PATH" is ticked during install.
    goto done
)

if not exist "output" mkdir "output"

echo Building the digest (looking %DAYS% days ahead)...
echo This makes a few web requests, so it takes about 15-20 seconds.

%PY% scripts\personal_digest.py --days %DAYS% --html > "%OUT%" 2> "%ERR%"

if errorlevel 1 (
    echo.
    echo Something went wrong. The error text is in output\digest-preview.err:
    echo.
    type "%ERR%"
    goto done
)

echo Done. Opening it now.
start "" "%OUT%"

:done
endlocal

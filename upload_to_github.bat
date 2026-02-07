@echo off
setlocal
echo ========================================================
echo   Antigravity Github Upload Tool
echo ========================================================

:: Check for Git in PATH
git --version >nul 2>&1
if %errorlevel% equ 0 (
    set GIT_CMD=git
) else (
    :: Fallback to default install location
    if exist "C:\Program Files\Git\cmd\git.exe" (
        set GIT_CMD="C:\Program Files\Git\cmd\git.exe"
    ) else (
        echo [ERROR] Git is not installed or not in PATH. Please install Git.
        pause
        exit /b
    )
)

:: Initialize Git if not present
if not exist ".git" (
    echo [INFO] Initializing Git repository...
    %GIT_CMD% init
    %GIT_CMD% branch -M main
) else (
    echo [INFO] Git repository already exists.
)

:: Configure Remote
%GIT_CMD% remote remove origin >nul 2>&1
%GIT_CMD% remote add origin https://github.com/eneselhan/Mukabele-Bot.git
echo [INFO] Remote origin set to https://github.com/eneselhan/Mukabele-Bot.git

:: Configure Identity (if not set)
echo [INFO] Configuring Git Identity...
%GIT_CMD% config user.email "antigravity-bot@users.noreply.github.com"
%GIT_CMD% config user.name "Antigravity Bot"

:: Add Files
echo [INFO] Adding files...
%GIT_CMD% add .

:: Commit
set TIMESTAMP=%date% %time%
%GIT_CMD% commit -m "Direct upload via Antigravity: %TIMESTAMP%" || echo [INFO] Nothing to commit.

:: Push
echo [INFO] Pushing to GitHub...
%GIT_CMD% push -u origin main --force

if %errorlevel% neq 0 (
    echo [ERROR] Failed to push to GitHub. Make sure you have permissions and internet connection.
    pause
    exit /b
) else (
    echo [SUCCESS] Code uploaded successfully!
)

pause

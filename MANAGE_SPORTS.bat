@echo off
REM ============================================================
REM  Matthew Bowyer e-portfolio - manage what the digest follows
REM
REM  Double-click THIS file to add or remove the SPORTS, people, teams
REM  and competitions the daily email researches. No file to open, no
REM  commands to remember - it is a numbered menu.
REM
REM  Option 1 is the one you asked for: ADD OR REMOVE A WHOLE SPORT.
REM  Removing a sport switches it off everywhere - the event list, the
REM  result detail, the suggestions and the local-events matching - and
REM  it can be switched back on later.
REM
REM  It edits personal/data/follow.json, which is the one file that
REM  decides who and what is followed. Nothing is added that you do
REM  not type.
REM
REM  To stop: close this window.
REM ============================================================
setlocal enabledelayedexpansion
set "HERE=%~dp0"
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

:menu
cls
echo ============================================================
echo   WHAT THE DIGEST FOLLOWS
echo ============================================================
echo.
echo   SPORTS - the easy switch
echo   1  ADD a sport              (e.g. Cricket, Rugby, Darts)
echo   2  REMOVE a sport            (hides it everywhere, reversible)
echo.
echo   WHAT TO RESEARCH
echo   3  Add news to follow        (e.g. Formula 1, Springboks)
echo   4  Remove news
echo   5  Add a team to a competition
echo   6  Remove a team
echo   7  Add a competition        (see the ids first)
echo   8  Remove a competition
echo   9  Change the tennis top N
echo  10  Show teams playing in a competition right now
echo  11  Show the competition ids
echo   0  Exit
echo ------------------------------------------------------------
echo   What you follow right now:
echo.
%PY% scripts\follow_edit.py --list-sports
echo ------------------------------------------------------------
set "CHOICE="
set /p "CHOICE=Type a number and press Enter: "

if "!CHOICE!"=="1" goto add_sport
if "!CHOICE!"=="2" goto remove_sport
if "!CHOICE!"=="3" goto add_news
if "!CHOICE!"=="4" goto remove_news
if "!CHOICE!"=="5" goto add_team
if "!CHOICE!"=="6" goto remove_team
if "!CHOICE!"=="7" goto add_comp
if "!CHOICE!"=="8" goto remove_comp
if "!CHOICE!"=="9" goto top_n
if "!CHOICE!"=="10" goto list_teams
if "!CHOICE!"=="11" goto list_comps
if "!CHOICE!"=="0" goto done
echo.
echo Please type one of the numbers shown.
timeout /t 2 >nul
goto menu

:add_sport
echo.
echo Which sport do you want to ADD?
echo Examples: Cricket, Rugby, Darts, Athletics, Boxing
echo.
set "SPORT_NAME="
set /p "SPORT_NAME=Sport name: "
if "!SPORT_NAME!"=="" goto menu
echo.
%PY% scripts\follow_edit.py add-sport "!SPORT_NAME!"
goto pause_menu

:remove_sport
echo.
echo Which sport do you want to REMOVE?
echo (Type it exactly as it is listed at the top of this screen.)
echo.
set "SPORT_NAME="
set /p "SPORT_NAME=Sport name: "
if "!SPORT_NAME!"=="" goto menu
echo.
%PY% scripts\follow_edit.py remove-sport "!SPORT_NAME!"
goto pause_menu

:add_news
echo.
set "LABEL="
set /p "LABEL=What do you want news about? "
if "!LABEL!"=="" goto menu
set "SPORT="
set /p "SPORT=Which sport is it? (optional, press Enter to skip) "
echo.
if "!SPORT!"=="" (
    %PY% scripts\follow_edit.py add-news "!LABEL!"
) else (
    %PY% scripts\follow_edit.py add-news "!LABEL!" --sport "!SPORT!"
)
goto pause_menu

:remove_news
echo.
set "LABEL="
set /p "LABEL=Which one do you want to stop following? "
if "!LABEL!"=="" goto menu
echo.
%PY% scripts\follow_edit.py remove-news "!LABEL!"
goto pause_menu

:add_team
echo.
echo Competition ids (full list is option 11):
echo    uefa.champions   eng.1   esp.1   ita.1   ger.1   fra.1   rsa.1
echo.
set "LEAGUE="
set /p "LEAGUE=Which competition? "
if "!LEAGUE!"=="" goto menu
set "TEAM="
set /p "TEAM=Which team? "
if "!TEAM!"=="" goto menu
echo.
%PY% scripts\follow_edit.py add-team "!LEAGUE!" "!TEAM!"
goto pause_menu

:remove_team
echo.
set "LEAGUE="
set /p "LEAGUE=Which competition? "
if "!LEAGUE!"=="" goto menu
set "TEAM="
set /p "TEAM=Which team? "
if "!TEAM!"=="" goto menu
echo.
%PY% scripts\follow_edit.py remove-team "!LEAGUE!" "!TEAM!"
goto pause_menu

:add_comp
echo.
set "LEAGUE="
set /p "LEAGUE=Which competition id? (option 11 lists them) "
if "!LEAGUE!"=="" goto menu
echo.
%PY% scripts\follow_edit.py add-competition "!LEAGUE!"
goto pause_menu

:remove_comp
echo.
set "LEAGUE="
set /p "LEAGUE=Which competition id do you want to drop? "
if "!LEAGUE!"=="" goto menu
echo.
%PY% scripts\follow_edit.py remove-competition "!LEAGUE!"
goto pause_menu

:top_n
echo.
echo The digest reports matches involving the top N players of each tour.
echo The names come from the live rankings, so this follows whoever is
echo actually in the top N - you never list players yourself.
echo.
set "N="
set /p "N=How many? (currently 5) "
if "!N!"=="" goto menu
echo.
%PY% scripts\follow_edit.py --tennis top_n "!N!"
goto pause_menu

:list_teams
echo.
set "LEAGUE="
set /p "LEAGUE=Which competition id? (option 11 lists them) "
if "!LEAGUE!"=="" goto menu
echo.
%PY% scripts\follow_edit.py --list-teams "!LEAGUE!"
goto pause_menu

:list_comps
echo.
%PY% scripts\follow_edit.py --list-competitions
goto pause_menu

:pause_menu
echo.
echo Press any key to go back to the menu.
pause >nul
goto menu

:done
endlocal

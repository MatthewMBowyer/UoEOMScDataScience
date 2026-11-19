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
echo   3  ADD one event            (e.g. Trackmania Nations Forever)
echo   4  REMOVE one event
echo   5  SHOW my event list
echo.
echo   WHAT TO RESEARCH
echo   6  Add news to follow        (e.g. Formula 1, Springboks)
echo   7  Remove news
echo   8  Add a team to a competition
echo   9  Remove a team
echo  10  Add a competition        (see the ids first)
echo  11  Remove a competition
echo  12  Change the tennis top N
echo  13  Show teams playing in a competition right now
echo  14  Show the competition ids
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
if "!CHOICE!"=="3" goto add_event
if "!CHOICE!"=="4" goto remove_event
if "!CHOICE!"=="5" goto list_events
if "!CHOICE!"=="6" goto add_news
if "!CHOICE!"=="7" goto remove_news
if "!CHOICE!"=="8" goto add_team
if "!CHOICE!"=="9" goto remove_team
if "!CHOICE!"=="10" goto add_comp
if "!CHOICE!"=="11" goto remove_comp
if "!CHOICE!"=="12" goto top_n
if "!CHOICE!"=="13" goto list_teams
if "!CHOICE!"=="14" goto list_comps
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

:add_event
echo.
echo Add ONE event to your own list - for anything no feed publishes,
echo such as Trackmania Nations Forever or a local race.
echo.
set "EV_SPORT="
set /p "EV_SPORT=Which sport is it under? (e.g. Motorsport) "
if "!EV_SPORT!"=="" goto menu
set "EV_NAME="
set /p "EV_NAME=Event name: "
if "!EV_NAME!"=="" goto menu
set "EV_START="
set /p "EV_START=Start date (YYYY-MM-DD): "
if "!EV_START!"=="" goto menu
set "EV_END="
set /p "EV_END=End date (YYYY-MM-DD, or Enter if one day): "
echo.
if "!EV_END!"=="" (
    %PY% scripts\follow_edit.py add-event "!EV_SPORT!" "!EV_NAME!" "!EV_START!"
) else (
    %PY% scripts\follow_edit.py add-event "!EV_SPORT!" "!EV_NAME!" "!EV_START!" --end "!EV_END!"
)
goto pause_menu

:remove_event
echo.
%PY% scripts\follow_edit.py --list-events
echo.
set "EV_NAME="
set /p "EV_NAME=Which event do you want to remove? "
if "!EV_NAME!"=="" goto menu
echo.
%PY% scripts\follow_edit.py remove-event "!EV_NAME!"
goto pause_menu

:list_events
echo.
%PY% scripts\follow_edit.py --list-events
goto pause_menu

:pause_menu
echo.
echo Press any key to go back to the menu.
pause >nul
goto menu

:done
endlocal

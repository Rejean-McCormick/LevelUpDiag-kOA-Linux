@echo off
setlocal
set "HERE=%~dp0"
set "CAMPAIGN=%~1"
if "%CAMPAIGN%"=="" set "CAMPAIGN=standard"
if not "%~1"=="" shift
python "%HERE%levelupdiag.py" run "%CAMPAIGN%" %*
exit /b %ERRORLEVEL%

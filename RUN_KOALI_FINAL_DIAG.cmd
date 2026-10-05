@echo off
setlocal
set "HERE=%~dp0"
python "%HERE%levelupdiag.py" run koali-final
exit /b %ERRORLEVEL%

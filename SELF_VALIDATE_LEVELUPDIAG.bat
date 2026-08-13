@echo off
setlocal EnableExtensions

title LevelUpDiag-Koali - Self Validation

rem Toujours travailler depuis le dossier ou se trouve ce .bat
cd /d "%~dp0"

echo ============================================================
echo   LevelUpDiag-Koali - SELF VALIDATION
echo ============================================================
echo.
echo Dossier : %CD%
echo.

rem Verifier que le script principal existe
if not exist "scripts\self_validate.py" (
    echo [ERREUR] Fichier introuvable :
    echo         %CD%\scripts\self_validate.py
    echo.
    set "RC=10"
    goto :END
)

rem Choisir Python
where py >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=py -3"
    goto :PYTHON_FOUND
)

where python >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=python"
    goto :PYTHON_FOUND
)

echo [ERREUR] Python est introuvable.
echo Installe Python 3.11 ou plus recent et assure-toi que
echo "py" ou "python" est accessible dans le PATH.
echo.
set "RC=11"
goto :END

:PYTHON_FOUND
echo Python utilise :
%PY_CMD% --version
if errorlevel 1 (
    echo.
    echo [ERREUR] Impossible de lancer Python.
    set "RC=12"
    goto :END
)

echo.
echo Verification de pytest :
%PY_CMD% -m pytest --version
if errorlevel 1 (
    echo.
    echo [ERREUR] pytest n'est pas disponible pour ce Python.
    echo Tu peux l'installer avec :
    echo   %PY_CMD% -m pip install "pytest>=8"
    echo.
    set "RC=13"
    goto :END
)

echo.
echo ------------------------------------------------------------
echo Lancement de scripts\self_validate.py
echo ------------------------------------------------------------
echo.

%PY_CMD% "scripts\self_validate.py" %*
set "RC=%ERRORLEVEL%"

:END
echo.
echo ============================================================
if "%RC%"=="0" (
    echo   SELF VALIDATION TERMINEE : PASS
) else (
    echo   SELF VALIDATION TERMINEE : ECHEC
)
echo   Code de sortie : %RC%
echo ============================================================
echo.
echo Appuie sur une touche pour fermer cette fenetre.
pause >nul

exit /b %RC%

@echo off
REM Recrea el caso real: el robot se desestabiliza en el ascensor.
REM El simulador tiene que estar abierto (INICIAR_SIMULADOR).
cd /d "%~dp0"

echo ============================================================
echo    Caso real: robot en el ascensor
echo ============================================================
echo.
echo    El simulador tiene que estar abierto.
echo.
echo      1)  SIN proteccion  - se desestabiliza (el fallo)
echo      2)  MODO SEGURO     - congela el equilibrio y no se cae
echo.
set OPCION=2
set /p OPCION="   Elegi 1 o 2 [2]: "
echo.

set "PYTHON="
set "PYARGS="
py -3 -c "import sys" >nul 2>&1 && set "PYTHON=py" && set "PYARGS=-3"
if not defined PYTHON set "PYTHON=python"

if "%OPCION%"=="2" (
  "%PYTHON%" %PYARGS% mi_desarrollo\demo_ascensor.py --seguro
) else (
  "%PYTHON%" %PYARGS% mi_desarrollo\demo_ascensor.py
)
echo.
pause

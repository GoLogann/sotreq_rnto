@echo off
title SOTREQ RNTO - Sistema de Relatorios
color 0A

echo ========================================
echo   SOTREQ RNTO - Inicializando...
echo ========================================
echo.

cd /d "%~dp0"

REM Verifica se as dependencias ja foram instaladas
if not exist "app\venv\" (
    echo [1/3] Instalando dependencias pela primeira vez...
    echo Isso pode levar alguns minutos...
    echo.
    
    python\python.exe -m pip install --upgrade pip --quiet
    python\python.exe -m pip install -r app\requirements.txt --target app\libs --quiet
    
    echo.
    echo [OK] Dependencias instaladas!
    echo.
)

echo [2/3] Iniciando servidor...
cd app
set PYTHONPATH=%CD%\libs;%PYTHONPATH%
..\python\python.exe app.py

pause
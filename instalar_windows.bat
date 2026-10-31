@echo off
rem Instalacao da Biblioteca Pre Universitario no Windows 10. Rode uma vez (duplo clique).
rem Para abrir sozinha ao entrar no Windows:  instalar_windows.bat /autostart
setlocal
cd /d "%~dp0"
echo.
echo === Biblioteca Pre Universitario: instalacao no Windows ===
echo.

set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY python --version >nul 2>&1 && set "PY=python"
if not defined PY (
  echo Python nao encontrado. Tentando instalar com o winget ^(pode demorar^)...
  winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
  py -3 --version >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
  echo.
  echo Nao consegui instalar o Python sozinho.
  echo Vou abrir a pagina de download. Instale MARCANDO a opcao "Add python.exe to PATH"
  echo e depois de dois cliques neste arquivo de novo.
  start https://www.python.org/downloads/windows/
  pause
  exit /b 1
)

echo [1/3] Preparando o ambiente do programa...
if not exist venv\Scripts\python.exe %PY% -m venv venv
if errorlevel 1 goto erro
echo [2/3] Instalando os componentes ^(precisa de internet^)...
venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto erro

echo [3/3] Criando os icones na area de trabalho e no menu Iniciar...
set "AUTO="
if /i "%~1"=="/autostart" set "AUTO=-IniciarComOPc"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar_atalhos.ps1" %AUTO%
if errorlevel 1 goto erro

echo.
echo Pronto! Abra pelo icone "Biblioteca Pre Universitario" na area de trabalho.
echo ^(O icone laranja "TESTE" abre com dados de exemplo, sem mexer nos dados reais.^)
echo.
pause
exit /b 0

:erro
echo.
echo Algo deu errado. Confira se ha internet e rode este arquivo de novo.
echo Se o erro continuar, tire uma foto desta tela e envie para quem cuida do sistema.
pause
exit /b 1

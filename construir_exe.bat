@echo off
rem OPCIONAL: cria um programa "Biblioteca.exe" que NAO precisa de Python no computador onde for usado.
rem Rode no Windows, com internet, depois de instalar_windows.bat. O resultado fica em dist\Biblioteca\
cd /d "%~dp0"
if not exist venv\Scripts\python.exe (
  echo Rode instalar_windows.bat antes.
  pause
  exit /b 1
)
venv\Scripts\python.exe -m pip install pyinstaller
if errorlevel 1 goto erro
set "EXTRA="
if exist biblioteca\static set "EXTRA=--add-data biblioteca\static;biblioteca\static"
venv\Scripts\pyinstaller.exe --noconfirm --clean --windowed --name Biblioteca --icon icone.ico ^
  --add-data "biblioteca\templates;biblioteca\templates" %EXTRA% --hidden-import waitress.server programa.py
if errorlevel 1 goto erro
xcopy /e /i /y dados_teste dist\Biblioteca\dados_teste >nul
copy /y icone.ico dist\Biblioteca\ >nul
copy /y icone_teste.ico dist\Biblioteca\ >nul
copy /y iniciar_teste_exe.bat dist\Biblioteca\iniciar_teste.bat >nul
copy /y instalar_atalhos.ps1 dist\Biblioteca\ >nul
echo.
echo Pronto! Copie a pasta dist\Biblioteca para o computador da escola e, dentro dela, rode:
echo   powershell -ExecutionPolicy Bypass -File instalar_atalhos.ps1
echo para criar os icones. Os dados ficam na pasta "dados" ao lado do Biblioteca.exe.
pause
exit /b 0
:erro
echo Algo deu errado ao criar o programa.
pause
exit /b 1

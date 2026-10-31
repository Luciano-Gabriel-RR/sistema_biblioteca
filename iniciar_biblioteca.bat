@echo off
rem Abre a biblioteca como programa (Windows). Na primeira vez, prepara o ambiente sozinho.
cd /d "%~dp0"
if not exist venv\Scripts\pythonw.exe (
  py -3 -m venv venv
)
venv\Scripts\python.exe -c "import flask, waitress" 2>nul || venv\Scripts\python.exe -m pip install -r requirements.txt
if /i "%BIBLIOTECA_DADOS%"=="%~dp0dados_teste" if not exist dados_teste\biblioteca.db venv\Scripts\python.exe dados_teste.py
start "" venv\Scripts\pythonw.exe programa.py

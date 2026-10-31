@echo off
rem Abre a biblioteca com os DADOS DE TESTE (nao mexe nos dados reais).
cd /d "%~dp0"
set "BIBLIOTECA_DADOS=%~dp0dados_teste"
set "BIBLIOTECA_NOME=Biblioteca Pre Universitario (TESTE)"
call iniciar_biblioteca.bat

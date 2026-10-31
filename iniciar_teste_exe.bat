@echo off
rem Abre o Biblioteca.exe com os DADOS DE TESTE (nao mexe nos dados reais).
cd /d "%~dp0"
set "BIBLIOTECA_DADOS=%~dp0dados_teste"
set "BIBLIOTECA_NOME=Biblioteca Pre Universitario (TESTE)"
start "" "%~dp0Biblioteca.exe"

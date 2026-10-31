#!/bin/bash
# Abre a biblioteca com os DADOS DE TESTE (não mexe nos dados reais).
cd "$(dirname "$(readlink -f "$0")")" || exit 1
export BIBLIOTECA_DADOS="$PWD/dados_teste"
export BIBLIOTECA_NOME="Biblioteca Pré Universitário (TESTE)"
exec bash iniciar_biblioteca.sh "$@"

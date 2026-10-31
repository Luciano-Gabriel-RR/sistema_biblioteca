#!/bin/bash
# Abre a biblioteca como programa. Na primeira vez, prepara o ambiente sozinho.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
if [ ! -x venv/bin/python ]; then
  python3 -m venv --system-site-packages venv || { echo "Instale antes: sudo apt install python3-venv"; exit 1; }
fi
# o ambiente precisa enxergar os componentes da janela instalados pelo sistema (instalar.sh)
[ -f venv/pyvenv.cfg ] && sed -i 's/^include-system-site-packages *= *false/include-system-site-packages = true/' venv/pyvenv.cfg
venv/bin/python -c "import flask, waitress" 2>/dev/null || venv/bin/python -m pip install -r requirements.txt
venv/bin/python -c "import webview" 2>/dev/null || venv/bin/python -m pip install -q -r requirements-janela.txt >/dev/null 2>&1
if [ "${BIBLIOTECA_DADOS:-}" = "$PWD/dados_teste" ] && [ ! -f dados_teste/biblioteca.db ]; then
  venv/bin/python dados_teste.py   # cria o banco de exemplo
fi
exec venv/bin/python programa.py "$@"

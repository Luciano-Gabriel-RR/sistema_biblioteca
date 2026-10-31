#!/bin/bash
# Instala tudo para a biblioteca abrir como PROGRAMA (janela própria, sem navegador). Rode uma vez:
#     bash instalar.sh
# Para ela abrir sozinha quando você entrar no computador:
#     bash instalar.sh --iniciar-com-o-pc
cd "$(dirname "$(readlink -f "$0")")" || exit 1

echo "1/4  Instalando os componentes da janela (vai pedir a sua senha)..."
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y python3-venv python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1 \
    || sudo apt-get install -y python3-venv python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.0 \
    || echo "Aviso: não consegui instalar os componentes da janela; vou tentar outro jeito."
else
  echo "Este computador não usa apt; pulando esta etapa."
fi

echo "2/4  Preparando o ambiente do programa..."
if [ ! -x venv/bin/python ]; then
  python3 -m venv --system-site-packages venv || { echo "Não consegui criar o ambiente. Instale: sudo apt install python3-venv"; exit 1; }
elif [ -f venv/pyvenv.cfg ]; then
  # o ambiente precisa enxergar os componentes da janela instalados no passo 1
  sed -i 's/^include-system-site-packages *= *false/include-system-site-packages = true/' venv/pyvenv.cfg
fi
venv/bin/python -m pip install -r requirements.txt -r requirements-janela.txt || { echo "Falhou ao instalar os pacotes (sem internet?)."; exit 1; }

echo "3/4  Testando a janela nativa..."
if venv/bin/python - <<'PY'
import gi
gi.require_version("Gtk", "3.0")
try:
    gi.require_version("WebKit2", "4.1")
except ValueError:
    gi.require_version("WebKit2", "4.0")
from gi.repository import Gtk, WebKit2
PY
then
  echo "     Janela nativa pronta (GTK)."
else
  echo "     GTK indisponível. Tentando a alternativa Qt (baixa uns 100 MB)..."
  venv/bin/python -m pip install "pywebview[qt]" && echo "     Janela nativa pronta (Qt)." \
    || echo "     Não deu certo. O programa vai usar o Chrome/Chromium, se houver, ou o navegador comum."
fi

echo "4/4  Criando o ícone do programa..."
bash instalar_atalho.sh "$@"
echo
echo "Pronto! Abra pelo ícone 'Biblioteca Pré Universitário' ou rode:  bash iniciar_biblioteca.sh"

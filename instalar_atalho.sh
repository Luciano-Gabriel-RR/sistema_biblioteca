#!/bin/bash
# Cria o ícone "Biblioteca Pré Universitário" no menu de aplicativos e na área de trabalho (Linux).
cd "$(dirname "$(readlink -f "$0")")" || exit 1
DIR="$(pwd)"
chmod +x iniciar_biblioteca.sh
ARQ="$HOME/.local/share/applications/biblioteca-pre-universitario.desktop"
mkdir -p "$(dirname "$ARQ")"
cat > "$ARQ" <<FIM
[Desktop Entry]
Type=Application
Name=Biblioteca Pré Universitário
Comment=Sistema de biblioteca da escola
Exec="$DIR/iniciar_biblioteca.sh"
Path=$DIR
Icon=$DIR/icone.svg
Terminal=false
Categories=Education;Office;
FIM
chmod +x "$ARQ"
DESK="$(xdg-user-dir DESKTOP 2>/dev/null)"
if [ -d "$DESK" ]; then
  cp "$ARQ" "$DESK/"
  chmod +x "$DESK/biblioteca-pre-universitario.desktop"
  gio set "$DESK/biblioteca-pre-universitario.desktop" metadata::trusted true 2>/dev/null
fi
# Segundo atalho: o mesmo sistema com os dados de exemplo (ícone laranja, "(TESTE)" no nome)
chmod +x iniciar_teste.sh
ARQT="$HOME/.local/share/applications/biblioteca-pre-universitario-teste.desktop"
cat > "$ARQT" <<FIM
[Desktop Entry]
Type=Application
Name=Biblioteca Pré Universitário (TESTE)
Comment=Mesmo sistema, com dados de exemplo (não mexe nos dados reais)
Exec="$DIR/iniciar_teste.sh"
Path=$DIR
Icon=$DIR/icone_teste.svg
Terminal=false
Categories=Education;Office;
FIM
chmod +x "$ARQT"
if [ -d "$DESK" ]; then
  cp "$ARQT" "$DESK/"
  chmod +x "$DESK/biblioteca-pre-universitario-teste.desktop"
  gio set "$DESK/biblioteca-pre-universitario-teste.desktop" metadata::trusted true 2>/dev/null
fi
if [ "${1:-}" = "--iniciar-com-o-pc" ]; then
  mkdir -p "$HOME/.config/autostart"
  cp "$ARQ" "$HOME/.config/autostart/"
  echo "A biblioteca vai abrir sozinha quando você entrar no computador."
  echo "(Para desfazer, apague: ~/.config/autostart/biblioteca-pre-universitario.desktop)"
fi
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null
echo "Pronto! Foram criados dois ícones, no menu de aplicativos e na área de trabalho:"
echo "  - Biblioteca Pré Universitário          (dados reais)"
echo "  - Biblioteca Pré Universitário (TESTE)  (dados de exemplo)"
echo "(Se o ícone da área de trabalho aparecer sem cor, clique com o botão direito e escolha 'Permitir execução'.)"

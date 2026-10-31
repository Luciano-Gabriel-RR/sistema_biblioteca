"""Gera PALETA.md a partir dos valores de paleta.py (rode: python3 estudo_cores/gerar_doc.py)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paleta import CLARO as C, ESCURO as E, razao, matiz

def r(a, b, p): return f"{razao(p[a], p[b]):.1f} : 1"
papeis = [("Fundo da página", "papel", None), ("Cartões e campos", "ficha", None), ("Menu e cabeçalhos", "realce", None),
          ("Texto principal", "tinta", "ficha"), ("Texto de apoio", "tinta2", "ficha"), ("Legendas", "tinta3", "ficha"),
          ("Primária (petróleo): ações e navegação", "primaria", "ficha"),
          ("Sucesso (verde): em dia, disponível, devolvido", "sucesso", "ficha"),
          ("Atraso e erro (tijolo)", "perigo", "ficha"), ("Aviso (âmbar): vence em breve", "aviso", "ficha"),
          ("Reservas e fila (violeta)", "info", "ficha"), ("Acervo (ameixa)", "acervo", "ficha"),
          ("Decorativo (ouro): marcadores", "destaque", "ficha")]
L = ["# Paleta do sistema da biblioteca", "",
     "Este é o estudo de cores. Os valores em `biblioteca/templates/base.html` seguem esta tabela. "
     "Para mudar uma cor: altere `estudo_cores/paleta.py`, rode `python3 estudo_cores/paleta.py` (mede os contrastes) "
     "e depois `python3 estudo_cores/gerar_doc.py` (atualiza este documento).", "",
     "## Princípios", "",
     "- **Uma cor, uma função.** O vermelho aparece só em atraso ou erro; o verde, só para o que está em dia, disponível ou devolvido.",
     "- **Matizes separados.** As funções ocupam regiões distantes do círculo de cores: petróleo " + f"{matiz(C['primaria'])}°, verde {matiz(C['sucesso'])}°, violeta {matiz(C['info'])}°, tijolo {matiz(C['perigo'])}°, âmbar {matiz(C['aviso'])}°, ameixa {matiz(C['acervo'])}°" + ". O ouro (" + f"{matiz(C['destaque'])}°" + ") é só decorativo e nunca aparece em texto.",
     "- **Neutros frios e grafite.** Claro: papel levemente frio. Escuro: grafite-azulado pouco saturado, para que as cores de função se destaquem.",
     "- **Contraste medido.** Textos principais ≥ 7:1; demais textos ≥ 4,5:1 (WCAG AA); bordas e marcadores ≥ 3:1.",
     "- **A cor nunca é o único sinal.** Atraso tem texto (\"22 dias de atraso\"), não só vermelho.", "",
     "## Papéis e valores", "",
     "| Papel | Claro | Escuro | Contraste claro | Contraste escuro |", "|---|---|---|---|---|"]
for nome, k, sobre in papeis:
    if sobre is None:
        L.append(f"| {nome} | `{C[k]}` | `{E[k]}` | — | — |")
    else:
        L.append(f"| {nome} | `{C[k]}` | `{E[k]}` | {r(k, sobre, C)} sobre o cartão | {r(k, sobre, E)} sobre o cartão |")
L += ["", f"Bordas de cartões e campos: claro `{C['borda']}` ({razao(C['borda'], C['ficha']):.1f} : 1), escuro `{E['borda']}` ({razao(E['borda'], E['ficha']):.1f} : 1).", "",
      "## Textos sobre cores de estado (selos e botões)", "",
      "| Uso | Texto | Fundo | Contraste claro | Contraste escuro |", "|---|---|---|---|---|"]
for nome, a, b in [("Selo de sucesso", "sucesso", "sucesso_f"), ("Selo de atraso", "perigo", "perigo_f"),
                   ("Selo de aviso", "aviso", "aviso_f"), ("Selo de reserva", "info", "info_f"),
                   ("Botão principal", "texto_botao", "primaria"), ("Botão de devolver", "texto_botao", "sucesso"),
                   ("Botão de atraso", "texto_botao", "perigo"), ("Botão de aviso", "texto_destaque", "destaque_claro")]:
    L.append(f"| {nome} | `{C[a]}` / `{E[a]}` | `{C[b]}` / `{E[b]}` | {razao(C[a], C[b]):.1f} : 1 | {razao(E[a], E[b]):.1f} : 1 |")
L += ["", "## Matiz (graus HSL)", "", "| Função | Claro | Escuro |", "|---|---|---|"]
for k in ["primaria", "sucesso", "info", "perigo", "aviso", "acervo", "destaque"]:
    L.append(f"| {k} | {matiz(C[k])}° | {matiz(E[k])}° |")
L += ["", "## Como aplicar", "",
      "- Ações principais e navegação: `primaria` (botão, item ativo, marcas).",
      "- Estados de linha e selo: `sucesso`, `perigo`, `aviso`, `info`.",
      "- Indicadores do painel: cada um tem a cor da sua função (empréstimos = petróleo, atrasados = tijolo, reservas e fila = violeta, acervo = ameixa, cadastros = verde).",
      "- `destaque` (ouro) só em marcadores decorativos. Não use para texto."]
caminho = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "PALETA.md")
open(caminho, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("PALETA.md atualizado:", caminho)

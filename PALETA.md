# Paleta do sistema da biblioteca

Este é o estudo de cores. Os valores em `biblioteca/templates/base.html` seguem esta tabela. Para mudar uma cor: altere `estudo_cores/paleta.py`, rode `python3 estudo_cores/paleta.py` (mede os contrastes) e depois `python3 estudo_cores/gerar_doc.py` (atualiza este documento).

## Princípios

- **Uma cor, uma função.** O vermelho aparece só em atraso ou erro; o verde, só para o que está em dia, disponível ou devolvido.
- **Matizes separados.** As funções ocupam regiões distantes do círculo de cores: petróleo 191°, verde 139°, violeta 251°, tijolo 5°, âmbar 30°, ameixa 324°. O ouro (46°) é só decorativo e nunca aparece em texto.
- **Neutros frios e grafite.** Claro: papel levemente frio. Escuro: grafite-azulado pouco saturado, para que as cores de função se destaquem.
- **Contraste medido.** Textos principais ≥ 7:1; demais textos ≥ 4,5:1 (WCAG AA); bordas e marcadores ≥ 3:1.
- **A cor nunca é o único sinal.** Atraso tem texto ("22 dias de atraso"), não só vermelho.

## Papéis e valores

| Papel | Claro | Escuro | Contraste claro | Contraste escuro |
|---|---|---|---|---|
| Fundo da página | `#F2F0EA` | `#0F1417` | — | — |
| Cartões e campos | `#FDFCF8` | `#182025` | — | — |
| Menu e cabeçalhos | `#E8ECEA` | `#1F2A31` | — | — |
| Texto principal | `#1C2A2E` | `#EDF3F0` | 14.4 : 1 sobre o cartão | 14.7 : 1 sobre o cartão |
| Texto de apoio | `#41525A` | `#B9CAC8` | 7.9 : 1 sobre o cartão | 9.7 : 1 sobre o cartão |
| Legendas | `#56666C` | `#9AB0AE` | 5.8 : 1 sobre o cartão | 7.2 : 1 sobre o cartão |
| Primária (petróleo): ações e navegação | `#1E5F6E` | `#78C7D6` | 7.0 : 1 sobre o cartão | 8.6 : 1 sobre o cartão |
| Sucesso (verde): em dia, disponível, devolvido | `#276B3C` | `#9BD3A2` | 6.3 : 1 sobre o cartão | 9.6 : 1 sobre o cartão |
| Atraso e erro (tijolo) | `#B3352A` | `#F2897B` | 5.9 : 1 sobre o cartão | 6.8 : 1 sobre o cartão |
| Aviso (âmbar): vence em breve | `#9A5610` | `#F2B56B` | 5.5 : 1 sobre o cartão | 9.1 : 1 sobre o cartão |
| Reservas e fila (violeta) | `#5A4B9C` | `#B7AEF2` | 7.0 : 1 sobre o cartão | 8.1 : 1 sobre o cartão |
| Acervo (ameixa) | `#8A3D6B` | `#E9A6D2` | 6.9 : 1 sobre o cartão | 8.5 : 1 sobre o cartão |
| Decorativo (ouro): marcadores | `#A88512` | `#E6C15E` | 3.4 : 1 sobre o cartão | 9.6 : 1 sobre o cartão |

Bordas de cartões e campos: claro `#78867F` (3.7 : 1), escuro `#5E727A` (3.3 : 1).

## Textos sobre cores de estado (selos e botões)

| Uso | Texto | Fundo | Contraste claro | Contraste escuro |
|---|---|---|---|---|
| Selo de sucesso | `#276B3C` / `#9BD3A2` | `#DDF1E1` / `#1B3A25` | 5.5 : 1 | 7.3 : 1 |
| Selo de atraso | `#B3352A` / `#F2897B` | `#FBE2DC` / `#43231F` | 4.9 : 1 | 5.8 : 1 |
| Selo de aviso | `#9A5610` / `#F2B56B` | `#FBEDC8` / `#3F3316` | 4.9 : 1 | 6.8 : 1 |
| Selo de reserva | `#5A4B9C` / `#B7AEF2` | `#E7E3F7` / `#29244A` | 5.7 : 1 | 7.2 : 1 |
| Botão principal | `#FFFFFF` / `#0B161A` | `#1E5F6E` / `#78C7D6` | 7.2 : 1 | 9.6 : 1 |
| Botão de devolver | `#FFFFFF` / `#0B161A` | `#276B3C` / `#9BD3A2` | 6.5 : 1 | 10.7 : 1 |
| Botão de atraso | `#FFFFFF` / `#0B161A` | `#B3352A` / `#F2897B` | 6.1 : 1 | 7.6 : 1 |
| Botão de aviso | `#1C1A12` / `#1E1608` | `#E9BE62` / `#EBC67F` | 10.0 : 1 | 11.0 : 1 |

## Matiz (graus HSL)

| Função | Claro | Escuro |
|---|---|---|
| primaria | 191° | 190° |
| sucesso | 139° | 128° |
| info | 251° | 248° |
| perigo | 5° | 7° |
| aviso | 30° | 33° |
| acervo | 324° | 321° |
| destaque | 46° | 44° |

## Como aplicar

- Ações principais e navegação: `primaria` (botão, item ativo, marcas).
- Estados de linha e selo: `sucesso`, `perigo`, `aviso`, `info`.
- Indicadores do painel: cada um tem a cor da sua função (empréstimos = petróleo, atrasados = tijolo, reservas e fila = violeta, acervo = ameixa, cadastros = verde).
- `destaque` (ouro) só em marcadores decorativos. Não use para texto.

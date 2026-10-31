"""Estudo de cores do sistema: papéis, valores e verificação de contraste (WCAG 2.1)."""
import colorsys

def lum(h):
    h = h.lstrip('#'); r, g, b = [int(h[i:i+2], 16)/255 for i in (0, 2, 4)]
    f = lambda c: c/12.92 if c <= 0.03928 else ((c+0.055)/1.055)**2.4
    return 0.2126*f(r) + 0.7152*f(g) + 0.0722*f(b)

def razao(a, b):
    la, lb = sorted([lum(a), lum(b)], reverse=True)
    return (la+0.05)/(lb+0.05)

def rgb(h):
    h = h.lstrip('#'); return ",".join(str(int(h[i:i+2], 16)) for i in (0, 2, 4))

def matiz(h):
    h = h.lstrip('#'); r, g, b = [int(h[i:i+2], 16)/255 for i in (0, 2, 4)]
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b); return round(hh*360)

CLARO = dict(
    papel="#F2F0EA", ficha="#FDFCF8", realce="#E8ECEA", linha="#DCE1DE", borda="#78867F",
    tinta="#1C2A2E", tinta2="#41525A", tinta3="#56666C",
    primaria="#1E5F6E", primaria_esc="#15464F", primaria_f="#DCEEF0",
    destaque="#A88512", destaque_claro="#E9BE62", texto_destaque="#1C1A12",
    sucesso="#276B3C", sucesso_f="#DDF1E1",
    perigo="#B3352A", perigo_f="#FBE2DC",
    aviso="#9A5610", aviso_f="#FBEDC8",
    info="#5A4B9C", info_f="#E7E3F7", acervo="#8A3D6B",
    texto_botao="#FFFFFF", foco="rgba(30,95,110,.38)",
)
ESCURO = dict(
    papel="#0F1417", ficha="#182025", realce="#1F2A31", linha="#2A373E", borda="#5E727A",
    tinta="#EDF3F0", tinta2="#B9CAC8", tinta3="#9AB0AE",
    primaria="#78C7D6", primaria_esc="#A6DCE6", primaria_f="#173B43",
    destaque="#E6C15E", destaque_claro="#EBC67F", texto_destaque="#1E1608",
    sucesso="#9BD3A2", sucesso_f="#1B3A25",
    perigo="#F2897B", perigo_f="#43231F",
    aviso="#F2B56B", aviso_f="#3F3316",
    info="#B7AEF2", info_f="#29244A", acervo="#E9A6D2",
    texto_botao="#0B161A", foco="rgba(120,199,214,.42)",
)

# (texto, fundo, mínimo)  — texto precisa de 4.5; títulos grandes e textos principais, 7
TEXTO = [("tinta","ficha",7),("tinta","papel",7),("tinta","realce",7),("tinta2","ficha",7),("tinta2","papel",7),
         ("tinta3","ficha",4.5),("tinta3","papel",4.5),("primaria","ficha",4.5),("primaria","realce",4.5),
         ("sucesso","ficha",4.5),("sucesso","sucesso_f",4.5),("perigo","ficha",4.5),("perigo","perigo_f",4.5),
         ("aviso","aviso_f",4.5),("aviso","ficha",4.5),("info","ficha",4.5),("info","info_f",4.5),
         ("texto_botao","primaria",4.5),("texto_botao","sucesso",4.5),("texto_botao","perigo",4.5),
         ("texto_destaque","destaque_claro",4.5)]
# componentes gráficos (bordas, marcadores, faixas): 3
UI = [("acervo","ficha",3),("borda","ficha",3),("borda","papel",3),("primaria","ficha",3),("destaque","ficha",3),
      ("sucesso","ficha",3),("perigo","ficha",3),("aviso","ficha",3),("info","ficha",3)]

def auditar(p, nome):
    falhas = 0; linhas = []
    for a, b, m in TEXTO:
        r = razao(p[a], p[b]); ok = r >= m; falhas += not ok
        linhas.append((f"texto {a} / {b}", round(r, 2), m, ok))
    for a, b, m in UI:
        r = razao(p[a], p[b]); ok = r >= m; falhas += not ok
        linhas.append((f"gráfico {a} / {b}", round(r, 2), m, ok))
    print(f"== {nome}: {'todos passam' if not falhas else str(falhas)+' FALHAS'}")
    for n, r, m, ok in linhas:
        if not ok or "--v" in __import__("sys").argv: print(f"   {'OK   ' if ok else 'FALHA'} {n:<32} {r:>5}  (mín {m})")
    return falhas, linhas

if __name__ == "__main__":
    f1, l1 = auditar(CLARO, "CLARO")
    f2, l2 = auditar(ESCURO, "ESCURO")
    print("\nMatiz (graus HSL) — separação entre funções:")
    for nome in ["primaria","sucesso","info","perigo","destaque","aviso","acervo"]:
        print(f"   {nome:<10} claro {matiz(CLARO[nome]):>3}°   escuro {matiz(ESCURO[nome]):>3}°")
    import sys; sys.exit(1 if (f1 or f2) else 0)

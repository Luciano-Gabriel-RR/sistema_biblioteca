"""Camada web: recebe o pedido HTTP, chama os serviços e devolve a página."""
from datetime import datetime

import csv
import io
import os
import threading
import time

from flask import (Blueprint, Response, abort, current_app, flash, redirect, render_template, request,
                   send_from_directory, session, url_for)

from . import services as srv

bp = Blueprint("main", __name__)


def _executar(funcao, mensagem, *args, **kwargs):
    """Roda uma ação de negócio e avisa o usuário do resultado. Devolve True se deu certo."""
    try:
        resultado = funcao(*args, **kwargs)
    except srv.ErroNegocio as erro:
        flash(str(erro), "danger")
        return False
    flash(mensagem.format(resultado), "success")
    return True


def _turma(f):
    """Junta série e letra do formulário: ("9º ano", "b") -> "9º ano b" (o serviço padroniza)."""
    return f"{f.get('serie', '').strip()} {f.get('letra', '').strip()}".strip()


def _voltar(aba, **consulta):
    return redirect(url_for("main.index", **consulta) + f"#{aba}")


def _apos_acao(aba, **consulta):
    """Depois de uma ação: volta ao balcão se ela veio de lá (campo 'voltar'); senão, à aba."""
    if request.form.get("voltar") == "balcao":
        pessoa = request.form.get("pessoa_id", "")
        return redirect(url_for("main.balcao", pessoa=pessoa) if pessoa.isdigit() else url_for("main.balcao"))
    return _voltar(aba, **consulta)


@bp.get("/")
def index():
    q = request.args.get("q", "").strip()
    busca = request.args.get("busca", "").strip()
    srv.expirar_reservas()
    pag = lambda chave: request.args.get(chave, 1, type=int)  # página de cada lista
    h = request.args.get("h", "").strip()
    qp = request.args.get("qp", "").strip()
    qs = request.args.get("qs", "").strip()    # busca nas sugestões
    ss = request.args.get("ss", "").strip()    # filtro de situação das sugestões
    return render_template(
        "index.html", q=q, busca=busca, h=h,
        autores=srv.buscar_autores(q, pag("pa")), todos_autores=srv.nomes_autores(),
        livros=srv.buscar_livros(busca, pag("pl")), todos_livros=srv.buscar_livros(),
        usuarios=srv.listar_pessoas(), pessoas=srv.listar_pessoas(pag("pp"), qp), qp=qp,
        emprestimos=srv.emprestimos_ativos(), historico=srv.historico(h, pag("ph")),
        reservas=srv.reservas_abertas(), painel=srv.painel(), ranking=srv.ranking(),
        sugestoes=srv.listar_sugestoes(qs, ss, pag("ps")), qs=qs, ss=ss,
        mais_sugeridos=srv.mais_sugeridos(), generos=srv.generos_mais_lidos(), generos_lista=srv.GENEROS,
        ultimo_genero=session.get("ultimo_genero", ""),
        rascunho_livro=session.pop("rascunho_livro", {}), rascunho_pessoa=session.pop("rascunho_pessoa", {}),
        rascunho_sugestao=session.pop("rascunho_sugestao", {}), aviso_backup=srv.dias_desde_backup(),
        dias_alerta=current_app.config["DIAS_ALERTA_BACKUP"],
        ultimo_autor=session.get("ultimo_autor", ""), ultima_serie=session.get("ultima_serie", ""),
        ultima_letra=session.get("ultima_letra", ""), series=srv.SERIES, letras=srv.LETRAS,
        turmas_ativas=srv.turmas_ativas(),
        hoje=datetime.now().strftime("%Y-%m-%d"), prazos=current_app.config["PRAZOS"],
    )


# ----- Balcão de atendimento -----
@bp.get("/balcao")
def balcao():
    srv.expirar_reservas()
    qp = request.args.get("qp", "").strip()          # busca de pessoa
    lb = request.args.get("lb", "").strip()          # busca de livro
    pessoa = None
    pid = request.args.get("pessoa", type=int)
    if pid:
        try:
            pessoa = srv.obter_pessoa(pid)
        except srv.ErroNegocio:
            flash("Cadastro não encontrado.", "danger")
    encontradas = srv.listar_pessoas(None, qp)[:12] if qp else []
    emprestimos, reservas, livros, reservaveis = [], [], [], []
    if pessoa is not None:
        emprestimos = srv.emprestimos_da_pessoa(pessoa["id"])
        reservas = [r for r in srv.reservas_abertas() if r["usuario_id"] == pessoa["id"]]
        achados = srv.buscar_livros(lb)
        livros = [l for l in achados if l["quantidade_disponivel"] > 0][:20]
        reservaveis = [l for l in achados if l["quantidade_disponivel"] == 0][:20]
    return render_template(
        "balcao.html", qp=qp, lb=lb, encontradas=encontradas, pessoa=pessoa,
        emprestimos=emprestimos, reservas=reservas, livros=livros, reservaveis=reservaveis,
        atrasados=[e for e in emprestimos if e["dias_restantes"] is not None and e["dias_restantes"] < 0],
        prazos=current_app.config["PRAZOS"],
    )


# ----- Livros -----
@bp.post("/livros")
def add_livro():
    f = request.form
    if _executar(srv.salvar_livro, "{}", f.get("titulo"), f.get("isbn"),
                 f.get("autor"), f.get("quantidade"), observacao=f.get("observacao", ""),
                 genero=f.get("genero", "")):
        session["ultimo_autor"] = f.get("autor", "").strip()  # facilita cadastrar vários livros do mesmo autor
        session["ultimo_genero"] = f.get("genero", "")        # e do mesmo gênero
        return _voltar("livros", novo="livro")
    session["rascunho_livro"] = {c: f.get(c, "") for c in ("titulo", "isbn", "quantidade", "autor", "observacao", "genero")}
    return _voltar("livros", novo="livro")


@bp.route("/livros/<int:livro_id>/editar", methods=["GET", "POST"])
def editar_livro(livro_id):
    if request.method == "POST":
        f = request.form
        if _executar(srv.salvar_livro, "Livro atualizado.", f.get("titulo"), f.get("isbn"), f.get("autor"),
                     f.get("quantidade"), livro_id=livro_id, observacao=f.get("observacao", ""),
                     genero=f.get("genero", "")):
            return _voltar("livros")
    try:
        livro = srv.obter_livro(livro_id)
    except srv.ErroNegocio as erro:
        flash(str(erro), "danger")
        return _voltar("livros")
    return render_template("editar_livro.html", livro=livro, todos_autores=srv.nomes_autores(),
                           baixas=srv.baixas_do_livro(livro_id), motivos=srv.MOTIVOS_BAIXA,
                           generos_lista=srv.GENEROS)


@bp.post("/livros/<int:livro_id>/baixa")
def baixa_livro(livro_id):
    _executar(srv.baixar_exemplar, "Baixa registrada.", livro_id, request.form.get("motivo"),
              request.form.get("observacao", ""))
    return redirect(url_for("main.editar_livro", livro_id=livro_id))


@bp.post("/livros/<int:livro_id>/excluir")
def excluir_livro(livro_id):
    _executar(srv.excluir_livro, "Livro excluído.", livro_id)
    return _voltar("livros")


# ----- Sugestões de livros novos -----
_CAMPOS_SUGESTAO = ("titulo", "autor", "isbn", "motivo", "sugerido_por")


@bp.post("/sugestoes")
def add_sugestao():
    f = request.form
    dados = [f.get(c, "") for c in _CAMPOS_SUGESTAO]
    if not _executar(srv.salvar_sugestao, "{}", *dados):
        session["rascunho_sugestao"] = dict(zip(_CAMPOS_SUGESTAO, dados))  # mantém o que foi digitado
    return _voltar("sugestoes", novo="sugestao")  # a janela volta aberta: dá para registrar várias seguidas


@bp.route("/sugestoes/<int:sugestao_id>/editar", methods=["GET", "POST"])
def editar_sugestao(sugestao_id):
    if request.method == "POST":
        dados = [request.form.get(c, "") for c in _CAMPOS_SUGESTAO]
        if _executar(srv.salvar_sugestao, "Sugestão atualizada.", *dados, sugestao_id=sugestao_id):
            return _voltar("sugestoes")
    try:
        sugestao = srv.obter_sugestao(sugestao_id)
    except srv.ErroNegocio as erro:
        flash(str(erro), "danger")
        return _voltar("sugestoes")
    return render_template("editar_sugestao.html", sugestao=sugestao)


@bp.post("/sugestoes/adquirir")
def adquirir_sugestoes():
    """Da aba "Mais sugeridos": marca como adquiridas todas as sugestões pendentes de um mesmo livro."""
    ids = request.form.get("ids", "").split(",")
    _executar(srv.adquirir_sugestoes, "{} pedido(s) marcado(s) como adquirido(s).", ids)
    return _voltar("maissugeridos")


@bp.post("/sugestoes/<int:sugestao_id>/situacao")
def alternar_sugestao(sugestao_id):
    _executar(srv.alternar_sugestao, "Sugestão marcada como {}.", sugestao_id)
    return _voltar("sugestoes")


@bp.post("/sugestoes/<int:sugestao_id>/excluir")
def excluir_sugestao(sugestao_id):
    _executar(srv.excluir_sugestao, "Sugestão excluída.", sugestao_id)
    return _voltar("sugestoes")


# ----- Alunos e professores -----
@bp.post("/pessoas")
def add_pessoa():
    f = request.form
    if _executar(srv.salvar_pessoa, f.get("tipo", "Cadastro") + " cadastrado com sucesso.", f.get("tipo"),
                 f.get("nome"), f.get("email"), _turma(f), f.get("disciplina"),
                 matricula=f.get("matricula", "")):
        session["ultima_serie"], session["ultima_letra"] = f.get("serie", ""), f.get("letra", "").strip()
        return _voltar("pessoas", novo="pessoa")
    session["rascunho_pessoa"] = {c: f.get(c, "") for c in ("tipo", "nome", "email", "matricula", "serie", "letra", "disciplina")}
    return _voltar("pessoas", novo="pessoa")


@bp.route("/pessoas/<int:pessoa_id>/editar", methods=["GET", "POST"])
def editar_pessoa(pessoa_id):
    if request.method == "POST":
        f = request.form
        if _executar(srv.salvar_pessoa, "Cadastro atualizado.", f.get("tipo"), f.get("nome"), f.get("email"),
                     _turma(f), f.get("disciplina"), pessoa_id=pessoa_id,
                     matricula=f.get("matricula", "")):
            return _voltar("pessoas")
    try:
        pessoa = srv.obter_pessoa(pessoa_id)
    except srv.ErroNegocio as erro:
        flash(str(erro), "danger")
        return _voltar("pessoas")
    serie, letra = srv.separar_turma(pessoa["turma"])
    return render_template("editar_pessoa.html", pessoa=pessoa, series=srv.SERIES, letras=srv.LETRAS,
                           serie_atual=serie, letra_atual=letra)


@bp.get("/pessoas/<int:pessoa_id>/leitura")
def leitura_pessoa(pessoa_id):
    try:
        leitura = srv.generos_da_pessoa(pessoa_id)
    except srv.ErroNegocio as erro:
        flash(str(erro), "danger")
        return _voltar("pessoas")
    return render_template("pessoa_leitura.html", leitura=leitura, pessoa=leitura["pessoa"])


@bp.post("/pessoas/<int:pessoa_id>/excluir")
def excluir_pessoa(pessoa_id):
    _executar(srv.excluir_pessoa, "Cadastro excluído.", pessoa_id)
    return _voltar("pessoas")


@bp.post("/pessoas/<int:pessoa_id>/alternar")
def alternar_pessoa(pessoa_id):
    _executar(srv.alternar_ativo, "Cadastro {}.", pessoa_id)
    return _voltar("pessoas")


# ----- Empréstimos -----
@bp.post("/emprestimos")
def emprestar():
    ok = _executar(srv.emprestar, "Empréstimo registrado. Devolução até {}.",
                   request.form.get("livro_id"), request.form.get("usuario_id"), request.form.get("observacao", ""))
    return _apos_acao("emprestimos", **({} if ok else {"novo": "emprestimo"}))  # erro: reabre a janela


@bp.post("/emprestimos/<int:emprestimo_id>/devolver")
def devolver(emprestimo_id):
    _executar(srv.devolver, "Livro devolvido.", emprestimo_id, request.form.get("observacao", ""),
              request.form.get("estado", "Bom"))
    return _apos_acao("emprestimos")


@bp.post("/emprestimos/<int:emprestimo_id>/renovar")
def renovar(emprestimo_id):
    _executar(srv.renovar, "Empréstimo renovado. Nova devolução até {}.", emprestimo_id)
    return _apos_acao("emprestimos")


@bp.get("/atrasados")
def atrasados():
    return render_template("atrasados.html", atrasados=srv.atrasados(),
                           hoje=datetime.now().strftime("%Y-%m-%d"))



# ----- Reservas -----
@bp.post("/reservas")
def reservar():
    ok = _executar(srv.reservar, "Reserva registrada.", request.form.get("livro_id"), request.form.get("usuario_id"))
    return _apos_acao("reservas", **({} if ok else {"novo": "reserva"}))  # erro: reabre a janela


@bp.post("/reservas/<int:reserva_id>/cancelar")
def cancelar_reserva(reserva_id):
    _executar(srv.cancelar_reserva, "Reserva cancelada.", reserva_id)
    return _apos_acao("reservas")


# ----- Virada de ano -----
@bp.route("/virada", methods=["GET", "POST"])
def virada():
    if request.method == "POST":
        pares = []
        for atual, para in zip(request.form.getlist("de"), request.form.getlist("para")):
            if para == "__manter__":
                continue
            letra = srv.separar_turma(atual)[1]  # a letra da turma é mantida
            pares.append((atual, f"{para} {letra}".strip() if para else ""))
        excecoes = {}  # decisões individuais: campos "aluno_<id>" = arquivar | manter
        for campo, valor in request.form.items():
            if campo.startswith("aluno_") and campo[6:].isdigit() and valor in srv.ACOES_ALUNO:
                excecoes[int(campo[6:])] = valor
        srv.fazer_backup()
        try:
            movidos, arquivados, pendentes = srv.virar_ano(pares, excecoes)
        except srv.ErroNegocio as erro:
            flash(str(erro), "danger")
            return redirect(url_for("main.virada"))
        flash(f"Virada concluída: {movidos} aluno(s) mudaram de turma e {arquivados} foram arquivados.", "success")
        if pendentes:
            flash("Não foram arquivados por terem livro emprestado: " + ", ".join(pendentes) + ". Eles continuam "
                  "na turma atual. Registre a devolução e arquive cada um em Alunos e professores.", "warning")
        return _voltar("pessoas")
    alunos = srv.alunos_por_turma()
    turmas = [{"turma": t["turma"], "total": t["total"], "sugestao": srv.sugerir_turma(t["turma"]),
               "alunos": alunos.get(t["turma"], [])} for t in srv.turmas_ativas()]
    return render_template("virada.html", turmas=turmas, series=srv.SERIES)


@bp.post("/emprestimos/<int:emprestimo_id>/baixa")
def baixa_emprestimo(emprestimo_id):
    _executar(srv.baixar_emprestimo, "Baixa registrada: o exemplar saiu do estoque.", emprestimo_id,
              request.form.get("observacao", ""))
    return _voltar("emprestimos")


# ----- Impressão de listas -----
@bp.get("/imprimir/<lista>")
def imprimir(lista):
    br = current_app.jinja_env.filters["data_br"]
    if lista == "acervo":
        titulo, cab = "Acervo", ["Título", "Autor", "ISBN", "Disponíveis"]
        linhas = [(l["titulo"], l["autor_nome"], l["isbn"], l["quantidade_disponivel"]) for l in srv.buscar_livros()]
    elif lista == "emprestimos":
        titulo, cab = "Empréstimos em aberto", ["Livro", "Quem pegou", "Emprestado em", "Devolver até"]
        linhas = [(e["livro_titulo"], f'{e["usuario_nome"]} ({e["usuario_tipo"]})', e["data_emprestimo"],
                   br(e["data_prevista"])) for e in srv.emprestimos_ativos()]
    elif lista == "reservas":
        titulo, cab = "Fila de reservas", ["Livro", "Pessoa", "Reservado em", "Situação"]
        linhas = [(r["livro_titulo"], r["usuario_nome"], br(r["data_reserva"]),
                   f'Retirar até {br(r["data_limite"])}' if r["status"] == "Disponivel" else "Na fila")
                  for r in srv.reservas_abertas()]
    elif lista == "sugestoes":
        titulo, cab = "Sugestões de livros (pendentes)", ["Título", "Autor", "ISBN", "Sugerido por"]
        linhas = [(s["titulo"], s["autor"], s["isbn"] or "—", s["sugerido_por"] or "—")
                  for s in srv.listar_sugestoes(status="Pendente")]
    else:
        abort(404)
    return render_template("imprimir.html", titulo=titulo, cabecalho=cab, linhas=linhas,
                           hoje=datetime.now().strftime("%Y-%m-%d"))


# ----- Backups e exportação -----
@bp.get("/backups")
def backups():
    return render_template("backups.html", backups=srv.listar_backups(), dias=srv.dias_desde_backup())


@bp.post("/backups")
def criar_backup():
    _executar(srv.fazer_backup, "Backup criado: {}.")
    return redirect(url_for("main.backups"))


@bp.post("/backups/<nome>/restaurar")
def restaurar(nome):
    if _executar(srv.restaurar_backup, "Backup restaurado. Os dados voltaram ao estado daquele dia.", nome):
        current_app.logger.warning("Backup restaurado: %s", nome)
    return redirect(url_for("main.backups"))


@bp.get("/backups/<nome>/baixar")
def baixar_backup(nome):
    return send_from_directory(srv.pasta_backups(), nome, as_attachment=True)


@bp.get("/exportar/<tabela>")
def exportar(tabela):
    try:
        cabecalho, linhas = srv.exportar(tabela)
    except srv.ErroNegocio:
        abort(404)
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";")  # ";" e BOM: o Excel brasileiro abre com acentos corretos
    escritor.writerow(cabecalho)
    escritor.writerows(linhas)
    return Response("\ufeff" + saida.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={tabela}.csv"})


@bp.post("/encerrar")
def encerrar():
    """Só funciona no modo 'último recurso' do programa (navegador comum), para poder desligar o sistema."""
    if not current_app.config.get("MODO_PROGRAMA"):
        abort(404)
    current_app.logger.info("Sistema encerrado pelo botão Encerrar")
    threading.Timer(0.5, os._exit, [0]).start()
    return "Sistema encerrado. Você já pode fechar esta aba."


@bp.get("/ping")
def ping():
    """A página chama isto a cada poucos segundos; o programa usa para saber se a janela ainda está aberta."""
    current_app.config["ULTIMO_PING"] = time.monotonic()
    return "", 204

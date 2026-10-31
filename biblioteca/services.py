"""Camada de regras de negócio. Não conhece HTTP: recebe dados, valida, grava e devolve."""
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from flask import current_app

from .db import close_db, get_db, init_db

TIPOS = ("Aluno", "Professor")
MOTIVOS_BAIXA = ("Perdido", "Danificado", "Outro")


class ErroNegocio(Exception):
    """Erro com mensagem pronta para mostrar ao usuário."""


def _limpar(texto):
    return " ".join((texto or "").split())


SERIES = ("8º ano", "9º ano", "1º ano EM", "2º ano EM", "3º ano EM")  # únicas séries da escola
LETRAS = ("A", "B")  # cada série tem a turma A e a turma B (o sistema continua lendo outras letras já cadastradas)


def _normalizar_turma(texto):
    """Aceita só as séries da escola, com letra opcional ('9º ano B'). Devolve o texto padronizado."""
    texto = _limpar(texto)
    if not texto:
        raise ErroNegocio("Informe a série e a turma do aluno.")
    for serie in SERIES:
        if texto.casefold().startswith(serie.casefold()):
            resto = texto[len(serie):]
            if resto == "":
                return serie
            if len(resto) == 2 and resto[0] == " " and resto[1].isalpha():
                return f"{serie} {resto[1].upper()}"
    raise ErroNegocio("Turma inválida. As turmas vão do 8º ano ao 3º ano do ensino médio (ex.: 9º ano A, 2º ano EM B).")


def separar_turma(turma):
    """'9º ano B' -> ('9º ano', 'B'). Texto fora da lista -> ('', '')."""
    try:
        normal = _normalizar_turma(turma or "")
    except ErroNegocio:
        return "", ""
    if len(normal) > 2 and normal[-2] == " " and normal[:-2] in SERIES:
        return normal[:-2], normal[-1]
    return normal, ""


def _juntar_obs(atual, rotulo, nova):
    nova = _limpar(nova)
    if not nova:
        return atual
    texto = f"{rotulo}: {nova}"
    return f"{atual} | {texto}" if atual else texto


def _inteiro(valor, minimo):
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        raise ErroNegocio("Informe a quantidade de exemplares com um número inteiro.")
    if numero < minimo:
        raise ErroNegocio(f"A quantidade de exemplares deve ser {minimo} ou mais.")
    return numero


POR_PAGINA = 20


def _consultar(sql, params=(), pagina=None):
    """Sem `pagina`: devolve a lista inteira. Com `pagina`: devolve um dict com os itens da página."""
    db = get_db()
    if pagina is None:
        return db.execute(sql, params).fetchall()
    total = db.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
    paginas = max(1, -(-total // POR_PAGINA))
    pagina = min(max(pagina, 1), paginas)
    itens = db.execute(f"{sql} LIMIT ? OFFSET ?", (*params, POR_PAGINA, (pagina - 1) * POR_PAGINA)).fetchall()
    return {"itens": itens, "pagina": pagina, "paginas": paginas, "total": total}


# ---------- Autores (criados a partir dos livros) ----------
def _obter_ou_criar_autor(db, nome):
    nome = _limpar(nome)
    for autor in db.execute("SELECT id, nome FROM autores").fetchall():
        if autor["nome"].casefold() == nome.casefold():
            return autor["id"]
    return db.execute("INSERT INTO autores (nome) VALUES (?)", (nome,)).lastrowid


def _remover_autores_sem_livro(db):
    db.execute("DELETE FROM autores WHERE id NOT IN (SELECT autor_id FROM livros)")


def nomes_autores():
    return get_db().execute("SELECT nome FROM autores ORDER BY nome").fetchall()


def buscar_autores(busca="", pagina=None):
    return _consultar(
        """SELECT autores.id, autores.nome, COUNT(livros.id) AS total_livros,
                  GROUP_CONCAT(livros.titulo, ', ') AS titulos
           FROM autores LEFT JOIN livros ON livros.autor_id = autores.id
           WHERE autores.nome LIKE ? GROUP BY autores.id ORDER BY autores.nome""",
        (f"%{busca}%",), pagina,
    )


# ---------- Gêneros ----------
# Lista fixa de propósito: com texto livre, "Romance" e "romances" viram gêneros diferentes nas estatísticas.
# Para acrescentar ou renomear um gênero, é só editar esta lista (livros já salvos mantêm o nome antigo).
GENEROS = (
    "Romance", "Conto e crônica", "Poesia", "Teatro", "Ficção científica", "Fantasia", "Terror",
    "Policial e suspense", "Aventura", "Biografia", "História", "Filosofia e sociologia", "Ciências",
    "Didático e vestibular", "Quadrinhos e mangá", "Infantojuvenil", "Autoajuda", "Outros",
)


def _genero(valor):
    """None = não informado (na edição, mantém o atual); '' = sem gênero; senão tem de estar na lista."""
    if valor is None:
        return None
    valor = _limpar(valor)
    if valor and valor not in GENEROS:
        raise ErroNegocio("Escolha um gênero da lista.")
    return valor


# ---------- Livros ----------
def buscar_livros(busca="", pagina=None):
    like = f"%{busca}%"
    return _consultar(
        """SELECT livros.*, autores.nome AS autor_nome
           FROM livros JOIN autores ON livros.autor_id = autores.id
           WHERE livros.titulo LIKE ? OR autores.nome LIKE ? OR livros.isbn LIKE ? OR livros.genero LIKE ?
           ORDER BY livros.titulo""",
        (like, like, like, like), pagina,
    )


def obter_livro(livro_id):
    livro = get_db().execute(
        "SELECT livros.*, autores.nome AS autor_nome FROM livros "
        "JOIN autores ON livros.autor_id = autores.id WHERE livros.id = ?",
        (livro_id,),
    ).fetchone()
    if livro is None:
        raise ErroNegocio("Livro não encontrado.")
    return livro


def salvar_livro(titulo, isbn, autor, quantidade, livro_id=None, observacao="", genero=None):
    titulo, isbn, autor = _limpar(titulo), _limpar(isbn), _limpar(autor)
    isbn = re.sub(r"[\s-]", "", isbn)  # 978-85-... e 9788... são o mesmo ISBN
    observacao = _limpar(observacao) or None
    genero = _genero(genero)
    if not (titulo and isbn and autor):
        raise ErroNegocio("Preencha título, ISBN e autor.")
    qtd = _inteiro(quantidade, 0 if livro_id else 1)
    db = get_db()
    if livro_id is None:  # ISBN já cadastrado: é outra cópia do mesmo livro (soma) ou é um erro
        existente = db.execute(
            "SELECT livros.id, livros.titulo, livros.quantidade_disponivel, autores.nome AS autor "
            "FROM livros JOIN autores ON autores.id = livros.autor_id "
            "WHERE REPLACE(REPLACE(livros.isbn, '-', ''), ' ', '') = ?", (isbn,)).fetchone()
        if existente:
            if existente["titulo"].casefold() != titulo.casefold() or existente["autor"].casefold() != autor.casefold():
                raise ErroNegocio(f'Este ISBN já pertence a "{existente["titulo"]}", de {existente["autor"]}. '
                                  "Se for o mesmo livro, use o mesmo título e autor para somar exemplares.")
            with db:
                # outro exemplar: só preenche o gênero se o livro ainda não tinha
                db.execute("UPDATE livros SET quantidade_disponivel = quantidade_disponivel + ?, "
                           "genero = COALESCE(genero, NULLIF(?, '')) WHERE id = ?",
                           (qtd, genero, existente["id"]))
                _promover(db, existente["id"])
            return (f"Este livro já estava cadastrado: somei {qtd} exemplar(es). "
                    f"Agora são {existente['quantidade_disponivel'] + qtd} disponíveis.")
    try:
        with db:  # autor e livro entram juntos, ou nenhum dos dois
            autor_id = _obter_ou_criar_autor(db, autor)
            if livro_id is None:
                db.execute(
                    "INSERT INTO livros (titulo, isbn, quantidade_disponivel, autor_id, observacao, genero) "
                    "VALUES (?, ?, ?, ?, ?, ?)", (titulo, isbn, qtd, autor_id, observacao, genero or None))
            else:
                db.execute(
                    "UPDATE livros SET titulo=?, isbn=?, quantidade_disponivel=?, autor_id=?, observacao=?, "
                    "genero = CASE WHEN ? IS NULL THEN genero ELSE NULLIF(?, '') END "  # None = não mexe
                    "WHERE id=?", (titulo, isbn, qtd, autor_id, observacao, genero, genero, livro_id))
                _remover_autores_sem_livro(db)
                _promover(db, livro_id)
    except sqlite3.IntegrityError:
        raise ErroNegocio("Este ISBN já está cadastrado em outro livro.")
    return "Livro atualizado." if livro_id else "Livro cadastrado com sucesso."


def excluir_livro(livro_id):
    db = get_db()
    if db.execute("SELECT 1 FROM emprestimos WHERE livro_id = ?", (livro_id,)).fetchone():
        raise ErroNegocio("Este livro tem empréstimos registrados e não pode ser excluído.")
    if db.execute("SELECT 1 FROM reservas WHERE livro_id = ? AND status IN ('Aguardando', 'Disponivel')",
                  (livro_id,)).fetchone():
        raise ErroNegocio("Há reservas em aberto para este livro. Cancele-as antes de excluir.")
    with db:
        db.execute("DELETE FROM reservas WHERE livro_id = ?", (livro_id,))
        db.execute("DELETE FROM baixas WHERE livro_id = ?", (livro_id,))
        db.execute("DELETE FROM livros WHERE id = ?", (livro_id,))
        _remover_autores_sem_livro(db)


# ---------- Sugestões de livros novos ----------
STATUS_SUGESTAO = ("Pendente", "Adquirida")


def listar_sugestoes(busca="", status="", pagina=None):
    """Pendentes primeiro; dentro de cada grupo, a mais recente no topo. `status` vazio = todas."""
    like = f"%{(busca or '').strip()}%"
    sql = ("SELECT * FROM sugestoes "
           "WHERE (titulo LIKE ? OR autor LIKE ? OR isbn LIKE ? OR sugerido_por LIKE ?)")
    params = [like] * 4
    if status in STATUS_SUGESTAO:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY CASE status WHEN 'Pendente' THEN 0 ELSE 1 END, id DESC"
    return _consultar(sql, tuple(params), pagina)


def obter_sugestao(sugestao_id):
    sugestao = get_db().execute("SELECT * FROM sugestoes WHERE id = ?", (sugestao_id,)).fetchone()
    if sugestao is None:
        raise ErroNegocio("Sugestão não encontrada.")
    return sugestao


def _titulo_no_acervo(db, titulo, autor, isbn):
    """Título do livro do acervo que combina com a sugestão (mesmo ISBN, ou mesmo título e autor)."""
    for livro in db.execute("SELECT livros.titulo, livros.isbn, autores.nome AS autor FROM livros "
                            "JOIN autores ON autores.id = livros.autor_id"):
        mesmo_isbn = isbn and re.sub(r"[\s-]", "", livro["isbn"]) == isbn
        mesmo_livro = (livro["titulo"].casefold() == titulo.casefold()
                       and livro["autor"].casefold() == autor.casefold())
        if mesmo_isbn or mesmo_livro:
            return livro["titulo"]
    return None


def salvar_sugestao(titulo, autor, isbn="", motivo="", sugerido_por="", sugestao_id=None):
    """Cria ou atualiza uma sugestão. Recusa livro que já está no acervo.

    O mesmo livro pode ser sugerido por pessoas diferentes: cada pedido é contado em "Mais sugeridos".
    Só é barrada a mesma pessoa pedindo o mesmo livro duas vezes."""
    titulo, autor = _limpar(titulo), _limpar(autor)
    isbn = re.sub(r"[\s-]", "", _limpar(isbn)) or None
    motivo, sugerido_por = _limpar(motivo) or None, _limpar(sugerido_por) or None
    if not (titulo and autor):
        raise ErroNegocio("Preencha título e autor.")
    db = get_db()
    atual = obter_sugestao(sugestao_id) if sugestao_id is not None else None
    # Só confere enquanto a sugestão está pendente: uma já adquirida costuma estar no acervo.
    if atual is None or atual["status"] == "Pendente":
        no_acervo = _titulo_no_acervo(db, titulo, autor, isbn)
        if no_acervo:
            raise ErroNegocio(f'Este livro já está no acervo ("{no_acervo}"). '
                              'Para ter mais exemplares, use "Cadastrar livro" com o mesmo ISBN.')
        for p in db.execute("SELECT id, titulo, autor, isbn, sugerido_por FROM sugestoes WHERE status = 'Pendente'"):
            if p["id"] == sugestao_id:
                continue
            if (isbn and p["isbn"] == isbn) or (p["titulo"].casefold() == titulo.casefold()
                                                and p["autor"].casefold() == autor.casefold()):
                if sugerido_por and p["sugerido_por"] and p["sugerido_por"].casefold() == sugerido_por.casefold():
                    raise ErroNegocio(f'{sugerido_por} já sugeriu este livro. Se outra pessoa também quer, '
                                      'registre com o nome dela: cada pedido conta em "Mais sugeridos".')
    with db:
        if atual is None:
            novo_id = db.execute(
                "INSERT INTO sugestoes (titulo, autor, isbn, motivo, sugerido_por, data_sugestao) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (titulo, autor, isbn, motivo, sugerido_por, datetime.now().strftime("%Y-%m-%d"))).lastrowid
        else:  # edição mantém a data e a situação
            db.execute("UPDATE sugestoes SET titulo=?, autor=?, isbn=?, motivo=?, sugerido_por=? WHERE id=?",
                       (titulo, autor, isbn, motivo, sugerido_por, sugestao_id))
    if atual is not None:
        return "Sugestão atualizada."
    votos = next(g["votos"] for g in _grupos_pendentes(db) if novo_id in g["ids"])
    if votos > 1:
        return f"Sugestão registrada. Este livro já tinha {votos - 1} pedido(s): agora são {votos}."
    return "Sugestão registrada."


def _grupos_pendentes(db):
    """Agrupa as sugestões pendentes por livro: mesmo ISBN, ou mesmo título e autor."""
    grupos, por_isbn, por_obra = [], {}, {}
    for s in db.execute("SELECT * FROM sugestoes WHERE status = 'Pendente' ORDER BY id"):
        obra = (s["titulo"].casefold(), s["autor"].casefold())
        g = (por_isbn.get(s["isbn"]) if s["isbn"] else None) or por_obra.get(obra)
        if g is None:
            g = {"titulo": s["titulo"], "autor": s["autor"], "isbn": None, "ids": [],
                 "pedidos": [], "sem_nome": 0, "ultima": ""}
            grupos.append(g)
        por_obra.setdefault(obra, g)
        if s["isbn"]:
            g["isbn"] = g["isbn"] or s["isbn"]
            por_isbn.setdefault(s["isbn"], g)
        g["ids"].append(s["id"])
        if s["sugerido_por"]:
            g["pedidos"].append(s["sugerido_por"])
        else:
            g["sem_nome"] += 1
        g["ultima"] = max(g["ultima"], s["data_sugestao"])
    for g in grupos:
        g["votos"] = len(g["ids"])
    return grupos


def mais_sugeridos(limite=20):
    """Livros com sugestões pendentes, do mais pedido ao menos. Cada item traz os ids das sugestões do
    grupo, para marcar todas como adquiridas de uma vez."""
    grupos = _grupos_pendentes(get_db())
    grupos.sort(key=lambda g: g["titulo"].casefold())            # desempate: ordem alfabética
    grupos.sort(key=lambda g: g["ultima"], reverse=True)         # depois o pedido mais recente
    grupos.sort(key=lambda g: g["votos"], reverse=True)          # e, antes de tudo, o mais pedido
    return grupos[:limite]


def adquirir_sugestoes(ids):
    """Marca como adquiridas as sugestões pendentes informadas (todas as do mesmo livro, por exemplo)."""
    ids = [int(i) for i in ids if str(i).strip().isdigit()]
    if not ids:
        raise ErroNegocio("Nenhuma sugestão informada.")
    db = get_db()
    with db:
        n = db.execute(f"UPDATE sugestoes SET status = 'Adquirida' WHERE status = 'Pendente' "
                       f"AND id IN ({','.join('?' * len(ids))})", ids).rowcount
    if not n:
        raise ErroNegocio("Essas sugestões já não estão pendentes.")
    return n


def alternar_sugestao(sugestao_id):
    """Pendente <-> Adquirida. Devolve a nova situação em minúsculas, para a mensagem."""
    nova = "Pendente" if obter_sugestao(sugestao_id)["status"] == "Adquirida" else "Adquirida"
    db = get_db()
    with db:
        db.execute("UPDATE sugestoes SET status = ? WHERE id = ?", (nova, sugestao_id))
    return nova.lower()


def excluir_sugestao(sugestao_id):
    obter_sugestao(sugestao_id)
    db = get_db()
    with db:
        db.execute("DELETE FROM sugestoes WHERE id = ?", (sugestao_id,))


# ---------- Alunos e professores ----------
def listar_pessoas(pagina=None, busca=""):
    """Cadastros em ordem; com `busca`, só os que combinam com nome, e-mail, turma, disciplina ou matrícula."""
    busca = (busca or "").strip()
    if not busca:
        return _consultar("SELECT * FROM usuarios ORDER BY tipo, nome", (), pagina)
    like = f"%{busca}%"
    return _consultar(
        """SELECT * FROM usuarios
           WHERE nome LIKE ? OR email LIKE ? OR turma LIKE ? OR disciplina LIKE ? OR matricula LIKE ?
           ORDER BY tipo, nome""",
        (like,) * 5, pagina,
    )


def obter_pessoa(pessoa_id):
    pessoa = get_db().execute("SELECT * FROM usuarios WHERE id = ?", (pessoa_id,)).fetchone()
    if pessoa is None:
        raise ErroNegocio("Cadastro não encontrado.")
    return pessoa


def salvar_pessoa(tipo, nome, email, turma, disciplina, pessoa_id=None, matricula=""):
    nome, email = _limpar(nome), (email or "").strip().lower()
    turma, disciplina = _limpar(turma), _limpar(disciplina)
    matricula = (_limpar(matricula) or None) if tipo == "Aluno" else None  # só aluno tem matrícula
    if tipo not in TIPOS or not (nome and email):
        raise ErroNegocio("Informe tipo, nome e e-mail.")
    if tipo == "Aluno":
        turma = _normalizar_turma(turma)
    if tipo == "Professor" and not disciplina:
        raise ErroNegocio("Informe a disciplina do professor.")
    turma = turma if tipo == "Aluno" else None
    disciplina = disciplina if tipo == "Professor" else None
    db = get_db()
    try:
        with db:
            if pessoa_id is None:
                db.execute(
                    "INSERT INTO usuarios (nome, email, tipo, turma, disciplina, matricula) "
                    "VALUES (?, ?, ?, ?, ?, ?)", (nome, email, tipo, turma, disciplina, matricula))
            else:
                db.execute(
                    "UPDATE usuarios SET nome=?, email=?, tipo=?, turma=?, disciplina=?, matricula=? "
                    "WHERE id=?", (nome, email, tipo, turma, disciplina, matricula, pessoa_id))
    except sqlite3.IntegrityError:
        raise ErroNegocio("Este e-mail ou esta matrícula já está cadastrado.")


def excluir_pessoa(pessoa_id):
    db = get_db()
    if db.execute("SELECT 1 FROM emprestimos WHERE usuario_id = ?", (pessoa_id,)).fetchone():
        raise ErroNegocio("Este cadastro tem empréstimos registrados e não pode ser excluído.")
    with db:
        _cancelar_reservas_da_pessoa(db, pessoa_id)
        db.execute("DELETE FROM reservas WHERE usuario_id = ?", (pessoa_id,))
        db.execute("DELETE FROM usuarios WHERE id = ?", (pessoa_id,))


# ---------- Empréstimos ----------
_SQL_ATIVOS = """SELECT emprestimos.*, livros.titulo AS livro_titulo,
                  usuarios.nome AS usuario_nome, usuarios.tipo AS usuario_tipo, usuarios.turma AS usuario_turma,
                  CAST(julianday(emprestimos.data_prevista) - julianday(date('now', 'localtime')) AS INTEGER) AS dias_restantes
           FROM emprestimos
           JOIN livros ON emprestimos.livro_id = livros.id
           JOIN usuarios ON emprestimos.usuario_id = usuarios.id
           WHERE emprestimos.status = 'Ativo'"""


def emprestimos_ativos():
    return get_db().execute(_SQL_ATIVOS + " ORDER BY emprestimos.id DESC").fetchall()


def emprestimos_da_pessoa(usuario_id):
    """Livros que uma pessoa está levando agora, o mais atrasado primeiro."""
    return get_db().execute(_SQL_ATIVOS + " AND emprestimos.usuario_id = ? ORDER BY emprestimos.data_prevista",
                            (usuario_id,)).fetchall()


def emprestar(livro_id, usuario_id, observacao=""):
    """Baixa o estoque e registra o empréstimo. Devolve a data limite (dd/mm/aaaa)."""
    db = get_db()
    expirar_reservas()
    pessoa = db.execute("SELECT tipo, ativo FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
    if pessoa is None or not pessoa["ativo"]:
        raise ErroNegocio("Este cadastro não está ativo.")
    hoje = datetime.now().strftime("%Y-%m-%d")
    abertos = db.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(data_prevista < ?), 0) AS atrasados "
        "FROM emprestimos WHERE usuario_id = ? AND status = 'Ativo'", (hoje, usuario_id)).fetchone()
    if abertos["atrasados"]:
        raise ErroNegocio("Esta pessoa tem livro atrasado. Registre a devolução antes de um novo empréstimo.")
    reserva = db.execute("SELECT id FROM reservas WHERE livro_id = ? AND usuario_id = ? AND status = 'Disponivel'",
                         (livro_id, usuario_id)).fetchone()
    reservados = 0 if reserva else _retidos(db, livro_id)  # exemplares separados para a fila
    limite = current_app.config["LIMITES"][pessoa["tipo"]]
    if abertos["n"] >= limite:
        raise ErroNegocio(f"Limite de {limite} livros emprestados ao mesmo tempo atingido.")
    with db:
        # UPDATE condicional: nunca deixa o estoque negativo, mesmo com pedidos simultâneos.
        baixa = db.execute(
            "UPDATE livros SET quantidade_disponivel = quantidade_disponivel - 1 "
            "WHERE id = ? AND quantidade_disponivel > ?", (livro_id, reservados))
        if baixa.rowcount == 0:
            raise ErroNegocio("Livro sem exemplares livres no momento (pode estar reservado).")
        if reserva:
            db.execute("UPDATE reservas SET status = 'Atendida' WHERE id = ?", (reserva["id"],))
        agora = datetime.now()
        prevista = agora + timedelta(days=current_app.config["PRAZOS"][pessoa["tipo"]])
        db.execute(
            "INSERT INTO emprestimos (livro_id, usuario_id, data_emprestimo, data_prevista, observacao) "
            "VALUES (?, ?, ?, ?, ?)",
            (livro_id, usuario_id, agora.strftime("%d/%m/%Y %H:%M"), prevista.strftime("%Y-%m-%d"), _limpar(observacao) or None))
    return prevista.strftime("%d/%m/%Y")


def devolver(emprestimo_id, observacao="", estado="Bom"):
    if estado not in ("Bom", "Com defeito"):
        raise ErroNegocio("Informe o estado em que o livro voltou.")
    db = get_db()
    with db:
        emprestimo = db.execute(
            "SELECT livro_id, observacao FROM emprestimos WHERE id = ? AND status = 'Ativo'",
            (emprestimo_id,)).fetchone()
        if emprestimo is None:
            raise ErroNegocio("Este empréstimo não existe ou já foi devolvido.")
        db.execute("UPDATE livros SET quantidade_disponivel = quantidade_disponivel + 1 "
                   "WHERE id = ?", (emprestimo["livro_id"],))
        db.execute("UPDATE emprestimos SET status = 'Devolvido', data_devolucao = ?, observacao = ?, estado_devolucao = ? WHERE id = ?",
                   (datetime.now().strftime("%Y-%m-%d"),
                    _juntar_obs(emprestimo["observacao"], "Devolução", observacao), estado, emprestimo_id))
        _promover(db, emprestimo["livro_id"])


def renovar(emprestimo_id):
    """Estende o prazo (limitado por MAX_RENOVACOES). Só vale antes de atrasar."""
    db = get_db()
    e = db.execute("SELECT emprestimos.renovacoes, emprestimos.data_prevista, emprestimos.livro_id, usuarios.tipo "
                   "FROM emprestimos JOIN usuarios ON emprestimos.usuario_id = usuarios.id "
                   "WHERE emprestimos.id = ? AND emprestimos.status = 'Ativo'",
                   (emprestimo_id,)).fetchone()
    if e is None:
        raise ErroNegocio("Este empréstimo não existe ou já foi devolvido.")
    agora = datetime.now()
    if e["data_prevista"] and e["data_prevista"] < agora.strftime("%Y-%m-%d"):
        raise ErroNegocio("Empréstimo atrasado não pode ser renovado. Registre a devolução.")
    if db.execute("SELECT 1 FROM reservas WHERE livro_id = ? AND status = 'Aguardando'",
                  (e["livro_id"],)).fetchone():
        raise ErroNegocio("Há pessoas na fila de espera por este livro. Não é possível renovar.")
    if e["renovacoes"] >= current_app.config["MAX_RENOVACOES"]:
        raise ErroNegocio("Este empréstimo já foi renovado o máximo de vezes.")
    nova = agora + timedelta(days=current_app.config["PRAZOS"][e["tipo"]])
    with db:
        db.execute("UPDATE emprestimos SET data_prevista = ?, renovacoes = renovacoes + 1 "
                   "WHERE id = ?", (nova.strftime("%Y-%m-%d"), emprestimo_id))
    return nova.strftime("%d/%m/%Y")


def historico(busca="", pagina=None):
    """Todos os empréstimos (em aberto e devolvidos), do mais recente ao mais antigo."""
    like = f"%{busca}%"
    return _consultar(
        """SELECT emprestimos.*, livros.titulo AS livro_titulo,
                  usuarios.nome AS usuario_nome, usuarios.tipo AS usuario_tipo
           FROM emprestimos
           JOIN livros ON emprestimos.livro_id = livros.id
           JOIN usuarios ON emprestimos.usuario_id = usuarios.id
           WHERE livros.titulo LIKE ? OR usuarios.nome LIKE ?
           ORDER BY emprestimos.id DESC""", (like, like), pagina)


def alternar_ativo(pessoa_id):
    """Arquiva (ou reativa) um cadastro sem perder o histórico."""
    pessoa, db = obter_pessoa(pessoa_id), get_db()
    if pessoa["ativo"] and db.execute(
            "SELECT 1 FROM emprestimos WHERE usuario_id = ? AND status = 'Ativo'",
            (pessoa_id,)).fetchone():
        raise ErroNegocio("Esta pessoa ainda tem livros emprestados. Registre a devolução antes de arquivar.")
    with db:
        if pessoa["ativo"]:
            _cancelar_reservas_da_pessoa(db, pessoa_id)
        db.execute("UPDATE usuarios SET ativo = ? WHERE id = ?", (0 if pessoa["ativo"] else 1, pessoa_id))
    return "arquivado" if pessoa["ativo"] else "reativado"


def atrasados():
    """Empréstimos vencidos, agrupados por turma (alunos) ou 'Professores'."""
    hoje = datetime.now().strftime("%Y-%m-%d")
    return get_db().execute(
        """SELECT emprestimos.id, emprestimos.data_prevista, livros.titulo AS livro_titulo,
                  usuarios.nome AS usuario_nome,
                  CASE usuarios.tipo WHEN 'Aluno' THEN COALESCE(usuarios.turma, 'Sem turma')
                       ELSE 'Professores' END AS grupo,
                  CAST(julianday(?) - julianday(emprestimos.data_prevista) AS INTEGER) AS dias
           FROM emprestimos
           JOIN livros ON emprestimos.livro_id = livros.id
           JOIN usuarios ON emprestimos.usuario_id = usuarios.id
           WHERE emprestimos.status = 'Ativo' AND emprestimos.data_prevista < ?
           ORDER BY grupo, usuarios.nome""", (hoje, hoje)).fetchall()



# ---------- Reservas ----------
def _retidos(db, livro_id):
    """Exemplares já separados (reserva 'Disponivel') esperando retirada."""
    return db.execute("SELECT COUNT(*) FROM reservas WHERE livro_id = ? AND status = 'Disponivel'",
                      (livro_id,)).fetchone()[0]


def _promover(db, livro_id):
    """Separa os exemplares livres para quem está na fila, do mais antigo ao mais novo."""
    livro = db.execute("SELECT quantidade_disponivel FROM livros WHERE id = ?", (livro_id,)).fetchone()
    if livro is None:
        return
    livres = livro["quantidade_disponivel"] - _retidos(db, livro_id)
    limite = (datetime.now() + timedelta(days=current_app.config["PRAZO_RETIRADA_DIAS"])).strftime("%Y-%m-%d")
    for r in db.execute("SELECT id FROM reservas WHERE livro_id = ? AND status = 'Aguardando' "
                        "ORDER BY id LIMIT ?", (livro_id, max(livres, 0))).fetchall():
        db.execute("UPDATE reservas SET status = 'Disponivel', data_limite = ? WHERE id = ?", (limite, r["id"]))


def _cancelar_reservas_da_pessoa(db, pessoa_id):
    for r in db.execute("SELECT id, livro_id FROM reservas WHERE usuario_id = ? "
                        "AND status IN ('Aguardando', 'Disponivel')", (pessoa_id,)).fetchall():
        db.execute("UPDATE reservas SET status = 'Cancelada' WHERE id = ?", (r["id"],))
        _promover(db, r["livro_id"])


def reservas_abertas():
    return get_db().execute(
        """SELECT reservas.*, livros.titulo AS livro_titulo, usuarios.nome AS usuario_nome,
                  usuarios.tipo AS usuario_tipo
           FROM reservas JOIN livros ON reservas.livro_id = livros.id
           JOIN usuarios ON reservas.usuario_id = usuarios.id
           WHERE reservas.status IN ('Aguardando', 'Disponivel')
           ORDER BY livros.titulo, reservas.id""").fetchall()


def reservar(livro_id, usuario_id):
    db = get_db()
    expirar_reservas()
    pessoa = db.execute("SELECT ativo FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
    livro = db.execute("SELECT quantidade_disponivel FROM livros WHERE id = ?", (livro_id,)).fetchone()
    if pessoa is None or not pessoa["ativo"] or livro is None:
        raise ErroNegocio("Cadastro ou livro inválido.")
    if livro["quantidade_disponivel"] - _retidos(db, livro_id) > 0:
        raise ErroNegocio("Há exemplar livre: faça o empréstimo direto, sem reserva.")
    if db.execute("SELECT 1 FROM emprestimos WHERE livro_id = ? AND usuario_id = ? AND status = 'Ativo'",
                  (livro_id, usuario_id)).fetchone():
        raise ErroNegocio("Esta pessoa já está com este livro.")
    aberta = db.execute("SELECT livros.titulo FROM reservas JOIN livros ON livros.id = reservas.livro_id "
                        "WHERE reservas.usuario_id = ? AND reservas.status IN ('Aguardando', 'Disponivel')",
                        (usuario_id,)).fetchone()
    if aberta:  # vale para o mesmo livro e para qualquer outro
        raise ErroNegocio(f'Esta pessoa já tem uma reserva em aberto ("{aberta["titulo"]}"). '
                          "Cada pessoa pode ter só uma reserva por vez, de um exemplar.")
    with db:
        db.execute("INSERT INTO reservas (livro_id, usuario_id, data_reserva) VALUES (?, ?, ?)",
                   (livro_id, usuario_id, datetime.now().strftime("%Y-%m-%d")))


def cancelar_reserva(reserva_id):
    db = get_db()
    r = db.execute("SELECT livro_id FROM reservas WHERE id = ? AND status IN ('Aguardando', 'Disponivel')",
                   (reserva_id,)).fetchone()
    if r is None:
        raise ErroNegocio("Esta reserva não existe ou já foi encerrada.")
    with db:
        db.execute("UPDATE reservas SET status = 'Cancelada' WHERE id = ?", (reserva_id,))
        _promover(db, r["livro_id"])  # o próximo da fila passa a ter o exemplar


# ---------- Virada de ano ----------
def turmas_ativas():
    return get_db().execute(
        "SELECT turma, COUNT(*) AS total FROM usuarios WHERE tipo = 'Aluno' AND ativo = 1 "
        "AND turma IS NOT NULL GROUP BY turma ORDER BY turma").fetchall()


def sugerir_turma(turma):
    """Próxima série ('9º ano' -> '1º ano EM'); '' = arquivar (3º ano EM); '__manter__' = turma fora da lista."""
    serie, _ = separar_turma(turma)
    if serie not in SERIES:
        return "__manter__"
    posicao = SERIES.index(serie)
    return SERIES[posicao + 1] if posicao + 1 < len(SERIES) else ""


def fazer_backup(prefixo="backup"):
    """Cópia de segurança do banco em dados/backups/."""
    banco = current_app.config["DATABASE"]
    arquivo = pasta_backups() / f"{prefixo}-{datetime.now():%Y%m%d-%H%M%S}.db"
    origem, copia = sqlite3.connect(banco), sqlite3.connect(arquivo)
    origem.backup(copia)
    origem.close()
    copia.close()
    return arquivo


ACOES_ALUNO = ("arquivar", "manter")


def alunos_por_turma():
    """{turma: [alunos ativos]} para a Virada de ano, com quantos livros cada um tem emprestados."""
    resultado = {}
    for a in get_db().execute(
            "SELECT u.id, u.nome, u.matricula, u.turma, "
            "(SELECT COUNT(*) FROM emprestimos e WHERE e.usuario_id = u.id AND e.status = 'Ativo') AS emprestados "
            "FROM usuarios u WHERE u.tipo = 'Aluno' AND u.ativo = 1 AND u.turma IS NOT NULL"):
        resultado.setdefault(a["turma"], []).append(dict(a))
    for alunos in resultado.values():
        alunos.sort(key=lambda a: a["nome"].casefold())
    return resultado


def virar_ano(pares, excecoes=None):
    """pares = [(turma_atual, turma_nova)]. Turma nova vazia = arquivar todos os alunos da turma.

    excecoes = {aluno_id: 'arquivar' | 'manter'}: decisões individuais, que valem mais que a da turma.
    'arquivar' = o aluno saiu da escola (mesmo que o resto da turma passe de série); 'manter' = ele fica
    na turma atual (repetiu o ano, por exemplo).

    Devolve (mudaram de turma, arquivados, lista 'Nome (turma)' de quem NÃO foi arquivado por ter livro emprestado)."""
    db = get_db()
    destino = {}  # aluno_id -> turma nova ('' = arquivar); tudo é decidido ANTES de alterar,
    for atual, nova in pares:  # para uma turma não ser movida duas vezes
        nova = _normalizar_turma(nova) if _limpar(nova) else ""
        for r in db.execute("SELECT id FROM usuarios WHERE tipo = 'Aluno' AND ativo = 1 AND turma = ?", (atual,)):
            destino[r["id"]] = nova
    for aluno_id, acao in (excecoes or {}).items():
        if acao == "manter":
            destino.pop(aluno_id, None)
        elif acao == "arquivar":
            destino[aluno_id] = ""
    movidos = arquivados = 0
    pendentes = []
    with db:
        for aluno_id, nova in destino.items():
            aluno = db.execute("SELECT nome, turma FROM usuarios WHERE id = ? AND tipo = 'Aluno' AND ativo = 1",
                               (aluno_id,)).fetchone()
            if aluno is None:  # só alunos ativos entram (um id de professor, por exemplo, é ignorado)
                continue
            if nova:
                db.execute("UPDATE usuarios SET turma = ? WHERE id = ?", (nova, aluno_id))
                movidos += 1
            elif db.execute("SELECT 1 FROM emprestimos WHERE usuario_id = ? AND status = 'Ativo'",
                            (aluno_id,)).fetchone():
                pendentes.append(f"{aluno['nome']} ({aluno['turma']})")
            else:
                _cancelar_reservas_da_pessoa(db, aluno_id)
                db.execute("UPDATE usuarios SET ativo = 0 WHERE id = ?", (aluno_id,))
                arquivados += 1
    return movidos, arquivados, pendentes


def expirar_reservas():
    """Cancela reservas separadas que ninguém retirou no prazo e passa o exemplar ao próximo da fila."""
    db = get_db()
    vencidas = db.execute("SELECT id, livro_id FROM reservas WHERE status = 'Disponivel' "
                          "AND data_limite IS NOT NULL AND data_limite < ?",
                          (datetime.now().strftime("%Y-%m-%d"),)).fetchall()
    if vencidas:
        with db:
            for r in vencidas:
                db.execute("UPDATE reservas SET status = 'Cancelada' WHERE id = ?", (r["id"],))
                _promover(db, r["livro_id"])
    return len(vencidas)


# ---------- Livro perdido ou danificado ----------
def baixas_do_livro(livro_id):
    return get_db().execute("SELECT * FROM baixas WHERE livro_id = ? ORDER BY id DESC", (livro_id,)).fetchall()


def baixar_exemplar(livro_id, motivo, observacao=""):
    """Tira da estante um exemplar perdido ou danificado, mantendo o registro."""
    if motivo not in MOTIVOS_BAIXA:
        raise ErroNegocio("Escolha o motivo da baixa.")
    db, livro = get_db(), obter_livro(livro_id)
    if livro["quantidade_disponivel"] - _retidos(db, livro_id) <= 0:
        raise ErroNegocio("Não há exemplar livre na estante. Se o livro está com alguém, use o botão Perdido no empréstimo.")
    with db:
        db.execute("UPDATE livros SET quantidade_disponivel = quantidade_disponivel - 1, "
                   "baixados = baixados + 1 WHERE id = ?", (livro_id,))
        db.execute("INSERT INTO baixas (livro_id, data_baixa, motivo, observacao) VALUES (?, ?, ?, ?)",
                   (livro_id, datetime.now().strftime("%Y-%m-%d"), motivo, _limpar(observacao) or None))


def baixar_emprestimo(emprestimo_id, observacao=""):
    """Livro emprestado que não volta: encerra o empréstimo SEM devolver o exemplar ao estoque."""
    db = get_db()
    e = db.execute("SELECT livro_id, observacao FROM emprestimos WHERE id = ? AND status = 'Ativo'",
                   (emprestimo_id,)).fetchone()
    if e is None:
        raise ErroNegocio("Este empréstimo não existe ou já foi encerrado.")
    nota = _limpar(observacao) or "sem detalhes"
    hoje = datetime.now().strftime("%Y-%m-%d")
    with db:
        db.execute("UPDATE emprestimos SET status = 'Devolvido', data_devolucao = ?, observacao = ?, estado_devolucao = 'Perdido' WHERE id = ?",
                   (hoje, _juntar_obs(e["observacao"], "Baixa (perdido/danificado)", nota), emprestimo_id))
        db.execute("UPDATE livros SET baixados = baixados + 1 WHERE id = ?", (e["livro_id"],))
        db.execute("INSERT INTO baixas (livro_id, data_baixa, motivo, observacao) VALUES (?, ?, 'Perdido', ?)",
                   (e["livro_id"], hoje, nota))


# ---------- Painel e estatísticas ----------
def painel():
    db, hoje = get_db(), datetime.now().strftime("%Y-%m-%d")
    um = lambda sql, p=(): db.execute(sql, p).fetchone()[0]
    return {
        "emprestados": um("SELECT COUNT(*) FROM emprestimos WHERE status = 'Ativo'"),
        "atrasados": um("SELECT COUNT(*) FROM emprestimos WHERE status = 'Ativo' AND data_prevista < ?", (hoje,)),
        "retirada": um("SELECT COUNT(*) FROM reservas WHERE status = 'Disponivel'"),
        "fila": um("SELECT COUNT(*) FROM reservas WHERE status = 'Aguardando'"),
        "titulos": um("SELECT COUNT(*) FROM livros"),
        "exemplares": um("SELECT COALESCE(SUM(quantidade_disponivel), 0) FROM livros"),
        "pessoas": um("SELECT COUNT(*) FROM usuarios WHERE ativo = 1"),
        "top_livros": db.execute(
            "SELECT livros.titulo, COUNT(*) AS total FROM emprestimos JOIN livros ON livros.id = emprestimos.livro_id "
            "GROUP BY livros.id ORDER BY total DESC, livros.titulo LIMIT 5").fetchall(),
        "top_leitores": db.execute(
            "SELECT usuarios.nome, usuarios.tipo, COUNT(*) AS total FROM emprestimos "
            "JOIN usuarios ON usuarios.id = emprestimos.usuario_id "
            "GROUP BY usuarios.id ORDER BY total DESC, usuarios.nome LIMIT 5").fetchall(),
    }


# ---------- Backups e exportação ----------
def pasta_backups():
    pasta = Path(current_app.config["DATABASE"]).parent / "backups"
    pasta.mkdir(exist_ok=True)
    return pasta


def listar_backups():
    itens = [{"nome": f.name, "quando": datetime.fromtimestamp(f.stat().st_mtime),
              "kb": max(1, f.stat().st_size // 1024)} for f in pasta_backups().glob("*.db")]
    return sorted(itens, key=lambda i: i["quando"], reverse=True)


def dias_desde_backup():
    """Dias desde o último backup, ou None se nunca houve."""
    itens = listar_backups()
    return (datetime.now() - itens[0]["quando"]).days if itens else None


def restaurar_backup(nome):
    arquivo = pasta_backups() / Path(nome).name  # .name impede caminhos como ../
    if not arquivo.is_file() or arquivo.suffix != ".db":
        raise ErroNegocio("Backup não encontrado.")
    try:
        conn = sqlite3.connect(arquivo)
        tabelas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        conn.close()
    except sqlite3.DatabaseError:
        tabelas = set()
    if not {"livros", "usuarios", "emprestimos"} <= tabelas:
        raise ErroNegocio("Este arquivo não é um backup válido do sistema.")
    fazer_backup("antes-de-restaurar")  # guarda o estado atual, para poder desfazer
    banco = current_app.config["DATABASE"]
    close_db()
    origem, destino = sqlite3.connect(arquivo), sqlite3.connect(banco)
    origem.backup(destino)
    origem.close()
    destino.close()
    init_db(banco, current_app.config["PRAZO_DIAS"])  # atualiza backups feitos em versões antigas


def _seguro(valor):
    """Evita que o Excel execute como fórmula um texto que começa com = + - @."""
    return "'" + valor if isinstance(valor, str) and valor and valor[0] in "=+-@\t\r" else valor


_EXPORTACOES = {
    "livros": (["Título", "Autor", "ISBN", "Exemplares disponíveis", "Baixados", "Observação"],
               "SELECT livros.titulo, autores.nome, livros.isbn, livros.quantidade_disponivel, livros.baixados, "
               "livros.observacao FROM livros JOIN autores ON livros.autor_id = autores.id ORDER BY livros.titulo"),
    "pessoas": (["Tipo", "Nome", "E-mail", "Matrícula", "Turma", "Disciplina", "Situação"],
                "SELECT tipo, nome, email, matricula, turma, disciplina, "
                "CASE ativo WHEN 1 THEN 'Ativo' ELSE 'Arquivado' END FROM usuarios ORDER BY tipo, nome"),
    "emprestimos": (["Livro", "Pessoa", "Tipo", "Emprestado em", "Prazo", "Devolvido em", "Situação", "Estado na devolução", "Observações"],
                    "SELECT livros.titulo, usuarios.nome, usuarios.tipo, emprestimos.data_emprestimo, "
                    "emprestimos.data_prevista, emprestimos.data_devolucao, emprestimos.status, emprestimos.estado_devolucao, emprestimos.observacao "
                    "FROM emprestimos JOIN livros ON livros.id = emprestimos.livro_id "
                    "JOIN usuarios ON usuarios.id = emprestimos.usuario_id ORDER BY emprestimos.id DESC"),
}


def exportar(tabela):
    """Devolve (cabeçalho, linhas) prontos para virar CSV."""
    if tabela not in _EXPORTACOES:
        raise ErroNegocio("Exportação desconhecida.")
    cabecalho, sql = _EXPORTACOES[tabela]
    return cabecalho, [tuple(_seguro(v) for v in linha) for linha in get_db().execute(sql).fetchall()]


# ---------- Comportamento: quem e quais turmas entregam bem ----------
MIN_GENERO_PESSOA = 3  # abaixo disso o "gênero preferido" de uma pessoa é pouco mais que acaso
MIN_ENTREGAS = 2  # só entra no ranking quem (ou qual turma) tem pelo menos 2 devoluções


def _pct(parte, total):
    return round(100 * parte / total) if total else 0


def ranking():
    """Rankings de pessoas e turmas. 'Certa' = devolvida no prazo e sem defeito.
    Empréstimos antigos, sem estado registrado, contam como sem defeito."""
    db = get_db()
    todas = [dict(l) for l in db.execute(
        """SELECT u.nome, u.tipo, u.turma, COUNT(*) AS entregues,
                  SUM(CASE WHEN e.data_devolucao > e.data_prevista THEN 1 ELSE 0 END) AS atrasadas,
                  SUM(CASE WHEN e.estado_devolucao IN ('Com defeito', 'Perdido') THEN 1 ELSE 0 END) AS defeitos,
                  SUM(CASE WHEN e.data_devolucao <= e.data_prevista
                            AND COALESCE(e.estado_devolucao, 'Bom') NOT IN ('Com defeito', 'Perdido')
                           THEN 1 ELSE 0 END) AS certas
           FROM emprestimos e JOIN usuarios u ON u.id = e.usuario_id
           WHERE e.status = 'Devolvido' AND e.data_devolucao IS NOT NULL AND e.data_prevista IS NOT NULL
           GROUP BY u.id""")]
    soma = {c: sum(p[c] for p in todas) for c in ("entregues", "atrasadas", "defeitos", "certas")}
    geral = {"entregues": soma["entregues"],
             "pct_prazo": 100 - _pct(soma["atrasadas"], soma["entregues"]) if soma["entregues"] else 0,
             "pct_bom": 100 - _pct(soma["defeitos"], soma["entregues"]) if soma["entregues"] else 0,
             "pct_certas": _pct(soma["certas"], soma["entregues"])}
    turmas = {}
    for p in todas:  # soma os alunos de cada turma (professores não entram nas turmas)
        if p["tipo"] == "Aluno" and p["turma"]:
            t = turmas.setdefault(p["turma"], {"nome": p["turma"], "turma": "", "entregues": 0,
                                               "atrasadas": 0, "defeitos": 0, "certas": 0})
            for campo in ("entregues", "atrasadas", "defeitos", "certas"):
                t[campo] += p[campo]
    pessoas = [p for p in todas if p["entregues"] >= MIN_ENTREGAS]
    turmas = [t for t in turmas.values() if t["entregues"] >= MIN_ENTREGAS]
    for x in pessoas + turmas:
        x["pct_atrasos"] = _pct(x["atrasadas"], x["entregues"])
        x["pct_defeitos"] = _pct(x["defeitos"], x["entregues"])
        x["pct_certas"] = _pct(x["certas"], x["entregues"])
        x["pct_problemas"] = 100 - x["pct_certas"]  # atrasada ou com defeito
    top = lambda itens, pct, qtd: sorted(itens, key=lambda x: (-x[pct], -x[qtd], x["nome"]))[:5]
    emprestam = []
    for l in db.execute(
            """SELECT u.turma AS nome, COUNT(*) AS total,
                      (SELECT COUNT(*) FROM usuarios x WHERE x.tipo = 'Aluno' AND x.ativo = 1
                       AND x.turma = u.turma) AS alunos
               FROM emprestimos e JOIN usuarios u ON u.id = e.usuario_id
               WHERE u.tipo = 'Aluno' AND u.turma IS NOT NULL
               GROUP BY u.turma ORDER BY total DESC, u.turma LIMIT 5"""):
        emprestam.append({**dict(l), "media": round(l["total"] / l["alunos"], 1) if l["alunos"] else 0})
    return {
        "min_entregas": MIN_ENTREGAS,
        "geral": geral,
        "pessoas_atrasos": top([p for p in pessoas if p["atrasadas"]], "pct_atrasos", "atrasadas"),
        "pessoas_defeitos": top([p for p in pessoas if p["defeitos"]], "pct_defeitos", "defeitos"),
        "pessoas_certas": top([p for p in pessoas if p["certas"]], "pct_certas", "certas"),
        "turmas_emprestam": emprestam,
        "turmas_problemas": top([t for t in turmas if t["certas"] < t["entregues"]], "pct_problemas", "entregues"),
        "turmas_certas": top([t for t in turmas if t["certas"]], "pct_certas", "entregues"),
    }


# ---------- Gêneros mais lidos ----------
def _ranking_generos(db, filtro="", params=()):
    """Empréstimos por gênero (devolvidos ou ainda em aberto). Livro sem gênero fica de fora do ranking,
    mas é contado à parte para mostrar quanto da leitura ainda não dá para classificar."""
    linhas = db.execute(
        f"""SELECT livros.genero AS genero, COUNT(*) AS emprestimos,
                   COUNT(DISTINCT emprestimos.livro_id) AS titulos,
                   COUNT(DISTINCT emprestimos.usuario_id) AS leitores
            FROM emprestimos JOIN livros ON livros.id = emprestimos.livro_id
            WHERE livros.genero IS NOT NULL {filtro}
            GROUP BY livros.genero ORDER BY emprestimos DESC, livros.genero""", params).fetchall()
    sem = db.execute(
        f"SELECT COUNT(*) FROM emprestimos JOIN livros ON livros.id = emprestimos.livro_id "
        f"WHERE livros.genero IS NULL {filtro}", params).fetchone()[0]
    total = sum(l["emprestimos"] for l in linhas)
    return {"itens": [{**dict(l), "pct": _pct(l["emprestimos"], total)} for l in linhas],
            "total": total, "sem_genero": sem}


def generos_mais_lidos():
    """Retrato da biblioteca inteira. Não traz nomes de pessoas de propósito (ver generos_da_pessoa)."""
    db = get_db()
    geral = _ranking_generos(db)
    geral["livros_sem_genero"] = db.execute("SELECT COUNT(*) FROM livros WHERE genero IS NULL").fetchone()[0]
    geral["titulos"] = db.execute("SELECT COUNT(*) FROM livros").fetchone()[0]
    return geral


def generos_da_pessoa(usuario_id):
    """Gêneros que uma pessoa mais pegou emprestado. Fica numa página própria, aberta por pessoa, e não
    numa lista com todo mundo: é o hábito de leitura de alguém (muitas vezes um menor de idade)."""
    pessoa = obter_pessoa(usuario_id)
    r = _ranking_generos(get_db(), "AND emprestimos.usuario_id = ?", (usuario_id,))
    r["pessoa"] = pessoa
    r["emprestimos"] = r["total"] + r["sem_genero"]
    r["confiavel"] = r["total"] >= MIN_GENERO_PESSOA
    r["min"] = MIN_GENERO_PESSOA
    return r

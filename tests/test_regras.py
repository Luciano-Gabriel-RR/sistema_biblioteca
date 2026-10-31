import os
import tempfile
import unittest
from werkzeug.datastructures import MultiDict
from datetime import datetime, timedelta

from biblioteca import create_app
from biblioteca import services as s


class Base(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.app = create_app(os.path.join(self.pasta.name, "teste.db"))
        self.ctx = self.app.app_context()
        self.ctx.push()
        for n in "123":
            s.salvar_livro(f"Livro {n}", n, "Autor", 3)
        s.salvar_pessoa("Aluno", "Ana", "ana@x.com", "8º ano A", "")

    def tearDown(self):
        self.ctx.pop()
        self.pasta.cleanup()


class TestRegras(Base):
    def test_limite_de_livros_do_aluno(self):
        s.emprestar(1, 1)
        s.emprestar(2, 1)
        with self.assertRaises(s.ErroNegocio):
            s.emprestar(3, 1)

    def test_atrasado_bloqueia_e_devolucao_vai_para_o_historico(self):
        s.emprestar(1, 1)
        db = s.get_db()
        db.execute("UPDATE emprestimos SET data_prevista = '2020-01-01'")
        db.commit()
        with self.assertRaises(s.ErroNegocio):
            s.emprestar(2, 1)
        s.devolver(1)
        s.emprestar(2, 1)  # liberado depois de devolver
        antigo = [x for x in s.historico() if x["id"] == 1][0]
        self.assertEqual(antigo["status"], "Devolvido")
        self.assertIsNotNone(antigo["data_devolucao"])

    def test_renovar_so_uma_vez(self):
        s.emprestar(1, 1)
        s.renovar(1)
        with self.assertRaises(s.ErroNegocio):
            s.renovar(1)

    def test_nao_arquiva_quem_tem_livro_e_nao_exclui_com_historico(self):
        s.emprestar(1, 1)
        with self.assertRaises(s.ErroNegocio):
            s.alternar_ativo(1)
        s.devolver(1)
        with self.assertRaises(s.ErroNegocio):
            s.excluir_pessoa(1)
        s.alternar_ativo(1)
        with self.assertRaises(s.ErroNegocio):
            s.emprestar(1, 1)  # cadastro arquivado


class TestAcesso(Base):
    def test_exige_login_e_csrf(self):
        c = self.app.test_client()
        self.assertEqual(c.get("/").status_code, 302)  # vai para criar/entrar
        self.assertEqual(c.post("/livros", data={}).status_code, 400)  # sem token CSRF


class TestNovidades(Base):
    def test_relatorio_de_atrasados_agrupa_por_turma(self):
        s.emprestar(1, 1)
        db = s.get_db()
        db.execute("UPDATE emprestimos SET data_prevista = '2020-01-01'")
        db.commit()
        atrasos = s.atrasados()
        self.assertEqual((len(atrasos), atrasos[0]["grupo"]), (1, "8º ano A"))
        self.assertGreater(atrasos[0]["dias"], 0)

    def test_prazo_por_tipo(self):
        self.app.config["PRAZOS"] = {"Aluno": 7, "Professor": 30}
        prevista = s.emprestar(1, 1)
        esperado = (datetime.now() + timedelta(days=7)).strftime("%d/%m/%Y")
        self.assertEqual(prevista, esperado)


class TestReservasViradaPaginas(Base):
    def test_fila_de_reservas_separa_o_exemplar(self):
        s.salvar_livro("Raro", "9", "Autor", 1)           # id 4, um exemplar só
        s.salvar_pessoa("Aluno", "Bia", "bia@x.com", "9º ano A", "")   # id 2
        s.salvar_pessoa("Aluno", "Cid", "cid@x.com", "9º ano A", "")   # id 3
        s.emprestar(4, 1)
        with self.assertRaises(s.ErroNegocio):
            s.reservar(1, 2)                               # livro 1 tem exemplar livre
        s.reservar(4, 2)
        with self.assertRaises(s.ErroNegocio):
            s.renovar(1)                                   # há fila: não renova
        s.devolver(1)                                      # exemplar vai para a Bia
        with self.assertRaises(s.ErroNegocio):
            s.emprestar(4, 3)                              # Cid não pega o exemplar reservado
        s.emprestar(4, 2)                                  # Bia pega
        self.assertEqual(s.reservas_abertas(), [])

    def test_virada_de_ano_sem_mover_duas_vezes(self):
        s.salvar_pessoa("Aluno", "Bia", "bia@x.com", "9º ano A", "")
        movidos, arquivados, pendentes = s.virar_ano([("8º ano A", "9º ano A"), ("9º ano A", "1º ano EM A")])
        self.assertEqual((movidos, arquivados, pendentes), (2, 0, []))
        self.assertEqual((s.obter_pessoa(1)["turma"], s.obter_pessoa(2)["turma"]), ("9º ano A", "1º ano EM A"))
        s.emprestar(1, 1)
        # Ana tem livro: não é arquivada, e o resultado diz QUEM e de qual turma
        self.assertEqual(s.virar_ano([("9º ano A", ""), ("1º ano EM A", "")]), (0, 1, ["Ana (9º ano A)"]))
        self.assertEqual(s.sugerir_turma("8º ano A"), "9º ano")

    def test_paginacao(self):
        for n in range(25):
            s.salvar_livro(f"T{n}", f"x{n}", "A", 1)
        pagina = s.buscar_livros("", 2)
        self.assertEqual((pagina["total"], pagina["paginas"], len(pagina["itens"])), (28, 2, 8))


class TestDiaADia(Base):
    def test_baixas(self):
        s.baixar_exemplar(1, "Perdido", "sumiu")
        self.assertEqual((s.obter_livro(1)["quantidade_disponivel"], s.obter_livro(1)["baixados"]), (2, 1))
        s.emprestar(2, 1)
        s.baixar_emprestimo(1, "aluno perdeu")
        self.assertEqual(s.obter_livro(2)["quantidade_disponivel"], 2)  # exemplar não volta ao estoque
        self.assertEqual(s.historico()[0]["status"], "Devolvido")
        self.assertEqual(len(s.baixas_do_livro(2)), 1)

    def test_observacoes_e_matricula(self):
        s.emprestar(1, 1, "capa solta")
        s.devolver(1, "ok")
        self.assertEqual(s.historico()[0]["observacao"], "capa solta | Devolução: ok")
        s.salvar_pessoa("Aluno", "Bia", "b@x.com", "8º ano A", "", matricula="123")
        with self.assertRaises(s.ErroNegocio):
            s.salvar_pessoa("Aluno", "Cid", "c@x.com", "8º ano A", "", matricula="123")

    def test_reserva_expira_e_passa_ao_proximo(self):
        s.salvar_livro("Raro", "9", "Autor", 1)  # id 4
        s.salvar_pessoa("Aluno", "Bia", "b@x.com", "9º ano A", "")  # id 2
        s.emprestar(4, 1)
        s.reservar(4, 2)
        s.devolver(1)
        self.assertEqual(s.reservas_abertas()[0]["status"], "Disponivel")
        db = s.get_db()
        db.execute("UPDATE reservas SET data_limite = '2020-01-01'")
        db.commit()
        self.assertEqual(s.expirar_reservas(), 1)
        self.assertEqual(s.reservas_abertas(), [])

    def test_backup_restaurar_exportar_painel(self):
        arquivo = s.fazer_backup("teste")
        s.salvar_pessoa("Aluno", "Bia", "b@x.com", "8º ano A", "")
        self.assertEqual(len(s.listar_pessoas()), 2)
        s.restaurar_backup(arquivo.name)
        self.assertEqual(len(s.listar_pessoas()), 1)
        with self.assertRaises(s.ErroNegocio):
            s.restaurar_backup("../x.db")
        s.salvar_livro("=SOMA(1)", "77", "A", 1)
        _, linhas = s.exportar("livros")
        self.assertTrue(any(l[0] == "'=SOMA(1)" for l in linhas))
        self.assertEqual(s.painel()["titulos"], 4)


class TestRegrasNovas(Base):
    def test_mesmo_isbn_soma_exemplares_e_recusa_outro_livro(self):
        mensagem = s.salvar_livro("livro 1", "1", "autor", 2)  # mesmo título e autor, outra grafia
        self.assertIn("somei 2", mensagem)
        self.assertEqual(s.obter_livro(1)["quantidade_disponivel"], 5)
        s.salvar_livro("Livro 1", "1", "Autor", 1)
        self.assertEqual(s.obter_livro(1)["quantidade_disponivel"], 6)
        with self.assertRaises(s.ErroNegocio):
            s.salvar_livro("Outro título", "1", "Autor", 1)
        s.salvar_livro("Livro 4", "978-85-359", "Autor", 1)
        self.assertIn("somei", s.salvar_livro("Livro 4", "97885359", "Autor", 1))  # hifens não contam

    def test_uma_reserva_por_pessoa(self):
        s.salvar_livro("Raro", "9", "Autor", 1)   # id 4
        s.salvar_livro("Raro 2", "8", "Autor", 1)  # id 5
        s.salvar_pessoa("Aluno", "Bia", "b@x.com", "8º ano A", "")  # id 2
        s.emprestar(4, 1)
        s.emprestar(5, 1)
        s.reservar(4, 2)
        with self.assertRaises(s.ErroNegocio):
            s.reservar(4, 2)  # mesmo livro de novo
        with self.assertRaises(s.ErroNegocio):
            s.reservar(5, 2)  # outro livro
        s.cancelar_reserva(1)
        s.reservar(5, 2)      # liberada depois de cancelar

    def test_professor_nao_tem_matricula(self):
        s.salvar_pessoa("Professor", "Paulo", "p@x.com", "", "Matemática", matricula="999")
        self.assertIsNone(s.obter_pessoa(2)["matricula"])


class TestComportamento(Base):
    def _entregar(self, pessoa, livro, estado="Bom", atrasado=False):
        s.emprestar(livro, pessoa)
        emprestimo = s.get_db().execute("SELECT MAX(id) FROM emprestimos").fetchone()[0]
        if atrasado:
            s.get_db().execute("UPDATE emprestimos SET data_prevista = '2020-01-01' WHERE id = ?", (emprestimo,))
            s.get_db().commit()
        s.devolver(emprestimo, "", estado)

    def test_rankings_de_pessoas_e_turmas(self):
        s.salvar_pessoa("Aluno", "Bia", "b@x.com", "8º ano A", "")   # id 2
        s.salvar_pessoa("Aluno", "Cid", "c@x.com", "9º ano B", "")   # id 3
        self._entregar(1, 1)                                   # Ana: uma certa, uma atrasada
        self._entregar(1, 2, atrasado=True)
        self._entregar(2, 1, "Com defeito")                    # Bia: sempre com defeito
        self._entregar(2, 2, "Com defeito")
        self._entregar(3, 1)                                   # Cid: tudo certo
        self._entregar(3, 2)
        r = s.ranking()
        self.assertEqual(r["pessoas_atrasos"][0]["nome"], "Ana")
        self.assertEqual((r["pessoas_defeitos"][0]["nome"], r["pessoas_defeitos"][0]["pct_defeitos"]), ("Bia", 100))
        self.assertEqual((r["pessoas_certas"][0]["nome"], r["pessoas_certas"][0]["pct_certas"]), ("Cid", 100))
        self.assertEqual(r["turmas_emprestam"][0]["nome"], "8º ano A")
        self.assertEqual(r["turmas_emprestam"][0]["total"], 4)
        self.assertEqual(r["turmas_problemas"][0]["nome"], "8º ano A")
        self.assertEqual((r["turmas_certas"][0]["nome"], r["turmas_certas"][0]["pct_certas"]), ("9º ano B", 100))

    def test_estado_invalido_e_perdido_conta_como_defeito(self):
        s.emprestar(1, 1)
        with self.assertRaises(s.ErroNegocio):
            s.devolver(1, "", "Ótimo")
        s.baixar_emprestimo(1, "sumiu")
        self.assertEqual(s.historico()[0]["estado_devolucao"], "Perdido")


class TestTurmas(Base):
    def test_so_series_do_8_ano_ao_3_ano_em(self):
        for turma in ("7º ano A", "6º ano", "4º ano EM", "turma x", ""):
            with self.assertRaises(s.ErroNegocio):
                s.salvar_pessoa("Aluno", "X", "x@x.com", turma, "")
        s.salvar_pessoa("Aluno", "Bia", "b@x.com", "9º ano b", "")       # letra vira maiúscula
        s.salvar_pessoa("Aluno", "Cid", "c@x.com", "1º ano EM", "")      # letra é opcional
        self.assertEqual((s.obter_pessoa(2)["turma"], s.obter_pessoa(3)["turma"]), ("9º ano B", "1º ano EM"))
        self.assertEqual(s.separar_turma("2º ano EM C"), ("2º ano EM", "C"))

    def test_virada_segue_a_sequencia_e_arquiva_o_3_ano(self):
        self.assertEqual([s.sugerir_turma(t) for t in ("8º ano A", "9º ano B", "1º ano EM", "3º ano EM A", "7º ano A")],
                         ["9º ano", "1º ano EM", "2º ano EM", "", "__manter__"])
        with self.assertRaises(s.ErroNegocio):
            s.virar_ano([("8º ano A", "5º ano")])  # destino fora das séries da escola

    def test_emprestimos_ativos_trazem_a_turma(self):
        s.emprestar(1, 1)
        self.assertEqual(s.emprestimos_ativos()[0]["usuario_turma"], "8º ano A")


class TestPrograma(Base):
    def test_sem_dialogos_do_navegador_e_encerrar_so_no_modo_programa(self):
        import pathlib
        pasta = pathlib.Path(__file__).resolve().parent.parent / "biblioteca" / "templates"
        for arquivo in pasta.glob("*.html"):
            texto = arquivo.read_text(encoding="utf-8")
            self.assertNotIn("confirm(", texto, arquivo.name)  # as confirmações são janelas do próprio sistema
            self.assertNotIn("prompt(", texto, arquivo.name)
        banco = s.get_db()
        banco.execute("INSERT INTO bibliotecarios (usuario, senha_hash) VALUES ('t', 'x')")
        banco.commit()
        cliente = self.app.test_client()
        with cliente.session_transaction() as sessao:
            sessao["csrf"], sessao["bibliotecario"] = "t", "t"  # entra como bibliotecário
        self.assertEqual(cliente.post("/encerrar", data={"csrf_token": "t"}).status_code, 404)  # fora do modo programa


class TestPing(Base):
    def test_ping_nao_exige_login_e_marca_a_janela_como_aberta(self):
        cliente = self.app.test_client()
        resposta = cliente.get("/ping")
        self.assertEqual(resposta.status_code, 204)
        self.assertIn("ULTIMO_PING", self.app.config)


class TestMelhoriasDeUso(Base):
    def test_dias_restantes_para_o_semaforo_de_prazos(self):
        s.emprestar(1, 1)
        s.emprestar(2, 1)
        db = s.get_db()
        db.execute("UPDATE emprestimos SET data_prevista = date('now', 'localtime', '-5 day') WHERE id = 1")
        db.execute("UPDATE emprestimos SET data_prevista = date('now', 'localtime', '+2 day') WHERE id = 2")
        db.commit()
        dias = {e["id"]: e["dias_restantes"] for e in s.emprestimos_ativos()}
        self.assertEqual((dias[1], dias[2]), (-5, 2))

    def test_formulario_mantem_o_que_foi_digitado_quando_ha_erro(self):
        banco = s.get_db()
        banco.execute("INSERT INTO bibliotecarios (usuario, senha_hash) VALUES ('t', 'x')")
        banco.commit()
        cliente = self.app.test_client()
        with cliente.session_transaction() as sessao:
            sessao["csrf"], sessao["bibliotecario"] = "t", "t"
        cliente.post("/livros", data={"csrf_token": "t", "titulo": "Outro nome", "isbn": "1", "quantidade": "3",
                                      "autor": "Fulano", "observacao": "capa dura"})  # ISBN 1 já é de "Livro 1"
        pagina = cliente.get("/").data.decode()
        for valor in ("Outro nome", "Fulano", "capa dura"):
            self.assertIn(f'value="{valor}"', pagina)
        self.assertNotIn('value="Outro nome"', cliente.get("/").data.decode())  # o rascunho é usado uma vez só


class TestBalcaoEBusca(Base):
    def _logar(self):
        banco = s.get_db()
        banco.execute("INSERT INTO bibliotecarios (usuario, senha_hash) VALUES ('t', 'x')")
        banco.commit()
        cliente = self.app.test_client()
        with cliente.session_transaction() as sessao:
            sessao["csrf"], sessao["bibliotecario"] = "t", "t"
        return cliente

    def test_busca_de_pessoas_por_nome_turma_e_matricula(self):
        s.salvar_pessoa("Aluno", "Bia Lima", "bia@x.com", "9º ano B", "", matricula="555")
        s.salvar_pessoa("Professor", "Paulo", "p@x.com", "", "História")
        self.assertEqual([p["nome"] for p in s.listar_pessoas(None, "bia")], ["Bia Lima"])
        self.assertEqual(len(s.listar_pessoas(None, "8º ano A")), 1)           # Ana
        self.assertEqual([p["nome"] for p in s.listar_pessoas(None, "555")], ["Bia Lima"])
        self.assertEqual(len(s.listar_pessoas(None, "")), 3)                    # sem busca: todos
        self.assertEqual([p["nome"] for p in s.listar_pessoas(None, "história")], ["Paulo"])  # ignora maiúsculas

    def test_emprestimos_da_pessoa_so_traz_os_dela(self):
        s.salvar_pessoa("Aluno", "Bia", "bia@x.com", "8º ano A", "")
        s.emprestar(1, 1)
        s.emprestar(2, 2)
        self.assertEqual([e["usuario_nome"] for e in s.emprestimos_da_pessoa(1)], ["Ana"])
        self.assertEqual(len(s.emprestimos_da_pessoa(2)), 1)

    def test_balcao_mostra_pessoa_e_livros_disponiveis(self):
        cliente = self._logar()
        pagina = cliente.get("/balcao?qp=ana").data.decode()
        self.assertIn("Ana", pagina)
        self.assertIn("pessoa=1", pagina)            # resultado com link para atender
        atendimento = cliente.get("/balcao?pessoa=1").data.decode()
        self.assertIn("Pegar um livro emprestado", atendimento)
        self.assertIn('name="voltar" value="balcao"', atendimento)

    def test_acoes_do_balcao_voltam_para_o_balcao(self):
        cliente = self._logar()
        r = cliente.post("/emprestimos", data={"csrf_token": "t", "voltar": "balcao", "pessoa_id": "1",
                                               "usuario_id": "1", "livro_id": "1"})
        self.assertEqual(r.headers["Location"], "/balcao?pessoa=1")
        self.assertEqual(len(s.emprestimos_da_pessoa(1)), 1)
        r = cliente.post("/emprestimos/1/devolver", data={"csrf_token": "t", "voltar": "balcao", "pessoa_id": "1",
                                                          "estado": "Com defeito"})
        self.assertEqual(r.headers["Location"], "/balcao?pessoa=1")
        self.assertEqual(s.historico()[0]["estado_devolucao"], "Com defeito")

    def test_erro_no_balcao_volta_para_o_balcao_com_aviso(self):
        cliente = self._logar()
        s.emprestar(1, 1)
        s.emprestar(2, 1)                             # limite de 2 livros do aluno
        r = cliente.post("/emprestimos", data={"csrf_token": "t", "voltar": "balcao", "pessoa_id": "1",
                                               "usuario_id": "1", "livro_id": "3"})
        self.assertEqual(r.headers["Location"], "/balcao?pessoa=1")
        self.assertIn("limite", cliente.get("/balcao?pessoa=1").data.decode().lower())

    def test_acoes_do_balcao_exigem_csrf(self):
        cliente = self._logar()
        self.assertEqual(cliente.post("/emprestimos", data={"voltar": "balcao", "usuario_id": "1", "livro_id": "1"}).status_code, 400)
        self.assertEqual(cliente.post("/emprestimos/1/devolver", data={"voltar": "balcao"}).status_code, 400)

    def test_busca_de_pessoas_na_pagina_inicial(self):
        cliente = self._logar()
        s.salvar_pessoa("Aluno", "Bia", "bia@x.com", "8º ano A", "")
        pagina = cliente.get("/?qp=ana").data.decode()
        self.assertIn('value="ana"', pagina)
        self.assertIn('<div class="nome-principal">Ana</div>', pagina)   # linha da tabela
        self.assertNotIn('<div class="nome-principal">Bia</div>', pagina) # filtro exclui os demais


class _Logado(Base):
    """Base para testes de tela: entrega um cliente já logado (token CSRF fixo "t")."""

    def _logar(self):
        banco = s.get_db()
        banco.execute("INSERT INTO bibliotecarios (usuario, senha_hash) VALUES ('t', 'x')")
        banco.commit()
        cliente = self.app.test_client()
        with cliente.session_transaction() as sessao:
            sessao["csrf"], sessao["bibliotecario"] = "t", "t"
        return cliente


class TestSugestoes(_Logado):
    """Sugestões de livros novos para a biblioteca."""

    # ----- regras -----
    def test_registrar_limpa_os_campos_e_lista_pendentes_primeiro(self):
        s.salvar_sugestao("  Grande   Sertão: Veredas ", "João Guimarães Rosa", "978-85-359-0277-5", " vestibular ", "Prof. Helena")
        s.salvar_sugestao("Laranja Mecânica", "Anthony Burgess")
        s.alternar_sugestao(1)  # a primeira vira Adquirida
        lista = s.listar_sugestoes()
        self.assertEqual([x["titulo"] for x in lista], ["Laranja Mecânica", "Grande Sertão: Veredas"])  # pendente antes
        antiga = s.obter_sugestao(1)
        self.assertEqual((antiga["isbn"], antiga["motivo"], antiga["sugerido_por"], antiga["status"]),
                         ("9788535902775", "vestibular", "Prof. Helena", "Adquirida"))
        self.assertEqual(s.obter_sugestao(2)["data_sugestao"], datetime.now().strftime("%Y-%m-%d"))

    def test_titulo_e_autor_sao_obrigatorios(self):
        for titulo, autor in (("", "Autor"), ("Título", "  "), ("", "")):
            with self.assertRaises(s.ErroNegocio):
                s.salvar_sugestao(titulo, autor)
        self.assertEqual(len(s.listar_sugestoes()), 0)

    def test_recusa_livro_que_ja_esta_no_acervo(self):
        with self.assertRaises(s.ErroNegocio) as e:
            s.salvar_sugestao("Outro nome", "Outro autor", "1")            # ISBN do "Livro 1"
        self.assertIn("já está no acervo", str(e.exception))
        with self.assertRaises(s.ErroNegocio):
            s.salvar_sugestao("livro 2", "AUTOR")                          # mesmo título e autor, sem ISBN
        self.assertEqual(len(s.listar_sugestoes()), 0)

    def test_mesmo_livro_por_outra_pessoa_vira_mais_um_pedido(self):
        s.salvar_sugestao("Laranja Mecânica", "Anthony Burgess", "555", sugerido_por="Prof. Marcos")
        msg = s.salvar_sugestao("LARANJA MECÂNICA", "anthony burgess", sugerido_por="Ana")   # outra grafia
        self.assertIn("agora são 2", msg)
        self.assertIn("agora são 3", s.salvar_sugestao("Título diferente", "Fulano", "5-5-5"))  # mesmo ISBN, sem nome
        self.assertEqual(len(s.listar_sugestoes()), 3)

    def test_a_mesma_pessoa_nao_pede_o_mesmo_livro_duas_vezes(self):
        s.salvar_sugestao("Laranja Mecânica", "Anthony Burgess", sugerido_por="Ana Souza")
        with self.assertRaises(s.ErroNegocio) as e:
            s.salvar_sugestao("laranja mecânica", "ANTHONY BURGESS", sugerido_por="  ana souza ")
        self.assertIn("já sugeriu", str(e.exception))
        s.alternar_sugestao(1)                                              # adquirida: pode pedir de novo
        s.salvar_sugestao("Laranja Mecânica", "Anthony Burgess", sugerido_por="Ana Souza")
        self.assertEqual(len(s.listar_sugestoes()), 2)

    def test_editar_mantem_data_e_situacao_e_nao_conflita_consigo_mesma(self):
        s.salvar_sugestao("Rascunho", "Autor X")
        s.salvar_sugestao("Outro", "Autor Y")
        s.alternar_sugestao(1)
        s.salvar_sugestao("Rascunho corrigido", "Autor X", sugestao_id=1)
        editada = s.obter_sugestao(1)
        self.assertEqual((editada["titulo"], editada["status"]), ("Rascunho corrigido", "Adquirida"))
        s.alternar_sugestao(1)
        s.salvar_sugestao("Rascunho corrigido", "Autor X", "9", sugestao_id=1)  # regravar com o mesmo título: ok
        s.salvar_sugestao("Outro", "Autor Y", sugestao_id=1)                   # igual à 2, mas de outra pessoa: vira pedido extra
        s.salvar_sugestao("Outro", "Autor Y", sugerido_por="Beto")
        with self.assertRaises(s.ErroNegocio):
            s.salvar_sugestao("Outro", "Autor Y", sugerido_por="beto", sugestao_id=1)  # mesma pessoa da outra sugestão
        with self.assertRaises(s.ErroNegocio):
            s.salvar_sugestao("Qualquer", "Autor", sugestao_id=99)             # não existe

    def test_alternar_e_excluir(self):
        s.salvar_sugestao("Livro novo", "Autor Z")
        self.assertEqual(s.alternar_sugestao(1), "adquirida")
        self.assertEqual(s.alternar_sugestao(1), "pendente")
        s.excluir_sugestao(1)
        self.assertEqual(len(s.listar_sugestoes()), 0)
        for acao in (s.alternar_sugestao, s.excluir_sugestao):
            with self.assertRaises(s.ErroNegocio):
                acao(1)

    def test_busca_filtro_e_paginacao(self):
        s.salvar_sugestao("Laranja Mecânica", "Anthony Burgess", sugerido_por="Prof. Marcos")
        s.salvar_sugestao("Ensaio sobre a Cegueira", "José Saramago", "777")
        s.alternar_sugestao(2)
        achados = lambda busca="", status="": [x["titulo"] for x in s.listar_sugestoes(busca, status)]
        self.assertEqual(achados("burgess"), ["Laranja Mecânica"])
        self.assertEqual(achados("marcos"), ["Laranja Mecânica"])          # quem sugeriu
        self.assertEqual(achados("777"), ["Ensaio sobre a Cegueira"])      # ISBN
        self.assertEqual(achados(status="Adquirida"), ["Ensaio sobre a Cegueira"])
        self.assertEqual(achados(status="Pendente"), ["Laranja Mecânica"])
        self.assertEqual(len(achados(status="qualquer coisa")), 2)         # filtro inválido = todas
        for n in range(25):
            s.salvar_sugestao(f"Título {n}", f"Autor {n}")
        pagina = s.listar_sugestoes("", "", 2)
        self.assertEqual((pagina["total"], pagina["paginas"], len(pagina["itens"])), (27, 2, 7))

    def test_banco_antigo_sem_a_tabela_ganha_a_tabela(self):
        from biblioteca import db as camada
        banco = s.get_db()
        banco.execute("DROP TABLE sugestoes")
        banco.commit()
        camada.init_db(self.app.config["DATABASE"], 30)                    # o que acontece ao abrir o sistema
        s.salvar_sugestao("Livro novo", "Autor Z")
        self.assertEqual(len(s.listar_sugestoes()), 1)

    # ----- telas -----
    def test_exige_login_e_csrf(self):
        anonimo = self.app.test_client()
        self.assertEqual(anonimo.get("/sugestoes/1/editar").status_code, 302)
        self.assertEqual(anonimo.get("/imprimir/sugestoes").status_code, 302)
        cliente = self._logar()
        for rota in ("/sugestoes", "/sugestoes/1/situacao", "/sugestoes/1/excluir"):
            self.assertEqual(cliente.post(rota, data={"titulo": "x", "autor": "y"}).status_code, 400, rota)  # sem token

    def test_fluxo_completo_pelas_telas(self):
        cliente = self._logar()
        dados = {"csrf_token": "t", "titulo": "Laranja Mecânica", "autor": "Anthony Burgess",
                 "isbn": "", "sugerido_por": "Prof. Marcos", "motivo": "clássico distópico"}
        r = cliente.post("/sugestoes", data=dados)
        self.assertEqual(r.headers["Location"], "/?novo=sugestao#sugestoes")       # janela reabre para a próxima
        pagina = cliente.get("/").data.decode()
        for texto in ("Laranja Mecânica", "Anthony Burgess", "Prof. Marcos", "clássico distópico", "Marcar adquirida"):
            self.assertIn(texto, pagina)
        aba = pagina.split('id="sugestoes" role="tabpanel"')[1].split("<!-- =====")[0]  # só a aba de sugestões
        self.assertTrue('<form action="/sugestoes/1/excluir"' in aba, "Excluir da sugestão não foi desenhado como botão")
        self.assertFalse("&lt;" in aba, "o menu da linha (⋯) das sugestões saiu com HTML escapado")

        self.assertEqual(cliente.get("/sugestoes/1/editar").status_code, 200)
        cliente.post("/sugestoes/1/editar", data={**dados, "csrf_token": "t", "titulo": "A Laranja Mecânica"})
        self.assertIn("A Laranja Mecânica", cliente.get("/").data.decode())

        cliente.post("/sugestoes/1/situacao", data={"csrf_token": "t"})
        self.assertEqual(s.obter_sugestao(1)["status"], "Adquirida")
        self.assertIn("Reabrir", cliente.get("/").data.decode())
        self.assertIn("Nenhum registro", cliente.get("/imprimir/sugestoes").data.decode())  # só pendentes são impressos
        cliente.post("/sugestoes/1/situacao", data={"csrf_token": "t"})
        self.assertIn("A Laranja Mecânica", cliente.get("/imprimir/sugestoes").data.decode())

        cliente.post("/sugestoes/1/excluir", data={"csrf_token": "t"})
        self.assertEqual(len(s.listar_sugestoes()), 0)
        self.assertEqual(cliente.get("/sugestoes/1/editar").status_code, 302)       # já não existe: volta à lista

    def test_erro_ao_sugerir_mantem_o_que_foi_digitado(self):
        cliente = self._logar()
        cliente.post("/sugestoes", data={"csrf_token": "t", "titulo": "Livro 1", "autor": "Autor", "isbn": "",
                                         "sugerido_por": "Aluno Beto", "motivo": ""})  # já está no acervo
        pagina = cliente.get("/").data.decode()
        self.assertIn('value="Aluno Beto"', pagina)
        self.assertNotIn('value="Aluno Beto"', cliente.get("/").data.decode())   # rascunho usado uma vez só
        self.assertEqual(len(s.listar_sugestoes()), 0)

    def test_busca_pela_pagina_inicial(self):
        cliente = self._logar()
        s.salvar_sugestao("Laranja Mecânica", "Anthony Burgess")
        s.salvar_sugestao("Ensaio sobre a Cegueira", "José Saramago")
        pagina = cliente.get("/?qs=saramago&ss=Pendente").data.decode()
        aba = pagina.split('id="sugestoes" role="tabpanel"')[1].split("<!-- =====")[0]
        self.assertIn('<div class="nome-principal">Ensaio sobre a Cegueira</div>', aba)
        self.assertNotIn('<div class="nome-principal">Laranja Mecânica</div>', aba)


def _aba(pagina, aba_id):
    """Trecho do HTML de uma aba da página inicial."""
    return pagina.split(f'id="{aba_id}" role="tabpanel"')[1].split("<!-- =====")[0]


class TestMaisSugeridos(_Logado):
    """Ranking dos livros mais pedidos (sugestões pendentes agrupadas por livro)."""

    def test_agrupa_o_mesmo_livro_e_ordena_pelo_numero_de_pedidos(self):
        s.salvar_sugestao("Ensaio sobre a Cegueira", "José Saramago", sugerido_por="Ana")
        s.salvar_sugestao("Laranja Mecânica", "Anthony Burgess", sugerido_por="Prof. Marcos")
        s.salvar_sugestao("laranja mecânica", "ANTHONY BURGESS", sugerido_por="Beto")
        s.salvar_sugestao("Laranja Mecânica", "Anthony Burgess")                 # pedido sem nome
        ranking = s.mais_sugeridos()
        self.assertEqual([(g["titulo"], g["votos"]) for g in ranking],
                         [("Laranja Mecânica", 3), ("Ensaio sobre a Cegueira", 1)])
        self.assertEqual((ranking[0]["pedidos"], ranking[0]["sem_nome"]), (["Prof. Marcos", "Beto"], 1))
        self.assertEqual(ranking[0]["ids"], [2, 3, 4])

    def test_mesmo_isbn_une_grafias_diferentes(self):
        s.salvar_sugestao("Laranja Mecânica", "Anthony Burgess", "555", sugerido_por="Ana")
        s.salvar_sugestao("A Laranja Mecânica", "A. Burgess", "5-5-5", sugerido_por="Beto")
        ranking = s.mais_sugeridos()
        self.assertEqual((len(ranking), ranking[0]["votos"]), (1, 2))

    def test_adquiridas_saem_do_ranking(self):
        s.salvar_sugestao("Laranja Mecânica", "Anthony Burgess", sugerido_por="Ana")
        s.salvar_sugestao("Ensaio sobre a Cegueira", "José Saramago", sugerido_por="Ana")
        s.alternar_sugestao(1)
        self.assertEqual([g["titulo"] for g in s.mais_sugeridos()], ["Ensaio sobre a Cegueira"])

    def test_empate_vai_para_ordem_alfabetica_e_o_limite_vale(self):
        for titulo in ("Bravo", "Alfa", "Charlie"):
            s.salvar_sugestao(titulo, "Autor Z")
        self.assertEqual([g["titulo"] for g in s.mais_sugeridos()], ["Alfa", "Bravo", "Charlie"])
        self.assertEqual(len(s.mais_sugeridos(limite=2)), 2)

    def test_adquirir_todas_as_sugestoes_do_livro(self):
        s.salvar_sugestao("Laranja Mecânica", "Anthony Burgess", sugerido_por="Ana")
        s.salvar_sugestao("Laranja Mecânica", "Anthony Burgess", sugerido_por="Beto")
        s.salvar_sugestao("Outro livro", "Fulano")
        self.assertEqual(s.adquirir_sugestoes(s.mais_sugeridos()[0]["ids"]), 2)
        self.assertEqual([g["titulo"] for g in s.mais_sugeridos()], ["Outro livro"])
        with self.assertRaises(s.ErroNegocio):
            s.adquirir_sugestoes([1, 2])        # já estavam adquiridas
        with self.assertRaises(s.ErroNegocio):
            s.adquirir_sugestoes(["", "x"])     # nada utilizável

    def test_tela_mostra_o_ranking_e_marca_adquirida_pelo_botao(self):
        cliente = self._logar()
        s.salvar_sugestao("Laranja Mecânica", "Anthony Burgess", sugerido_por="Prof. Marcos")
        s.salvar_sugestao("Laranja Mecânica", "Anthony Burgess", sugerido_por="Beto")
        aba = _aba(cliente.get("/").data.decode(), "maissugeridos")
        for texto in ("Laranja Mecânica", "Prof. Marcos, Beto", 'name="ids" value="1,2"'):
            self.assertTrue(texto in aba, f"faltou na aba: {texto}")
        self.assertEqual(cliente.post("/sugestoes/adquirir", data={"ids": "1,2"}).status_code, 400)  # sem CSRF
        r = cliente.post("/sugestoes/adquirir", data={"csrf_token": "t", "ids": "1,2"})
        self.assertEqual(r.headers["Location"], "/#maissugeridos")
        self.assertEqual(len(s.mais_sugeridos()), 0)
        self.assertIn("Nenhuma sugestão pendente", _aba(cliente.get("/").data.decode(), "maissugeridos"))

    def test_cadastro_pela_tela_avisa_quando_o_livro_ja_foi_pedido(self):
        cliente = self._logar()
        base = {"csrf_token": "t", "titulo": "Laranja Mecânica", "autor": "Anthony Burgess", "isbn": "",
                "motivo": "", "sugerido_por": "Ana"}
        cliente.post("/sugestoes", data=base)
        cliente.post("/sugestoes", data={**base, "sugerido_por": "Beto"})
        self.assertIn("agora são 2", cliente.get("/").data.decode())


class TestGeneros(_Logado):
    """Gênero dos livros e estatística de gêneros mais lidos."""

    def _ler(self, livro, pessoa=1):
        """Um empréstimo já devolvido (assim o limite de livros abertos não atrapalha)."""
        s.emprestar(livro, pessoa)
        s.devolver(s.get_db().execute("SELECT MAX(id) FROM emprestimos").fetchone()[0])

    # ----- cadastro -----
    def test_cadastro_com_genero_e_validacao(self):
        s.salvar_livro("Dom Casmurro", "9", "Machado de Assis", 1, genero="Romance")
        self.assertEqual(s.obter_livro(4)["genero"], "Romance")
        with self.assertRaises(s.ErroNegocio):
            s.salvar_livro("Outro", "10", "Autor", 1, genero="Gênero inventado")
        s.salvar_livro("Sem gênero", "11", "Autor", 1, genero="")
        s.salvar_livro("Sem argumento", "12", "Autor", 1)
        self.assertEqual((s.obter_livro(5)["genero"], s.obter_livro(6)["genero"]), (None, None))
        self.assertEqual(s.obter_livro(1)["genero"], None)                      # livros antigos seguem sem gênero

    def test_edicao_so_mexe_no_genero_quando_ele_e_informado(self):
        s.salvar_livro("Livro 1", "1", "Autor", 3, livro_id=1, genero="Poesia")
        self.assertEqual(s.obter_livro(1)["genero"], "Poesia")
        s.salvar_livro("Livro 1 (2ª ed.)", "1", "Autor", 3, livro_id=1)         # não informou: mantém
        self.assertEqual(s.obter_livro(1)["genero"], "Poesia")
        s.salvar_livro("Livro 1 (2ª ed.)", "1", "Autor", 3, livro_id=1, genero="")  # "Sem gênero": limpa
        self.assertEqual(s.obter_livro(1)["genero"], None)

    def test_somar_exemplar_so_preenche_genero_que_estava_vazio(self):
        s.salvar_livro("Livro 1", "1", "Autor", 1, genero="Poesia")
        self.assertEqual(s.obter_livro(1)["genero"], "Poesia")
        s.salvar_livro("Livro 1", "1", "Autor", 1, genero="Romance")            # já tinha: não troca
        self.assertEqual(s.obter_livro(1)["genero"], "Poesia")
        self.assertEqual(s.obter_livro(1)["quantidade_disponivel"], 5)

    def test_busca_de_livros_tambem_acha_pelo_genero(self):
        s.salvar_livro("Livro 2", "2", "Autor", 3, livro_id=2, genero="Fantasia")
        self.assertEqual([l["titulo"] for l in s.buscar_livros("fantasia")], ["Livro 2"])

    def test_banco_antigo_sem_a_coluna_ganha_a_coluna(self):
        import sqlite3
        if sqlite3.sqlite_version_info < (3, 35):
            self.skipTest("SQLite antigo, sem DROP COLUMN")
        from biblioteca import db as camada
        banco = s.get_db()
        banco.execute("ALTER TABLE livros DROP COLUMN genero")
        banco.commit()
        camada.init_db(self.app.config["DATABASE"], 30)
        s.salvar_livro("Novo", "9", "Autor", 1, genero="Teatro")
        self.assertEqual(s.obter_livro(4)["genero"], "Teatro")
        self.assertEqual(s.obter_livro(1)["titulo"], "Livro 1")                 # dados antigos intactos

    # ----- estatística geral -----
    def test_ranking_geral_conta_emprestimos_e_separa_os_sem_genero(self):
        s.salvar_pessoa("Aluno", "Bia", "bia@x.com", "8º ano A", "")
        s.salvar_livro("Livro 1", "1", "Autor", 3, livro_id=1, genero="Romance")
        s.salvar_livro("Livro 2", "2", "Autor", 3, livro_id=2, genero="Romance")
        s.salvar_livro("Livro 3", "3", "Autor", 3, livro_id=3, genero="Poesia")
        s.salvar_livro("Sem gênero", "4", "Autor", 3)                           # livro 4
        for livro, pessoa in ((1, 1), (1, 2), (2, 1), (3, 1), (4, 1)):
            self._ler(livro, pessoa)
        s.emprestar(3, 2)                                                       # em aberto também conta
        g = s.generos_mais_lidos()
        self.assertEqual([(x["genero"], x["emprestimos"], x["titulos"], x["leitores"], x["pct"]) for x in g["itens"]],
                         [("Romance", 3, 2, 2, 60), ("Poesia", 2, 1, 2, 40)])
        self.assertEqual((g["total"], g["sem_genero"], g["livros_sem_genero"], g["titulos"]), (5, 1, 1, 4))

    def test_ranking_geral_vazio(self):
        g = s.generos_mais_lidos()
        self.assertEqual((g["itens"], g["total"]), ([], 0))
        self.assertEqual(g["livros_sem_genero"], 3)

    # ----- estatística por pessoa -----
    def test_genero_por_pessoa_e_confiabilidade(self):
        s.salvar_pessoa("Aluno", "Bia", "bia@x.com", "8º ano A", "")
        s.salvar_livro("Livro 1", "1", "Autor", 3, livro_id=1, genero="Romance")
        s.salvar_livro("Livro 2", "2", "Autor", 3, livro_id=2, genero="Poesia")
        s.salvar_livro("Livro 3", "3", "Autor", 3, livro_id=3)                  # sem gênero
        for livro in (1, 1, 2, 3):
            self._ler(livro, 1)
        self._ler(2, 2)
        ana, bia = s.generos_da_pessoa(1), s.generos_da_pessoa(2)
        self.assertEqual([(x["genero"], x["emprestimos"]) for x in ana["itens"]], [("Romance", 2), ("Poesia", 1)])
        self.assertEqual((ana["emprestimos"], ana["total"], ana["sem_genero"], ana["confiavel"]), (4, 3, 1, True))
        self.assertEqual((bia["total"], bia["confiavel"]), (1, False))          # poucos dados: só uma pista
        with self.assertRaises(s.ErroNegocio):
            s.generos_da_pessoa(99)

    # ----- telas -----
    def test_cadastro_e_edicao_de_livro_pelas_telas(self):
        cliente = self._logar()
        base = {"csrf_token": "t", "titulo": "Dom Casmurro", "isbn": "9", "quantidade": "1",
                "autor": "Machado de Assis", "observacao": "", "genero": "Romance"}
        cliente.post("/livros", data=base)
        self.assertEqual(s.obter_livro(4)["genero"], "Romance")
        livros = _aba(cliente.get("/").data.decode(), "livros")
        self.assertIn("Romance", livros)
        self.assertIn("Sem gênero", livros)                                      # os três livros antigos
        # o gênero usado fica pré-selecionado para o próximo cadastro em sequência
        self.assertTrue('<option selected>Romance</option>' in cliente.get("/").data.decode())
        # gênero inválido: erro e o resto do que foi digitado é mantido
        cliente.post("/livros", data={**base, "isbn": "10", "titulo": "Outro", "genero": "Inventado"})
        self.assertIn("Escolha um gênero da lista", cliente.get("/").data.decode())
        # edição
        pagina = cliente.get("/livros/4/editar").data.decode()
        self.assertTrue('<option selected>Romance</option>' in pagina)
        cliente.post("/livros/4/editar", data={**base, "quantidade": "1", "genero": "Poesia"})
        self.assertEqual(s.obter_livro(4)["genero"], "Poesia")

    def test_aba_de_generos_nao_mostra_nomes_de_pessoas(self):
        cliente = self._logar()
        s.salvar_pessoa("Aluno", "Zuleica Prado", "z@x.com", "8º ano A", "")
        s.salvar_livro("Livro 1", "1", "Autor", 3, livro_id=1, genero="Romance")
        self._ler(1, 2)
        pagina = cliente.get("/").data.decode()
        aba = _aba(pagina, "generos")
        self.assertIn("Romance", aba)
        self.assertIn("100%", aba)
        self.assertFalse("Zuleica" in aba, "a aba geral de gêneros não deve listar pessoas")
        self.assertTrue("Zuleica" in _aba(pagina, "pessoas"))                    # e o nome está onde deve estar

    def test_pagina_de_leitura_da_pessoa(self):
        cliente = self._logar()
        anonimo = self.app.test_client()
        self.assertEqual(anonimo.get("/pessoas/1/leitura").status_code, 302)    # exige login
        s.salvar_livro("Livro 1", "1", "Autor", 3, livro_id=1, genero="Fantasia")
        self._ler(1, 1)
        pagina = cliente.get("/pessoas/1/leitura").data.decode()
        for texto in ("Leitura de Ana", "Fantasia", "Só 1 empréstimo(s) com gênero definido"):
            self.assertTrue(texto in pagina, f"faltou: {texto}")
        self.assertTrue("/pessoas/1/leitura" in cliente.get("/").data.decode())  # botão na lista de pessoas
        self.assertTrue("/pessoas/1/leitura" in cliente.get("/balcao?pessoa=1").data.decode())  # e no atendimento
        self.assertEqual(cliente.get("/pessoas/99/leitura").status_code, 302)  # não existe: volta à lista


class TestViradaPorAluno(_Logado):
    """Virada de ano: a regra é por turma, mas cada aluno pode fugir dela (saiu da escola, repetiu o ano)."""

    def setUp(self):
        super().setUp()                                   # Ana (id 1), 8º ano A
        s.salvar_pessoa("Aluno", "Bia", "bia@x.com", "8º ano A", "", matricula="20")      # id 2
        s.salvar_pessoa("Aluno", "Caio", "caio@x.com", "8º ano A", "")                    # id 3
        s.salvar_pessoa("Aluno", "Duda", "duda@x.com", "3º ano EM A", "")                 # id 4
        s.salvar_pessoa("Aluno", "Eli", "eli@x.com", "8º ano B", "")                      # id 5

    def _turma(self, pessoa_id):
        p = s.obter_pessoa(pessoa_id)
        return p["turma"], p["ativo"]

    def test_um_aluno_sai_e_o_resto_da_turma_passa_de_serie(self):
        r = s.virar_ano([("8º ano A", "9º ano A")], {2: "arquivar"})
        self.assertEqual(r, (2, 1, []))
        self.assertEqual((self._turma(1), self._turma(3)), (("9º ano A", 1), ("9º ano A", 1)))
        self.assertEqual(self._turma(2), ("8º ano A", 0))          # Bia: arquivada, histórico e turma preservados
        self.assertEqual(self._turma(5), ("8º ano B", 1))          # outras turmas não são tocadas

    def test_aluno_que_repete_fica_na_turma_mesmo_com_a_turma_arquivada(self):
        r = s.virar_ano([("3º ano EM A", "")], {4: "manter"})
        self.assertEqual((r, self._turma(4)), ((0, 0, []), ("3º ano EM A", 1)))

    def test_decisao_individual_vale_mesmo_com_a_turma_marcada_para_ficar(self):
        r = s.virar_ano([], {2: "arquivar"})                      # turma "Manter": nenhum par enviado
        self.assertEqual((r, self._turma(2), self._turma(1)), ((0, 1, []), ("8º ano A", 0), ("8º ano A", 1)))

    def test_aluno_com_livro_nao_e_arquivado_e_o_aviso_diz_quem(self):
        s.emprestar(1, 1)                                         # Ana está com um livro
        r = s.virar_ano([("8º ano A", "9º ano A")], {1: "arquivar", 2: "arquivar"})
        self.assertEqual(r, (1, 1, ["Ana (8º ano A)"]))
        self.assertEqual((self._turma(1), self._turma(2), self._turma(3)),
                         (("8º ano A", 1), ("8º ano A", 0), ("9º ano A", 1)))   # Ana fica; Bia sai; Caio passa

    def test_decisoes_individuais_so_atingem_alunos_ativos(self):
        s.salvar_pessoa("Professor", "Prof. Z", "z@x.com", "", "Química")        # id 6
        s.virar_ano([], {2: "arquivar"})                                         # Bia já arquivada abaixo
        r = s.virar_ano([], {6: "arquivar", 99: "arquivar", 2: "arquivar", 3: "apagar"})
        self.assertEqual(r, (0, 0, []))                                          # professor, id inexistente, já arquivada, ação inválida
        self.assertEqual(s.obter_pessoa(6)["ativo"], 1)
        self.assertEqual(self._turma(3), ("8º ano A", 1))

    def test_lista_de_alunos_por_turma(self):
        s.emprestar(1, 2)                                         # Bia pega o livro 1
        s.alternar_ativo(5)                                       # Eli arquivado: some da lista
        s.salvar_pessoa("Professor", "Prof. Z", "z@x.com", "", "Química")
        por_turma = s.alunos_por_turma()
        self.assertEqual(sorted(por_turma), ["3º ano EM A", "8º ano A"])
        self.assertEqual([(a["nome"], a["emprestados"]) for a in por_turma["8º ano A"]], [("Ana", 0), ("Bia", 1), ("Caio", 0)])

    # ----- telas -----
    def test_tela_lista_os_alunos_e_avisa_de_livro_emprestado(self):
        cliente = self._logar()
        s.emprestar(1, 2)                                         # Bia com livro
        pagina = cliente.get("/virada").data.decode()
        for texto in ("Ver os 3 alunos", "Ana", "Bia", "Caio", 'name="aluno_2"', "Saiu da escola (arquivar)",
                      "Fica na turma atual", "1 livro emprestado", "matrícula 20"):
            self.assertTrue(texto in pagina, f"faltou na tela: {texto}")
        self.assertTrue("Eli" in pagina)                           # turma B também aparece

    def test_aplicar_pela_tela_arquiva_so_o_aluno_marcado(self):
        cliente = self._logar()
        dados = [("csrf_token", "t"), ("de", "8º ano A"), ("para", "9º ano"), ("de", "8º ano B"), ("para", "__manter__"),
                 ("de", "3º ano EM A"), ("para", ""), ("aluno_1", ""), ("aluno_2", "arquivar"), ("aluno_3", ""),
                 ("aluno_4", "manter"), ("aluno_5", "arquivar")]
        r = cliente.post("/virada", data=MultiDict(dados))
        self.assertEqual(r.headers["Location"], "/#pessoas")
        self.assertEqual((self._turma(1), self._turma(3)), (("9º ano A", 1), ("9º ano A", 1)))
        self.assertEqual(self._turma(2), ("8º ano A", 0))
        self.assertEqual(self._turma(4), ("3º ano EM A", 1))      # repetiu: ficou
        self.assertEqual(self._turma(5), ("8º ano B", 0))         # turma B ficou, mas ele saiu
        self.assertTrue("2 aluno(s) mudaram de turma e 2 foram arquivados" in cliente.get("/").data.decode())

    def test_aviso_depois_da_virada_cita_o_aluno_que_nao_saiu(self):
        cliente = self._logar()
        s.emprestar(1, 2)                                         # Bia com livro
        cliente.post("/virada", data=MultiDict([("csrf_token", "t"), ("aluno_2", "arquivar")]))
        pagina = cliente.get("/").data.decode()
        self.assertTrue("Não foram arquivados por terem livro emprestado: Bia (8º ano A)" in pagina)
        self.assertEqual(self._turma(2), ("8º ano A", 1))

    def test_virada_exige_csrf_e_ignora_campos_invalidos(self):
        cliente = self._logar()
        self.assertEqual(cliente.post("/virada", data=MultiDict([("aluno_2", "arquivar")])).status_code, 400)
        cliente.post("/virada", data=MultiDict([("csrf_token", "t"), ("aluno_2", "apagar"), ("aluno_x", "arquivar")]))
        self.assertEqual(self._turma(2), ("8º ano A", 1))


class TestTurmasAeB(_Logado):
    """Cada série tem as turmas A e B, escolhidas por seletor."""

    def test_formularios_oferecem_turma_a_e_b(self):
        cliente = self._logar()
        pagina = cliente.get("/").data.decode()
        for texto in ('<option value="A"', '<option value="B"', "Turma A", "Turma B"):
            self.assertTrue(texto in pagina, f"faltou no cadastro: {texto}")
        self.assertFalse('name="letra" class="form-control"' in pagina)        # não é mais campo livre
        edicao = cliente.get("/pessoas/1/editar").data.decode()
        self.assertTrue('<option value="A" selected>Turma A</option>' in edicao)

    def test_cadastro_pela_tela_em_turma_b_e_lembra_a_turma(self):
        cliente = self._logar()
        cliente.post("/pessoas", data={"csrf_token": "t", "tipo": "Aluno", "nome": "Lia", "email": "lia@x.com",
                                       "serie": "2º ano EM", "letra": "B", "matricula": "", "disciplina": ""})
        self.assertEqual(s.obter_pessoa(2)["turma"], "2º ano EM B")
        self.assertTrue('<option value="B" selected>' in cliente.get("/").data.decode())   # próxima inclusão já vem em B

    def test_pessoa_com_letra_antiga_continua_editavel(self):
        s.salvar_pessoa("Aluno", "Zé", "ze@x.com", "9º ano C", "")             # letra fora da lista, já cadastrada
        edicao = self._logar().get("/pessoas/2/editar").data.decode()
        self.assertTrue('<option value="C" selected>Turma C</option>' in edicao)


class TestMenusLogoEEscape(_Logado):
    """Menus '⋯' (antes saíam como texto) e identidade visual."""

    def test_menus_de_linha_saem_como_botoes_e_nao_como_texto(self):
        cliente = self._logar()
        s.emprestar(1, 1)
        s.salvar_sugestao("Laranja Mecânica", "Anthony Burgess")
        pagina = cliente.get("/").data.decode()
        for aba in ("emprestimos", "livros", "sugestoes", "pessoas"):
            self.assertFalse("&lt;li&gt;" in _aba(pagina, aba) or "&lt;form" in _aba(pagina, aba), f"menu escapado em {aba}")
        pessoas = _aba(pagina, "pessoas")
        self.assertTrue('action="/pessoas/1/alternar"' in pessoas and "Arquivar (saiu da escola)" in pessoas)
        self.assertTrue("Renovar prazo" in _aba(pagina, "emprestimos"))

    def test_titulo_com_aspas_nao_quebra_o_menu_de_emprestimos(self):
        cliente = self._logar()
        s.salvar_livro('O "Pequeno" <b>Príncipe</b>', "77", "Autor", 1)
        s.emprestar(4, 1)
        aba = _aba(cliente.get("/").data.decode(), "emprestimos")
        self.assertTrue('data-livro="O &#34;Pequeno&#34; &lt;b&gt;Príncipe&lt;/b&gt;"' in aba)   # escapado, nada de HTML solto
        self.assertFalse("<b>Príncipe</b>" in aba)

    def test_arquivar_um_aluno_pela_rota_do_menu(self):
        cliente = self._logar()
        cliente.post("/pessoas/1/alternar", data={"csrf_token": "t"})
        self.assertEqual(s.obter_pessoa(1)["ativo"], 0)

    def test_logo_esta_nas_telas_e_e_servida(self):
        cliente = self._logar()
        self.assertTrue("logo-cepi.svg" in cliente.get("/").data.decode())
        self.assertTrue("CEPI" in cliente.get("/").data.decode())
        entrada = self.app.test_client().get("/entrar").data.decode()
        self.assertTrue("logo-cepi.svg" in entrada and "Centro de Ensino em Período Integral" in entrada)
        r = cliente.get("/static/logo-cepi.svg")
        self.assertEqual((r.status_code, r.mimetype), (200, "image/svg+xml"))
        self.assertIn(b"<svg", r.data)
        r.close()

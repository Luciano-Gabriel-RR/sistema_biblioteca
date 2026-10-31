"""Preenche o banco com dados de exemplo: 75 pessoas (70 alunos em 10 turmas, 5 professores), 5.000 livros, histórico de devoluções,
dezenas de empréstimos em aberto (vários atrasados), reservas, gêneros dos livros e sugestões de livros. Só roda em banco VAZIO.

    python dados_teste.py          # 5.000 livros
    python dados_teste.py 1000     # outro tamanho de acervo

Para testar sem mexer nos dados reais, use outra pasta de dados:
    BIBLIOTECA_DADOS=dados_teste python dados_teste.py
    BIBLIOTECA_DADOS=dados_teste python run.py
"""
import random
import sys
import unicodedata
from datetime import datetime, timedelta

from biblioteca import create_app
from biblioteca import services as s

# (tipo, nome, e-mail, turma, disciplina, matrícula)  ->  ids 1 a 22, nesta ordem
# (ids 1 a 9: alunos das turmas A; 10 a 12: professores; 13 a 22: alunos das turmas B, duas por série)
PESSOAS = [
    ("Aluno", "Ana Souza", "ana.souza@escola.exemplo", "8º ano A", "", "2026001"),
    ("Aluno", "Bruno Lima", "bruno.lima@escola.exemplo", "8º ano A", "", "2026002"),
    ("Aluno", "Carla Mendes", "carla.mendes@escola.exemplo", "9º ano A", "", "2026003"),
    ("Aluno", "Diego Rocha", "diego.rocha@escola.exemplo", "9º ano A", "", "2026004"),
    ("Aluno", "Eduarda Alves", "eduarda.alves@escola.exemplo", "1º ano EM A", "", "2026005"),
    ("Aluno", "Felipe Costa", "felipe.costa@escola.exemplo", "2º ano EM A", "", "2026006"),
    ("Aluno", "Gabriela Nunes", "gabriela.nunes@escola.exemplo", "2º ano EM A", "", "2026007"),
    ("Aluno", "Henrique Dias", "henrique.dias@escola.exemplo", "3º ano EM A", "", "2026008"),
    ("Aluno", "Isabela Martins", "isabela.martins@escola.exemplo", "3º ano EM A", "", "2026009"),
    ("Professor", "Marcos Ribeiro", "marcos.ribeiro@escola.exemplo", "", "Matemática", ""),
    ("Professor", "Helena Barros", "helena.barros@escola.exemplo", "", "Língua Portuguesa", ""),
    ("Professor", "Paulo Teixeira", "paulo.teixeira@escola.exemplo", "", "História", ""),
    ("Aluno", "Larissa Pereira", "larissa.pereira@escola.exemplo", "8º ano B", "", "2026010"),
    ("Aluno", "Mateus Oliveira", "mateus.oliveira@escola.exemplo", "8º ano B", "", "2026011"),
    ("Aluno", "Nicole Ferreira", "nicole.ferreira@escola.exemplo", "9º ano B", "", "2026012"),
    ("Aluno", "Otávio Ramos", "otavio.ramos@escola.exemplo", "9º ano B", "", "2026013"),
    ("Aluno", "Priscila Gomes", "priscila.gomes@escola.exemplo", "1º ano EM B", "", "2026014"),
    ("Aluno", "Rafael Santos", "rafael.santos@escola.exemplo", "1º ano EM B", "", "2026015"),
    ("Aluno", "Sofia Carvalho", "sofia.carvalho@escola.exemplo", "2º ano EM B", "", "2026016"),
    ("Aluno", "Thiago Araújo", "thiago.araujo@escola.exemplo", "2º ano EM B", "", "2026017"),
    ("Aluno", "Valentina Lopes", "valentina.lopes@escola.exemplo", "3º ano EM B", "", "2026018"),
    ("Aluno", "Wesley Barbosa", "wesley.barbosa@escola.exemplo", "3º ano EM B", "", "2026019"),
]

# (título, autor, exemplares, gênero)  ->  ids 1 a 22, nesta ordem. Os ISBNs são fictícios (TESTE-nnn).
# O último livro fica sem gênero de propósito, para mostrar o aviso na aba "Gêneros lidos".
LIVROS = [
    ("Dom Casmurro", "Machado de Assis", 3, "Romance"), ("Memórias Póstumas de Brás Cubas", "Machado de Assis", 2, "Romance"),
    ("Quincas Borba", "Machado de Assis", 1, "Romance"), ("O Alienista", "Machado de Assis", 2, "Conto e crônica"),
    ("O Cortiço", "Aluísio Azevedo", 2, "Romance"), ("Iracema", "José de Alencar", 2, "Romance"),
    ("O Guarani", "José de Alencar", 1, "Romance"), ("Vidas Secas", "Graciliano Ramos", 3, "Romance"),
    ("São Bernardo", "Graciliano Ramos", 1, "Romance"), ("Capitães da Areia", "Jorge Amado", 2, "Romance"),
    ("A Hora da Estrela", "Clarice Lispector", 2, "Romance"), ("O Sítio do Picapau Amarelo", "Monteiro Lobato", 3, "Infantojuvenil"),
    ("Reinações de Narizinho", "Monteiro Lobato", 2, "Infantojuvenil"), ("O Pequeno Príncipe", "Antoine de Saint-Exupéry", 3, "Infantojuvenil"),
    ("Alice no País das Maravilhas", "Lewis Carroll", 2, "Fantasia"), ("O Hobbit", "J. R. R. Tolkien", 2, "Fantasia"),
    ("Harry Potter e a Pedra Filosofal", "J. K. Rowling", 3, "Fantasia"), ("O Diário de Anne Frank", "Anne Frank", 2, "Biografia"),
    ("O Menino do Pijama Listrado", "John Boyne", 1, "Romance"), ("A Moreninha", "Joaquim Manuel de Macedo", 2, "Romance"),
    ("Os Lusíadas", "Luís de Camões", 1, "Poesia"), ("O Homem que Calculava", "Malba Tahan", 2, ""),
]

TOTAL_LIVROS = 5000  # acervo de exemplo: os 22 livros acima + gerados; para outro tamanho: python dados_teste.py 1000

_NOMES = ["Ana", "Bruno", "Carla", "Daniel", "Elisa", "Fábio", "Gisele", "Hugo", "Ingrid", "João", "Karina", "Lucas", "Marta",
          "Nelson", "Olívia", "Paulo", "Quitéria", "Rafael", "Sílvia", "Tomás", "Ursula", "Vítor", "Wanda", "Xavier", "Yara",
          "Zélia", "Alberto", "Beatriz", "Caio", "Diana", "Eduardo", "Flávia", "Gustavo", "Helena", "Igor", "Júlia", "Léo", "Mônica", "Nuno", "Paula"]
_SOBRENOMES = ["Almeida", "Barbosa", "Cardoso", "Dias", "Esteves", "Farias", "Guedes", "Horta", "Ibrahim", "Jardim", "Klein", "Lacerda",
               "Machado", "Nogueira", "Ornelas", "Pinheiro", "Queiroz", "Rezende", "Siqueira", "Tavares", "Uchoa", "Vasconcelos",
               "Werneck", "Ximenes", "Yamada", "Zanetti", "Amaral", "Bastos", "Coutinho", "Duarte", "Estrela", "Furtado", "Gomes",
               "Holanda", "Lopes", "Medeiros", "Neves", "Prado", "Ramos", "Seixas"]
_PESOS = {"Romance": 25, "Conto e crônica": 5, "Poesia": 5, "Teatro": 2, "Ficção científica": 6, "Fantasia": 8, "Terror": 3,
          "Policial e suspense": 5, "Aventura": 5, "Biografia": 3, "História": 6, "Filosofia e sociologia": 4, "Ciências": 6,
          "Didático e vestibular": 8, "Quadrinhos e mangá": 4, "Infantojuvenil": 8, "Autoajuda": 2, "Outros": 3}
_SUBST = {
    "Romance": ["amor", "promessa", "carta", "casamento", "saudade", "segredo", "herança"],
    "Conto e crônica": ["conto", "crônica", "esquina", "domingo", "vizinho", "café", "bonde"],
    "Poesia": ["verso", "poema", "canção", "silêncio", "rio", "lua", "sonho"],
    "Teatro": ["peça", "palco", "ato", "cortina", "ensaio", "comédia", "tragédia"],
    "Ficção científica": ["colônia", "androide", "órbita", "futuro", "máquina", "planeta", "viagem"],
    "Fantasia": ["reino", "dragão", "feitiço", "espada", "floresta", "profecia", "guardião"],
    "Terror": ["casa", "sombra", "noite", "porão", "assombração", "maldição", "vigília"],
    "Policial e suspense": ["crime", "detetive", "pista", "álibi", "mistério", "testemunha", "dossiê"],
    "Aventura": ["expedição", "tesouro", "travessia", "ilha", "mapa", "naufrágio", "caçada"],
    "Biografia": ["vida", "memórias", "trajetória", "diário", "retrato", "legado", "história"],
    "História": ["império", "revolução", "colônia", "guerra", "república", "fronteira", "século"],
    "Filosofia e sociologia": ["razão", "liberdade", "sociedade", "ética", "poder", "trabalho", "consciência"],
    "Ciências": ["átomo", "célula", "energia", "ecossistema", "universo", "química", "evolução"],
    "Didático e vestibular": ["gramática", "redação", "matemática", "física", "geometria", "literatura", "revisão"],
    "Quadrinhos e mangá": ["herói", "aventura", "guerreiro", "turma", "missão", "academia", "lenda"],
    "Infantojuvenil": ["menino", "aventura", "bichos", "castelo", "turma", "viagem", "amizade"],
    "Autoajuda": ["hábito", "foco", "mente", "rotina", "equilíbrio", "coragem", "propósito"],
    "Outros": ["guia", "manual", "almanaque", "dicionário", "atlas", "coleção", "antologia"],
}
_ADJ = ["perdido", "secreto", "último", "esquecido", "distante", "improvável", "silencioso", "antigo", "invisível", "primeiro",
        "inacabado", "eterno", "pequeno", "grande", "outro", "novo", "estranho", "final", "dourado", "azul"]


def gerar_livros(quantidade):
    """Livros fictícios, sempre os mesmos (semente fixa): (título, autor, exemplares, gênero)."""
    rnd = random.Random(42)
    autores = [f"{n} {sn}" for n in _NOMES for sn in _SOBRENOMES]
    rnd.shuffle(autores)
    autores = autores[:max(quantidade // 6, 1)]  # ~6 títulos por autor
    generos, pesos = list(_PESOS), list(_PESOS.values())
    usados, livros = {t for t, *_ in LIVROS}, []
    while len(livros) < quantidade:
        g = rnd.choices(generos, pesos)[0]
        titulo = f"{rnd.choice(['O', 'A'])} {rnd.choice(_SUBST[g])} {rnd.choice(_ADJ)}"
        if titulo in usados:
            titulo += f" {rnd.randint(2, 9)}"
        if titulo in usados:
            continue
        usados.add(titulo)
        livros.append((titulo, rnd.choice(autores), rnd.choices([1, 2, 3, 4], [4, 3, 2, 1])[0],
                       "" if rnd.random() < 0.03 else g))
    return livros


ALUNOS_POR_TURMA = 7  # 10 turmas x 7 = 70 alunos
_PROFESSORES_EXTRA = [("Renata Cavalcanti", "Matemática"), ("Sérgio Albuquerque", "Biologia")]  # somam 5 professores


def _sem_acento(texto):
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower().replace(" ", ".")


def gerar_pessoas():
    """Completa cada turma até ALUNOS_POR_TURMA alunos e acrescenta os professores extras (ids depois dos 22 primeiros)."""
    rnd = random.Random(11)
    existentes = {nome for _, nome, *_ in PESSOAS}
    nomes = [f"{n} {sn}" for n in _NOMES for sn in _SOBRENOMES if f"{n} {sn}" not in existentes]
    rnd.shuffle(nomes)
    novas, seq = [], 19
    for serie in ("8º ano", "9º ano", "1º ano EM", "2º ano EM", "3º ano EM"):
        for letra in "AB":
            turma = f"{serie} {letra}"
            faltam = ALUNOS_POR_TURMA - sum(1 for q in PESSOAS if q[0] == "Aluno" and q[3] == turma)
            for _ in range(faltam):
                nome = nomes.pop()
                seq += 1
                novas.append(("Aluno", nome, f"{_sem_acento(nome)}@escola.exemplo", turma, "", f"2026{seq:03d}"))
    for nome, disciplina in _PROFESSORES_EXTRA:
        novas.append(("Professor", nome, f"{_sem_acento(nome)}@escola.exemplo", "", disciplina, ""))
    return novas


# Devoluções passadas: (pessoa, livro, estado, dias de atraso)
HISTORICO = [
    (1, 12, "Bom", 0), (1, 14, "Bom", 0),
    (2, 12, "Bom", 0), (2, 14, "Com defeito", 0), (2, 15, "Com defeito", 0),
    (3, 1, "Bom", 0), (3, 8, "Bom", 9), (3, 17, "Bom", 0),
    (4, 17, "Com defeito", 6), (4, 16, "Bom", 12), (4, 1, "Bom", 0),
    (5, 14, "Bom", 0), (5, 15, "Bom", 0), (5, 12, "Bom", 0),
    (6, 8, "Bom", 15), (6, 10, "Bom", 7), (6, 5, "Com defeito", 0),
    (7, 11, "Bom", 0), (7, 2, "Bom", 0),
    (8, 18, "Bom", 0), (8, 1, "Bom", 5),
    (9, 18, "Bom", 0), (9, 11, "Bom", 0), (9, 20, "Bom", 0),
    (10, 22, "Bom", 0), (10, 16, "Bom", 0),
    (11, 2, "Bom", 0), (11, 6, "Bom", 0), (11, 4, "Bom", 0),
    (12, 21, "Bom", 8), (12, 18, "Bom", 0),
    # turmas B
    (13, 12, "Bom", 0), (14, 16, "Bom", 0), (15, 17, "Bom", 0), (16, 1, "Bom", 0), (17, 15, "Bom", 0),
    (18, 14, "Bom", 0), (19, 11, "Bom", 0), (20, 5, "Bom", 0), (21, 18, "Bom", 0), (22, 2, "Bom", 0),
]

app = create_app()
with app.app_context():
    db = s.get_db()
    if db.execute("SELECT COUNT(*) FROM livros").fetchone()[0] or db.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]:
        sys.exit("O banco já tem dados, então nada foi feito. Para testar sem misturar com dados reais, use outra pasta:\n"
                 "  BIBLIOTECA_DADOS=dados_teste python dados_teste.py")

    for tipo, nome, email, turma, disciplina, matricula in PESSOAS + gerar_pessoas():
        s.salvar_pessoa(tipo, nome, email, turma, disciplina, matricula=matricula)
    total = int(sys.argv[1]) if len(sys.argv) > 1 else TOTAL_LIVROS
    for n, (titulo, autor, qtd, genero) in enumerate(LIVROS + gerar_livros(max(total - len(LIVROS), 0)), start=1):
        s.salvar_livro(titulo, f"TESTE-{n:03d}", autor, qtd,
                       observacao="Edição de bolso" if n == 14 else "", genero=genero)

    def dia(n):
        return (datetime.now() + timedelta(days=n)).strftime("%Y-%m-%d")

    def emprestar(pessoa, livro, obs="", atraso=0):
        s.emprestar(livro, pessoa, obs)
        emprestimo_id = db.execute("SELECT MAX(id) FROM emprestimos").fetchone()[0]
        if atraso:  # recua o prazo para simular um empréstimo vencido
            db.execute("UPDATE emprestimos SET data_prevista = ? WHERE id = ?", (dia(-atraso), emprestimo_id))
            db.commit()
        return emprestimo_id

    for pessoa, livro, estado, atraso in HISTORICO:
        s.devolver(emprestar(pessoa, livro, atraso=atraso), "", estado)

    rnd = random.Random(7)
    ids_pessoas = [r[0] for r in db.execute("SELECT id FROM usuarios WHERE ativo = 1")]
    n_livros = db.execute("SELECT COUNT(*) FROM livros").fetchone()[0]

    def livro_aleatorio():  # 70% dos pedidos caem nos 300 primeiros títulos: há livros "campeões" e uma cauda longa
        return rnd.randint(1, min(300, n_livros)) if rnd.random() < 0.7 else rnd.randint(1, n_livros)

    def tentar_emprestar(pessoa, atraso=0):
        try:
            return emprestar(pessoa, livro_aleatorio(), atraso=atraso)
        except s.ErroNegocio:
            return None

    for pessoa in ids_pessoas:  # as 22 primeiras pessoas já têm histórico próprio acima
        for _ in range(rnd.randint(3, 12) if pessoa > 22 else 0):
            eid = tentar_emprestar(pessoa, rnd.randint(1, 15) if rnd.random() < 0.15 else 0)
            if eid:
                s.devolver(eid, "", "Com defeito" if rnd.random() < 0.08 else "Bom")

    # Empréstimos em aberto agora
    emprestar(1, 19, "Para a feira de leitura")   # Ana: no prazo (livro de 1 exemplar)
    emprestar(3, 3)                               # Carla: no prazo (1 exemplar)
    emprestar(6, 9, atraso=12)                    # Felipe: ATRASADO (1 exemplar)
    emprestar(8, 7)                               # Henrique: no prazo
    emprestar(9, 15)                              # Isabela: no prazo
    emprestar(11, 13, "Para a aula de literatura")  # Helena (professora): no prazo

    # Reservas: livros de 1 exemplar que estão emprestados
    s.reservar(19, 2)   # Bruno espera "O Menino do Pijama Listrado"
    s.reservar(3, 4)    # Diego espera "Quincas Borba"
    s.reservar(9, 5)    # Eduarda espera "São Bernardo"

    candidatos = [i for i in ids_pessoas if i not in (1, 3, 6, 8, 9, 11)]
    rnd.shuffle(candidatos)
    for k, pessoa in enumerate(candidatos[:24]):          # 24 empréstimos: 9 atrasados e 15 no prazo
        tentar_emprestar(pessoa, rnd.randint(2, 30) if k < 9 else 0)
    for pessoa in candidatos[9:15]:                       # alguns pegaram um segundo livro
        tentar_emprestar(pessoa)
    reservadas = 0
    for livro in [r[0] for r in db.execute("SELECT id FROM livros WHERE quantidade_disponivel = 0")]:
        if reservadas >= 12:
            break
        try:
            s.reservar(livro, rnd.choice(ids_pessoas))
            reservadas += 1
        except s.ErroNegocio:
            pass

    s.baixar_exemplar(20, "Danificado", "Capa descolada")

    # Sugestões de livros novos: o mesmo livro pedido por pessoas diferentes soma pedidos em "Mais sugeridos".
    # A primeira já foi comprada.
    s.salvar_sugestao("Grande Sertão: Veredas", "João Guimarães Rosa", "", "Leitura do vestibular", "Profa. Helena Barros")
    s.salvar_sugestao("Laranja Mecânica", "Anthony Burgess", "", "Pedido de alunos do 3º ano EM", "Henrique Dias")
    s.salvar_sugestao("Laranja Mecânica", "Anthony Burgess", "", "", "Isabela Martins")
    s.salvar_sugestao("Laranja Mecânica", "Anthony Burgess", "", "", "Prof. Marcos Ribeiro")
    s.salvar_sugestao("Ensaio sobre a Cegueira", "José Saramago", "", "", "Prof. Paulo Teixeira")
    s.salvar_sugestao("Ensaio sobre a Cegueira", "José Saramago", "", "", "Gabriela Nunes")
    s.salvar_sugestao("Percy Jackson e o Ladrão de Raios", "Rick Riordan", "", "Série que a turma está lendo", "Bruno Lima")
    s.alternar_sugestao(1)

    p = s.painel()
    print(f"Pronto: {p['pessoas']} pessoas, {p['titulos']} livros, {p['emprestados']} empréstimos em aberto "
          f"({p['atrasados']} atrasados), {p['fila']} reservas, {len(s.historico())} registros no histórico.")
    print("Crie a conta do bibliotecário ao abrir o sistema pela primeira vez.")

# Biblioteca Pré Universitário (sistema de biblioteca)

## Instalar e rodar
```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run.py                     # abre em http://127.0.0.1:8000
```
Para testar mudanças no código: `python run.py --debug`.

## Colocar no computador da escola
1. Copie a pasta inteira (inclua `dados/`, se já houver cadastros) e repita os 4 comandos acima.
2. Para outros computadores da rede acessarem, inicie assim e acesse `http://IP-DO-PC-DA-ESCOLA:8000`:
   `BIBLIOTECA_HOST=0.0.0.0 python run.py`  (Windows: `set BIBLIOTECA_HOST=0.0.0.0` antes).
3. Ajuste o firewall para liberar a porta 8000 só na rede da escola.
4. Se o PC ficar sem internet, baixe o Bootstrap 5.3.3 (CSS e JS) para uma pasta `static/` e troque os links em `base.html`.

## Dados e backup
- Tudo fica em `dados/biblioteca.db`. Rode `python backup.py` para criar cópias em `dados/backups/` (pode agendar todo dia).
- Variáveis opcionais: `BIBLIOTECA_DADOS` (pasta dos dados), `BIBLIOTECA_PRAZO_DIAS` (padrão 30), `BIBLIOTECA_PORTA` (padrão 8000), `SECRET_KEY`.

## Login
No primeiro acesso o sistema pede para criar a conta do bibliotecário (senha de 8+ caracteres). Depois, todas as telas exigem login. Se esquecer a senha, apague a linha da tabela `bibliotecarios` no banco e acesse de novo: o sistema volta a pedir a criação da conta.

## Regras de empréstimo
Alunos podem ter 2 livros ao mesmo tempo e professores 5; quem tem livro atrasado não pega outro; cada empréstimo pode ser renovado 1 vez, antes de atrasar. Ajuste com `BIBLIOTECA_LIMITE_ALUNO`, `BIBLIOTECA_LIMITE_PROFESSOR` e `BIBLIOTECA_MAX_RENOVACOES`.

## Backup automático (Linux)
`crontab -e` e adicione (todo dia às 18h): `0 18 * * * cd /caminho/do/projeto && venv/bin/python backup.py`

## Iniciar com o computador (Linux, systemd)
Crie `/etc/systemd/system/biblioteca.service` com `ExecStart=/caminho/do/projeto/venv/bin/python run.py`, `WorkingDirectory=/caminho/do/projeto` e `Restart=always`; depois `sudo systemctl enable --now biblioteca`.

## Testes
`python -m unittest discover tests`

## Estrutura
- `biblioteca/db.py` banco e migrações · `services.py` regras de negócio · `routes.py` páginas · `templates/ (inclui balcao.html e _acoes.html)` interface.

## Relatório de atrasados
Botão na aba Empréstimos: lista os atrasos por turma (e professores), pronta para imprimir.

## Funcionar sem internet
Com internet, rode uma vez `python baixar_bootstrap.py` e reinicie o sistema. Os arquivos ficam em `biblioteca/static/`.

## Prazos e registros
`BIBLIOTECA_PRAZO_ALUNO` e `BIBLIOTECA_PRAZO_PROFESSOR` definem o prazo de cada tipo (padrão 30 dias). Erros e logins que falharam ficam em `dados/biblioteca.log`.

## Reservas, virada de ano e paginação
- **Reservas:** aba Reservas, para livro sem exemplar livre. Ao devolver, o exemplar fica separado para o primeiro da fila ("Disponível para retirada"); só essa pessoa consegue emprestá-lo. Livro com fila não pode ser renovado. Não há aviso automático: quem atende vê a situação na aba.
- **Virada de ano:** botão na aba Alunos e professores. Cada turma passa para a série seguinte mantendo a letra (8º ano A vai para o 9º ano A, 8º ano B para o 9º ano B); o 3º ano EM é sugerido para arquivar. Faz backup antes em `dados/backups/`. Alunos com livro emprestado não são arquivados.
  - **Decisão por aluno:** a escolha da linha vale para a turma toda, mas em **Ver os alunos** cada aluno pode ser tratado à parte: **Saiu da escola (arquivar)** arquiva só aquele aluno (o histórico dele fica guardado, e a turma segue normalmente), e **Fica na turma atual** serve para quem vai repetir o ano. Quem tem livro emprestado aparece sinalizado, e ao final o aviso diz **quais alunos** não puderam ser arquivados e de qual turma.
  - Para um aluno que sai no meio do ano, sem virada: menu **⋯** da linha dele em Alunos e professores, **Arquivar (saiu da escola)**.
- **Paginação:** 20 registros por página em livros, autores, alunos e professores e histórico.

## Painel, backups e exportação
- **Painel:** tela inicial com números (emprestados, atrasados, reservas), livros mais emprestados e quem mais leu. Mostra um aviso se o último backup tem 7 dias ou mais (`BIBLIOTECA_DIAS_ALERTA_BACKUP`).
- **Backups e exportação** (botão no topo): fazer backup, baixar, restaurar (guarda uma cópia do estado atual antes) e exportar livros, pessoas e histórico em CSV para o Excel.
- **Reservas:** o exemplar separado fica 3 dias para retirada (`BIBLIOTECA_PRAZO_RETIRADA`); depois a reserva expira e passa ao próximo da fila.
- **Perdido ou danificado:** botão "Perdido" no empréstimo (o exemplar não volta ao estoque) e "Dar baixa" na edição do livro.
- **Listas para imprimir:** acervo, empréstimos em aberto, reservas e sugestões pendentes.
- **Cadastro em sequência:** depois de salvar, o cursor volta ao primeiro campo e o último autor/turma ficam preenchidos.

## Sugestões de livros
Aba **Sugestões de livros** (menu Acervo): lista dos livros novos que poderiam entrar na biblioteca. Para cada sugestão registram-se título e autor (obrigatórios), ISBN, quem sugeriu e o motivo (opcionais). Quando o livro for comprado, **Marcar como adquirida**; **Reabrir** desfaz. Dá para buscar por título, autor, ISBN ou quem sugeriu, filtrar por situação e imprimir só as pendentes (botão **Imprimir pendentes**, bom para levar a uma reunião de compras).
- O sistema recusa a sugestão de um livro que **já está no acervo** (mesmo ISBN, ou mesmo título e autor).
- O **mesmo livro pode ser sugerido por pessoas diferentes**: cada pedido é registrado e contado em "Mais sugeridos". Só é recusada a mesma pessoa pedindo o mesmo livro duas vezes (quando o campo "Sugerido por" é preenchido).
- Sugestões não afetam empréstimos nem estoque: adquirir de fato continua sendo feito em **Cadastrar livro**.

### Mais sugeridos
Aba **Mais sugeridos** (menu Acervo): ranking dos livros mais pedidos, até 20, com quantos pedidos cada um teve e quem pediu. Considera só os pedidos **pendentes**. O mesmo livro (mesmo ISBN, ou mesmo título e autor) é agrupado mesmo escrito de formas diferentes. O botão **Marcar adquirida** da linha marca de uma vez todos os pedidos daquele livro, e ele sai do ranking.

## Gêneros
- **Gênero do livro:** campo opcional ao cadastrar ou editar um livro, escolhido de uma lista fixa (Romance, Poesia, Fantasia, Infantojuvenil etc.). A lista foi feita fixa de propósito: com texto livre, "Romance" e "romances" virariam gêneros diferentes nas estatísticas. Para mudar a lista, edite `GENEROS` em `biblioteca/services.py`. Livros antigos ficam "Sem gênero" até você editá-los. A busca de livros também acha pelo gênero.
- **Gêneros lidos** (menu Análises): ranking dos gêneros mais emprestados na biblioteca toda, com a porcentagem, quantos livros diferentes e quantos leitores diferentes. Não mostra nomes de pessoas. Mostra também quantos livros ainda estão sem gênero e ficam fora da conta.
- **Leitura por pessoa:** botão **Leitura** na linha de cada pessoa em *Alunos e professores* (e o link no *Atendimento*) abre uma página com os gêneros que ela mais pegou. Ficou separada da estatística geral de propósito: é o hábito de leitura de uma pessoa, muitas vezes menor de idade, então só aparece quando se abre o cadastro dela. Com menos de 3 empréstimos com gênero definido, a página avisa que o resultado é só uma pista.
- "Lido" significa **emprestado** (devolvido ou ainda em aberto): o sistema não sabe se a pessoa terminou o livro. Renovações e reservas não contam como novo empréstimo.
- Bancos criados em versões anteriores ganham a coluna `genero` automaticamente ao abrir o sistema; nenhum dado existente é alterado.

## Vários exemplares do mesmo livro
Cadastre o livro uma vez, com a quantidade de exemplares. Para acrescentar cópias depois, cadastre de novo com o **mesmo ISBN, título e autor**: o sistema soma os exemplares ao registro existente (hifens e espaços no ISBN são ignorados). Se o ISBN existir com outro título ou autor, o cadastro é recusado. Os exemplares são contados, mas não têm código individual.

## Reservas e buscas
Cada pessoa pode ter **uma reserva por vez** (de um exemplar, de um livro). Nos formulários de empréstimo e de reserva há campos de busca que filtram, ao digitar, a lista de livros (título, autor ou ISBN) e de pessoas (nome, turma ou matrícula). Só aluno tem matrícula, e a escola tem um único turno.

## Comportamento, busca nos empréstimos e modo escuro
- **Devolução:** o botão Devolver abre uma janela para informar se o livro voltou **em bom estado** ou **com defeito**, com observação opcional.
- **Busca nos empréstimos em aberto:** campo acima da lista, por nome da pessoa ou título do livro, sem diferenciar acentos.
- **Aba Comportamento:** quem mais atrasa, quem mais devolve com defeito, quem entrega tudo certo, e as turmas que mais pegam livros, que mais atrasam ou devolvem com defeito, e que mais entregam certo. Só entra quem tem 2 ou mais devoluções (`MIN_ENTREGAS` em `services.py`).
- **Modo escuro:** botão no topo; lembra a escolha e, na primeira vez, segue o tema do sistema. A impressão sai sempre clara.

## Balcão de atendimento

Em **Balcão › Atendimento**, busque a pessoa pelo nome, turma, e-mail ou matrícula e atenda sem trocar de tela: veja o que ela está levando, empreste, devolva (em bom estado ou com defeito), renove o prazo ou reserve um livro sem exemplar livre. Cada ação volta para o próprio balcão. A regra de cada operação é a mesma das outras telas: pessoa com livro em atraso ou arquivada não pega livro novo.

## Busca de alunos e professores

Na aba **Alunos e professores**, a busca procura em nome, e-mail, turma, disciplina e matrícula, e pagina os resultados.

## Dados de exemplo
`python dados_teste.py` preenche um banco vazio com 75 pessoas (70 alunos, 7 em cada uma das 10 turmas A e B, e 5 professores), 5.000 livros (os 22 primeiros são reais; o restante é gerado, sempre igual; `python dados_teste.py 1000` muda o tamanho), um histórico de devoluções (com atrasos e defeitos), 36 empréstimos em aberto (10 atrasados), 12 reservas, gêneros nos livros e sugestões (com pedidos repetidos), para ver todas as telas funcionando. Roda só em banco vazio. Para não misturar com dados reais: `BIBLIOTECA_DADOS=dados_teste python dados_teste.py` e depois `BIBLIOTECA_DADOS=dados_teste python run.py`. Para recomeçar do zero, apague a pasta de dados usada.

## Nome e turmas
O nome exibido é "Biblioteca Pré Universitário" (mude com `BIBLIOTECA_NOME`). As turmas aceitas vão do **8º ano ao 3º ano do ensino médio** (8º ano, 9º ano, 1º, 2º e 3º ano EM), e cada série tem as turmas **A** e **B**, escolhidas por seletor no cadastro (cadastros antigos com outra letra, ou sem letra, continuam funcionando). Para acrescentar mais turmas, edite `LETRAS` em `biblioteca/services.py`. Na virada de ano, o 3º ano EM é sugerido para arquivar, e dá para ajustar aluno por aluno. Nos empréstimos em aberto, a busca aceita turma e há um filtro por turma.

## Dados de exemplo já prontos
A pasta `dados_teste/` já vem com um banco de exemplo preenchido (75 pessoas (70 alunos e 5 professores), 5.000 livros com gênero, histórico, empréstimos, reservas e sugestões). Para usá-lo sem tocar nos dados reais (`dados/`):
`BIBLIOTECA_DADOS=dados_teste python run.py`
Na primeira vez, crie a conta do bibliotecário. Os prazos foram calculados na data em que o banco foi gerado; para datas novas, apague `dados_teste/` e rode `BIBLIOTECA_DADOS=dados_teste python dados_teste.py`.

## Aparência
Visual renovado (cartões arredondados, abas em formato de pílula, ícone no topo) e modo escuro em azul-marinho, com botões e cores ajustados para ficar confortável. Na aba Comportamento, pessoas e turmas aparecem em grades de cartões, sem rolagem lateral.

## Rodar como programa (sem abrir o navegador)
`python programa.py` (ou duplo clique em `iniciar_biblioteca.sh` no Linux / `iniciar_biblioteca.bat` no Windows) abre uma **janela própria**, sem navegador, e encerra o sistema quando a janela é fechada. Ela usa, nesta ordem: uma janela **nativa** (pacote `pywebview`), o Chrome/Edge/Chromium/Brave em "modo aplicativo" e, se nenhum funcionar, aparece um aviso de como instalar (o navegador comum **não** é aberto sozinho; só com `python programa.py --navegador`). Para ver o que falta no computador: `bash iniciar_biblioteca.sh --diagnostico`.
- **Linux, instalação completa (janela nativa + ícone):** `bash instalar.sh` (uma vez). Para abrir sozinha ao entrar no computador: `bash instalar.sh --iniciar-com-o-pc`.
- **Ícone no Linux:** `bash instalar_atalho.sh` cria o atalho no menu e na área de trabalho.
- **Windows:** clique com o botão direito em `iniciar_biblioteca.bat`, Enviar para, Área de trabalho (criar atalho).
- Erros sem terminal ficam em `dados/programa.log`.

## Atalho dos dados de teste
`bash instalar_atalho.sh` cria um segundo ícone, **Biblioteca Pré Universitário (TESTE)** (laranja), que abre o sistema com os dados de exemplo de `dados_teste/` e mostra "(TESTE)" no título, para não confundir com os dados reais. Pelo terminal: `bash iniciar_teste.sh` (Windows: `iniciar_teste.bat`). Se `dados_teste/` não existir, o banco de exemplo é gerado sozinho.

## Windows 10
Use o pacote `sistema_biblioteca_windows.zip` e siga o `LEIA-ME-WINDOWS.txt`: extrair, dar dois cliques em `instalar_windows.bat` e abrir pelo ícone. A janela é o Microsoft Edge (já vem no Windows 10) em modo aplicativo, sem barra de endereço; quando a janela fecha, o sistema encerra. `construir_exe.bat` (opcional) gera um `Biblioteca.exe` que não exige Python.

## Logo do CEPI
O menu, a tela de entrada e o ícone da aba do navegador usam o emblema `biblioteca/static/logo-cepi.svg` (sol nascendo sobre um livro aberto: o período integral e a biblioteca; verde e dourado) e a identificação "CEPI · Goiás". **É um emblema próprio do sistema, não a marca oficial do Governo de Goiás/Seduc.** Para usar a marca oficial da escola, basta substituir esse arquivo por outro com o mesmo nome (`logo-cepi.svg`; PNG também serve se você trocar a extensão nos modelos `base.html`, `index.html` e `login.html`). O executável do Windows (`construir_exe.bat`) já inclui a pasta `biblioteca/static`. O ícone do atalho e do executável (`icone.ico`, `icone.svg`) usa o mesmo emblema; o ícone laranja "TESTE" (`icone_teste.*`) foi mantido para diferenciar os dados de exemplo.

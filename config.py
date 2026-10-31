"""Configurações. Tudo pode ser trocado por variáveis de ambiente, sem mexer no código."""
import os
import secrets
import shutil
import sys
from pathlib import Path

BASE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("BIBLIOTECA_DADOS", BASE / "dados"))
DATABASE = DATA_DIR / "biblioteca.db"
PRAZO_DIAS = int(os.environ.get("BIBLIOTECA_PRAZO_DIAS", 30))

DATA_DIR.mkdir(parents=True, exist_ok=True)

# Versões anteriores guardavam o banco na raiz do projeto: move para a pasta de dados.
_legado = BASE / "biblioteca.db"
if _legado.exists() and not DATABASE.exists():
    shutil.move(str(_legado), str(DATABASE))


def chave_secreta():
    """Usa SECRET_KEY do ambiente ou gera uma uma única vez e guarda em dados/secret.key."""
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    arquivo = DATA_DIR / "secret.key"
    if not arquivo.exists():
        arquivo.write_text(secrets.token_hex(32))
    return arquivo.read_text().strip()

LIMITES = {  # livros que cada tipo pode ter emprestados ao mesmo tempo
    "Aluno": int(os.environ.get("BIBLIOTECA_LIMITE_ALUNO", 2)),
    "Professor": int(os.environ.get("BIBLIOTECA_LIMITE_PROFESSOR", 5)),
}
MAX_RENOVACOES = int(os.environ.get("BIBLIOTECA_MAX_RENOVACOES", 1))

# Prazo de devolução por tipo (dias). Por padrão, igual ao prazo geral.
PRAZOS = {
    "Aluno": int(os.environ.get("BIBLIOTECA_PRAZO_ALUNO", PRAZO_DIAS)),
    "Professor": int(os.environ.get("BIBLIOTECA_PRAZO_PROFESSOR", PRAZO_DIAS)),
}

PRAZO_RETIRADA_DIAS = int(os.environ.get("BIBLIOTECA_PRAZO_RETIRADA", 3))  # reserva não retirada expira
DIAS_ALERTA_BACKUP = int(os.environ.get("BIBLIOTECA_DIAS_ALERTA_BACKUP", 7))

NOME_BIBLIOTECA = os.environ.get("BIBLIOTECA_NOME", "Biblioteca Pré Universitário")

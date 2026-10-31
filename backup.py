"""Cria uma cópia segura do banco em dados/backups/ (pode rodar com o sistema ligado)."""
import sqlite3
from datetime import datetime

from config import DATA_DIR, DATABASE

pasta = DATA_DIR / "backups"
pasta.mkdir(exist_ok=True)
destino = pasta / f"biblioteca-{datetime.now():%Y%m%d-%H%M%S}.db"

origem, copia = sqlite3.connect(DATABASE), sqlite3.connect(destino)
origem.backup(copia)
origem.close()
copia.close()
print(f"Backup criado: {destino}")

"""Baixa o Bootstrap para biblioteca/static/ (rode UMA vez, com internet). Depois o sistema funciona offline."""
import urllib.request
from pathlib import Path

BASE = "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/"
ARQUIVOS = {"css/bootstrap.min.css": "bootstrap.min.css", "js/bootstrap.bundle.min.js": "bootstrap.bundle.min.js"}

pasta = Path(__file__).resolve().parent / "biblioteca" / "static"
pasta.mkdir(parents=True, exist_ok=True)
for origem, destino in ARQUIVOS.items():
    urllib.request.urlretrieve(BASE + origem, pasta / destino)
    print("Baixado:", destino)
print("Pronto. Reinicie o sistema.")

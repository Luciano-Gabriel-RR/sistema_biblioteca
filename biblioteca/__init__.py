import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, render_template

import config

from . import auth, db, routes


def create_app(database=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=config.chave_secreta(),
        DATABASE=str(database or config.DATABASE),
        PRAZO_DIAS=config.PRAZO_DIAS,
        PRAZOS=config.PRAZOS,
        PRAZO_RETIRADA_DIAS=config.PRAZO_RETIRADA_DIAS,
        DIAS_ALERTA_BACKUP=config.DIAS_ALERTA_BACKUP,
        LIMITES=config.LIMITES,
        MAX_RENOVACOES=config.MAX_RENOVACOES,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    db.init_db(app.config["DATABASE"], app.config["PRAZO_DIAS"])
    app.teardown_appcontext(db.close_db)
    app.register_blueprint(routes.bp)
    auth.registrar(app)
    app.jinja_env.globals["nome_biblioteca"] = config.NOME_BIBLIOTECA

    # Bootstrap local (se baixado com baixar_bootstrap.py); senão usa a internet
    estatico = Path(app.static_folder)
    app.jinja_env.globals["bootstrap_local"] = all(
        (estatico / f).exists() for f in ("bootstrap.min.css", "bootstrap.bundle.min.js"))

    # Registro de eventos e erros em dados/biblioteca.log
    if not any(isinstance(h, RotatingFileHandler) for h in app.logger.handlers):
        arquivo = RotatingFileHandler(config.DATA_DIR / "biblioteca.log", maxBytes=500_000,
                                      backupCount=3, encoding="utf-8")
        arquivo.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        app.logger.addHandler(arquivo)
        app.logger.setLevel(logging.INFO)

    erros = {400: "Pedido inválido", 404: "Página não encontrada", 500: "Algo deu errado"}
    for codigo, titulo in erros.items():
        app.register_error_handler(codigo, lambda e, c=codigo, t=titulo: (render_template(
            "erro.html", titulo=t,
            mensagem="O erro foi registrado." if c == 500 else getattr(e, "description", t)), c))

    @app.template_filter("data_br")
    def data_br(valor):
        """2026-11-15 -> 15/11/2026"""
        return datetime.strptime(valor, "%Y-%m-%d").strftime("%d/%m/%Y") if valor else "—"

    return app

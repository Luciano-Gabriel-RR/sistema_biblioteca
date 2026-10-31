"""Login do bibliotecário e proteção CSRF."""
import hmac
import secrets

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db

bp = Blueprint("auth", __name__)
LIVRES = {"auth.login", "auth.primeiro_acesso", "main.ping"}  # páginas que não exigem login


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


def _ha_bibliotecario():
    return get_db().execute("SELECT 1 FROM bibliotecarios LIMIT 1").fetchone() is not None


def registrar(app):
    app.register_blueprint(bp)
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def proteger():
        if request.endpoint in (None, "static"):
            return None
        if request.method == "POST":
            esperado = session.get("csrf")
            if not esperado or not hmac.compare_digest(request.form.get("csrf_token", ""), esperado):
                abort(400, "Formulário inválido ou sessão expirada. Volte e tente de novo.")
        if request.endpoint in LIVRES:
            return None
        if not _ha_bibliotecario():
            return redirect(url_for("auth.primeiro_acesso"))
        if "bibliotecario" not in session:
            return redirect(url_for("auth.login"))
        return None


@bp.route("/primeiro-acesso", methods=["GET", "POST"])
def primeiro_acesso():
    """Cria o primeiro bibliotecário. Só funciona enquanto não existir nenhum."""
    if _ha_bibliotecario():
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip().lower()
        senha = request.form.get("senha", "")
        if not usuario:
            flash("Informe o nome de usuário.", "danger")
        elif len(senha) < 8:
            flash("A senha precisa ter pelo menos 8 caracteres.", "danger")
        elif senha != request.form.get("confirmar", ""):
            flash("As senhas não conferem.", "danger")
        else:
            db = get_db()
            with db:
                db.execute("INSERT INTO bibliotecarios (usuario, senha_hash) VALUES (?, ?)",
                           (usuario, generate_password_hash(senha)))
            flash("Conta criada. Entre com seus dados.", "success")
            return redirect(url_for("auth.login"))
    return render_template("login.html", primeiro=True)


@bp.route("/entrar", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = get_db().execute("SELECT * FROM bibliotecarios WHERE usuario = ?",
                                   (request.form.get("usuario", "").strip().lower(),)).fetchone()
        if usuario and check_password_hash(usuario["senha_hash"], request.form.get("senha", "")):
            session.clear()
            session["bibliotecario"] = usuario["usuario"]
            return redirect(url_for("main.index"))
        current_app.logger.warning("Login falhou para o usuário %r", request.form.get("usuario", ""))
        flash("Usuário ou senha incorretos.", "danger")
    return render_template("login.html", primeiro=False)


@bp.post("/sair")
def sair():
    session.clear()
    return redirect(url_for("auth.login"))

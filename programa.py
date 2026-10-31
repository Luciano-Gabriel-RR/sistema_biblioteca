"""Abre a biblioteca como um PROGRAMA: janela própria, sem barra de endereço nem abas.

    python programa.py              abre a janela do sistema (e encerra tudo ao fechar a janela)
    python programa.py --navegador  abre no navegador comum, com botão Encerrar no topo

No Windows, a janela é o Edge (ou Chrome) em modo aplicativo. No Linux, a janela é aberta com: (1) uma janela NATIVA (pacote pywebview, sem navegador) ou, se não houver,
(2) Chrome, Edge, Chromium ou Brave em "modo aplicativo". O navegador comum NUNCA é aberto por conta própria;
se nada funcionar, aparece um aviso explicando como instalar (Linux: bash instalar.sh).

    python programa.py --diagnostico  mostra o que falta neste computador
    python programa.py --chromium     força o modo aplicativo do Chrome/Edge
"""
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
import webbrowser

import config
from biblioteca import create_app


def _criar_servidor(app, porta):
    """Devolve (função que roda o servidor, porta real). Usa waitress; se faltar, o servidor do Flask."""
    try:
        from waitress.server import create_server
    except ImportError:
        from werkzeug.serving import make_server

        servidor = make_server("127.0.0.1", porta, app, threaded=True)
        return servidor.serve_forever, servidor.server_port
    servidor = create_server(app, host="127.0.0.1", port=porta)
    return servidor.run, getattr(servidor, "effective_port", None) or servidor.socket.getsockname()[1]


def _porta_livre(porta):
    """Confere se a porta está livre (o servidor do Flask encerra o programa, em vez de avisar, se estiver ocupada)."""
    with socket.socket() as teste:
        if os.name != "nt":  # no Linux/Mac, ignora conexões antigas já encerradas; no Windows isso liberaria porta em uso
            teste.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            teste.bind(("127.0.0.1", porta))
        except OSError:
            return False
    return True


def _registrar(texto):
    """Anota em dados/programa.log (útil quando o programa é aberto por ícone, sem terminal)."""
    try:
        with open(config.DATA_DIR / "programa.log", "a", encoding="utf-8") as log:
            log.write(time.strftime("%Y-%m-%d %H:%M:%S ") + texto + "\n")
    except OSError:
        pass


def iniciar_servidor(app):
    """Liga o sistema só neste computador. Usa a porta 8000 (ou uma livre, se estiver ocupada)."""
    porta = int(os.environ.get("BIBLIOTECA_PORTA", 8000))
    if not _porta_livre(porta):
        porta = 0  # 0 = o sistema escolhe uma porta livre
    try:
        rodar, porta_real = _criar_servidor(app, porta)
    except OSError:
        rodar, porta_real = _criar_servidor(app, 0)
    threading.Thread(target=rodar, daemon=True).start()
    return f"http://127.0.0.1:{porta_real}"


def _navegadores():
    """Navegadores baseados em Chromium instalados neste computador (os que abrem em 'modo aplicativo')."""
    nomes = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
             "microsoft-edge", "microsoft-edge-stable", "brave-browser"]
    candidatos = [shutil.which(n) for n in nomes]
    if sys.platform == "win32":
        bases = [os.environ.get(v, "") for v in ("ProgramFiles(x86)", "ProgramFiles", "LocalAppData")]
        relativos = [r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"]
        candidatos = [os.path.join(b, r) for r in relativos for b in bases if b] + candidatos
    elif sys.platform == "darwin":
        candidatos += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                       "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    return [c for c in dict.fromkeys(candidatos) if c and os.path.exists(c)]


def _vigiar_janela(app):
    """Rede de segurança: se a página parar de avisar que está aberta (janela fechada) mas o processo do
    navegador continuar vivo em segundo plano, encerra o programa."""
    limite = int(os.environ.get("BIBLIOTECA_LIMITE_PING", 180))  # segundos (janelas minimizadas avisam mais devagar)
    intervalo = max(1, min(10, limite // 3))

    def vigiar():
        while True:
            time.sleep(intervalo)
            ultimo = app.config.get("ULTIMO_PING")
            if ultimo and time.monotonic() - ultimo > limite:
                time.sleep(intervalo)  # confirma (o computador pode ter acabado de acordar)
                if time.monotonic() - app.config["ULTIMO_PING"] > limite:
                    os._exit(0)

    threading.Thread(target=vigiar, daemon=True).start()


def abrir_como_aplicativo(url, app):
    """Janela sem barra de endereço. Perfil próprio, para o processo durar enquanto a janela estiver aberta."""
    perfil = config.DATA_DIR / "perfil_janela"
    perfil.mkdir(parents=True, exist_ok=True)
    _vigiar_janela(app)
    for exe in _navegadores():
        inicio = time.time()
        try:
            subprocess.Popen([exe, f"--app={url}", f"--user-data-dir={perfil}", "--no-first-run",
                              "--no-default-browser-check", "--window-size=1280,860"]).wait()
        except OSError:
            continue
        if time.time() - inicio > 3:  # a janela abriu e foi fechada pelo usuário
            return True
    return False  # nenhum abriu (ou todos falharam logo): tenta o próximo método


def abrir_janela_nativa(url):
    """Janela nativa (pywebview): o sistema aparece dentro do próprio programa, sem navegador."""
    try:
        import webview
    except Exception as erro:
        print("Janela nativa indisponível (pywebview não instalado):", erro, flush=True)
        _registrar(f"pywebview não instalado: {erro}")
        return False
    try:
        try:
            webview.settings["ALLOW_DOWNLOADS"] = True
        except Exception:
            pass
        webview.create_window(config.NOME_BIBLIOTECA, url, width=1280, height=840, min_size=(900, 600))
        try:
            webview.start(private_mode=False, storage_path=str(config.DATA_DIR / "perfil_nativo"))
        except TypeError:  # pywebview antigo
            webview.start()
        return True
    except Exception as erro:
        print("Janela nativa indisponível:", erro, flush=True)
        _registrar(f"Janela nativa indisponível: {erro}")
        return False


def _ajuda_instalacao():
    if sys.platform == "win32":
        return ("Instale o Microsoft Edge ou o Google Chrome e abra o programa de novo.\n\n"
                "Se continuar com problema, veja o arquivo dados\\programa.log.")
    return ("Para instalar o que falta, abra o Terminal na pasta do sistema e rode:\n"
            "    bash instalar.sh\n\n"
            "Depois, abra o ícone de novo. Se continuar com problema, rode:\n"
            "    bash iniciar_biblioteca.sh --diagnostico")


def _avisar(titulo, texto):
    """Mostra um aviso numa janelinha (sem abrir navegador). Sem ambiente gráfico, escreve no terminal e no log."""
    print(f"{titulo}\n{texto}", flush=True)
    _registrar(f"{titulo}: {texto}")
    try:
        if sys.platform == "win32":
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, texto, titulo, 0x10)
            return
        for comando in (["zenity", "--error", "--width=480", "--title", titulo, "--text", texto],
                        ["kdialog", "--error", texto, "--title", titulo]):
            if shutil.which(comando[0]):
                subprocess.run(comando, check=False)
                return
        import tkinter
        from tkinter import messagebox

        raiz = tkinter.Tk()
        raiz.withdraw()
        messagebox.showerror(titulo, texto)
        raiz.destroy()
    except Exception:
        pass


def diagnostico():
    """Mostra o que falta neste computador para a janela do programa abrir."""
    print("Python:", sys.version.split()[0], "em", sys.executable)
    print("Tela:", os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY") or "NENHUMA (sem ambiente gráfico?)")
    try:
        import gi

        for nome in ("Gtk", "WebKit2"):
            print(f"{nome}:", gi.Repository.get_default().enumerate_versions(nome) or "NÃO ENCONTRADO")
    except Exception as erro:
        print("PyGObject (gi): NÃO ENCONTRADO:", erro)
    try:
        import webview

        print("pywebview:", getattr(webview, "__version__", "instalado"))
    except Exception as erro:
        print("pywebview: NÃO INSTALADO:", erro)
    for modulo in ("PyQt6", "PyQt5", "PySide6"):
        try:
            __import__(modulo)
            print(f"{modulo}: instalado")
        except Exception:
            pass
    print("Chrome/Chromium/Edge:", _navegadores() or "nenhum")


def no_navegador_comum(app, url):
    """Só quando pedido (--navegador). O sistema fica ligado até clicar em Encerrar (ou Ctrl+C)."""
    app.config["MODO_PROGRAMA"] = "navegador"
    webbrowser.open(url)
    print("Sistema ligado. Use o botão Encerrar no topo da página (ou Ctrl+C aqui) para fechar.", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


def main():
    if "--diagnostico" in sys.argv:
        diagnostico()
        return
    app = create_app()
    url = iniciar_servidor(app)
    print(f"{config.NOME_BIBLIOTECA} em {url}", flush=True)
    if "--navegador" in sys.argv:  # só se você pedir
        no_navegador_comum(app, url)
        return
    if "--chromium" in sys.argv:
        if abrir_como_aplicativo(url, app):
            return
    elif sys.platform == "win32":  # no Windows o Edge (já instalado) abre sem barra de endereço: o caminho mais confiável
        if abrir_como_aplicativo(url, app) or abrir_janela_nativa(url):
            return
    elif abrir_janela_nativa(url) or abrir_como_aplicativo(url, app):
        return  # a janela foi fechada: o programa termina e leva o servidor junto
    _avisar("Biblioteca Pré Universitário",
            "Não foi possível abrir a janela do programa neste computador.\n\n" + _ajuda_instalacao())
    sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # sem terminal (duplo clique), o erro fica registrado em dados/programa.log
        _registrar(traceback.format_exc())
        raise

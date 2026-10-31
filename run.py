"""Inicia o sistema. `python run.py` (servidor de produção) ou `python run.py --debug` (desenvolvimento)."""
import os
import sys

from biblioteca import create_app

app = create_app()

if __name__ == "__main__":
    host = os.environ.get("BIBLIOTECA_HOST", "127.0.0.1")  # use 0.0.0.0 para outros PCs da rede acessarem
    porta = int(os.environ.get("BIBLIOTECA_PORTA", 8000))
    if "--debug" in sys.argv:
        app.run(debug=True, host=host, port=porta)
    else:
        from waitress import serve

        print(f"Biblioteca no ar em http://{host}:{porta}  (Ctrl+C para parar)")
        serve(app, host=host, port=porta)

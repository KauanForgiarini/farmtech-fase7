"""
FarmTech Solutions - lançador do sistema integrado (Fase 7).

Dispara pelo terminal os mesmos serviços que a dashboard dispara por botão.

    python farmtech.py --listar                      # catálogo de serviços
    python farmtech.py pipeline                      # executa todas as fases em ordem
    python farmtech.py dashboard                     # abre a dashboard (Streamlit)
    python farmtech.py fase1 [--exemplo | --listar | --adicionar soja "Talhão 9" 200 100]
    python farmtech.py fase1-estatistica
    python farmtech.py fase2 [--leituras 72 --cenario seca --clima | --serial COM3]
    python farmtech.py fase3 [--backend oracle]
    python farmtech.py fase4
    python farmtech.py fase6 [--imagens foto.jpg]
    python farmtech.py alertas [--modo local|s3|lambda|sns]
    python farmtech.py aws-deploy --email voce@exemplo.com

Argumentos após o nome do serviço são repassados ao programa da fase.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))

from farmtech_core.config import configurar_saida  # noqa: E402
from farmtech_core.servicos import (ORDEM_PIPELINE, SERVICOS, ambiente_filho,  # noqa: E402
                                    comando_terminal, executar)


def listar() -> None:
    print("Serviços disponíveis (python farmtech.py <serviço> [argumentos]):\n")
    for s in SERVICOS.values():
        print(f"  {s.chave:<18} {s.fase:<7} {s.nome}")
        print(f"  {'':<18} {'':<7} {s.descricao}")
    print("\n  pipeline           todas   Executa as fases em sequência (dados -> banco -> alertas)")
    print("  dashboard          Fase 4  Dashboard final em Streamlit (botões para cada serviço)")


def pipeline() -> int:
    for chave in ORDEM_PIPELINE:
        print(f"\n{'=' * 70}\n>>> {SERVICOS[chave].fase} | {SERVICOS[chave].nome}\n"
              f"    {comando_terminal(chave)}\n{'=' * 70}")
        resultado = executar(chave)
        print(resultado["saida"].rstrip())
        if resultado["codigo"] != 0:
            print(f"[ERRO] {chave} terminou com código {resultado['codigo']}")
            return resultado["codigo"]
    print("\nPipeline concluído. Abra a dashboard com: python farmtech.py dashboard")
    return 0


def main(argv: list[str]) -> int:
    configurar_saida()
    if not argv or argv[0] in {"-h", "--help", "--listar"}:
        print(__doc__)
        listar()
        return 0
    comando, *args = argv
    if comando == "pipeline":
        return pipeline()
    if comando == "dashboard":
        return subprocess.call([sys.executable, "-m", "streamlit", "run",
                                str(RAIZ / "src" / "dashboard" / "app.py"), *args],
                               cwd=RAIZ, env=ambiente_filho())
    if comando not in SERVICOS:
        print(f"Serviço desconhecido: {comando}\n")
        listar()
        return 2
    # sem argumentos extras usa os padrões do catálogo (os mesmos dos botões da dashboard)
    resultado = executar(comando, args or None, capturar=False)
    return resultado["codigo"]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

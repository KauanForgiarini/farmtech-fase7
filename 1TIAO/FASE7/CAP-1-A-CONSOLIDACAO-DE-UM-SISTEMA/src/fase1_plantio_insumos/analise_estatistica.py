"""
FarmTech Solutions - Fase 1: orquestrador da análise estatística.

Executa o script em R (analise_estatistica.R) quando o Rscript está instalado.
Sem R, calcula em Python exatamente as mesmas estatísticas (desvio padrão
amostral, n-1), para que a dashboard funcione em qualquer máquina.

Uso:
    python src/fase1_plantio_insumos/analise_estatistica.py [--forcar-python]
"""

from __future__ import annotations

import argparse
import glob
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from farmtech_core.config import ARQUIVOS, RAIZ, configurar_saida

SCRIPT_R = Path(__file__).resolve().with_name("analise_estatistica.R")


def localizar_rscript() -> str | None:
    encontrado = shutil.which("Rscript")
    if encontrado:
        return encontrado
    candidatos = sorted(glob.glob(r"C:\Program Files\R\R-*\bin\Rscript.exe"))
    return candidatos[-1] if candidatos else None


def resumir(valores: pd.Series, grupo: str, variavel: str) -> dict:
    v = pd.to_numeric(valores, errors="coerce").dropna()
    media = v.mean()
    desvio = v.std(ddof=1) if len(v) > 1 else 0.0
    return {"grupo": grupo, "variavel": variavel, "n": len(v), "media": round(media, 4),
            "desvio_padrao": round(desvio, 4), "mediana": round(v.median(), 4),
            "minimo": round(v.min(), 4), "maximo": round(v.max(), 4),
            "coef_variacao_pct": round(100 * desvio / media, 2) if media else 0.0}


def analisar_em_python() -> pd.DataFrame:
    linhas = []
    if ARQUIVOS["talhoes"].exists():
        talhoes = pd.read_csv(ARQUIVOS["talhoes"])
        for cultura, sub in talhoes.groupby("CULTURA"):
            linhas.append(resumir(sub["AREA_HA"], f"talhoes_{cultura}", "area_ha"))
            linhas.append(resumir(sub["NUM_RUAS"], f"talhoes_{cultura}", "num_ruas"))
        print("Área plantada por cultura (ha):")
        print(talhoes.groupby("CULTURA")["AREA_HA"].sum().round(2).to_string())
    if ARQUIVOS["insumos"].exists():
        insumos = pd.read_csv(ARQUIVOS["insumos"])
        print("\nTotal de cada insumo:")
        print(insumos.groupby(["INSUMO", "UNIDADE_TOTAL"])["QUANTIDADE_TOTAL"].sum()
              .round(2).to_string())
    if ARQUIVOS["leituras"].exists():
        leituras = pd.read_csv(ARQUIVOS["leituras"])
        for coluna in ["UMIDADE_SOLO_PCT", "PH_SOLO", "TEMPERATURA_C", "CHUVA_PREVISTA_MM"]:
            linhas.append(resumir(leituras[coluna], "sensores", coluna.lower()))
        print("\nFrequência das decisões da bomba:")
        print(leituras["MOTIVO_DECISAO"].value_counts().to_string())
        print(f"\nBomba ligada em {100 * leituras['BOMBA_LIGADA'].mean():.1f}% das leituras.")
        print("Correlação umidade x temperatura: "
              f"{leituras['UMIDADE_SOLO_PCT'].corr(leituras['TEMPERATURA_C']):.3f}")
    tabela = pd.DataFrame(linhas)
    tabela["ferramenta"] = "Python"
    return tabela


def main() -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(description="Estatística descritiva FarmTech (R/Python)")
    parser.add_argument("--forcar-python", action="store_true", help="não tenta usar o R")
    args = parser.parse_args()

    rscript = None if args.forcar_python else localizar_rscript()
    if rscript:
        print(f"Executando a análise em R: {rscript}")
        processo = subprocess.run([rscript, str(SCRIPT_R), str(RAIZ)], cwd=RAIZ,
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace")
        print(processo.stdout)
        if processo.returncode == 0:
            return 0
        print("[AVISO] O R retornou erro; usando o cálculo equivalente em Python.")
        print(processo.stderr)
    else:
        print("Rscript não encontrado: estatística calculada em Python com as mesmas "
              "fórmulas do script R (src/fase1_plantio_insumos/analise_estatistica.R).\n")

    tabela = analisar_em_python()
    tabela.to_csv(ARQUIVOS["estatisticas"], index=False)
    print("\nEstatísticas descritivas:")
    print(tabela[["grupo", "variavel", "n", "media", "desvio_padrao", "mediana"]]
          .to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

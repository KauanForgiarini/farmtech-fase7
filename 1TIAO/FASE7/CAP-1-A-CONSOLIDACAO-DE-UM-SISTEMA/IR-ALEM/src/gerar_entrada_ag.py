"""
Ir Além 2 - geração da entrada do algoritmo genético (executada uma única vez).

Parte dos talhões cadastrados na Fase 1 (data/fase1_talhoes.csv), divide cada
um em 3 setores e cria 3 intervenções candidatas por setor:

  * irrigação suplementar  -> consome água (m³) e orçamento (R$)
  * adubação de cobertura  -> consome orçamento
  * calagem (correção pH)  -> consome orçamento

Cada intervenção tem um ganho esperado de produtividade (sacas) convertido em
receita (R$). O problema é uma mochila binária com duas restrições (água da
semana e orçamento): escolher o conjunto que maximiza a receita.

Os valores de água são múltiplos de 10 m³ e os custos múltiplos de R$ 100,
o que permite calcular o ótimo exato por programação dinâmica para comparar.

Uso:
    python IR-ALEM/src/gerar_entrada_ag.py
Saídas:
    IR-ALEM/data/ag_entrada_intervencoes.csv
    IR-ALEM/data/ag_restricoes.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
SAIDA = RAIZ / "IR-ALEM" / "data"
SEMENTE = 574005
PRECO_SACA = {"soja": 125.0, "milho": 62.0}       # R$/saca (referência CEPEA 2026)
GANHO_SC_HA = {                                    # ganho máximo por hectare (sacas)
    "irrigacao": {"soja": 9.0, "milho": 18.0},
    "adubacao": {"soja": 7.0, "milho": 14.0},
    "calagem": {"soja": 5.0, "milho": 9.0},
}


def gerar(semente: int = SEMENTE) -> tuple[pd.DataFrame, dict]:
    rng = np.random.default_rng(semente)
    talhoes = pd.read_csv(RAIZ / "data" / "fase1_talhoes.csv")
    itens = []
    for _, talhao in talhoes.iterrows():
        for setor in range(1, 4):
            area = round(talhao["AREA_HA"] / 3 * rng.uniform(0.85, 1.15), 2)
            deficit_hidrico = rng.uniform(0.1, 1.0)
            deficit_nutrientes = rng.uniform(0.1, 1.0)
            acidez = rng.uniform(0.0, 1.0)
            cultura = talhao["CULTURA"]
            nome = f"{talhao['NOME'].split(' - ')[0]} · S{setor}"
            lamina_mm = rng.uniform(15, 30)
            agua = int(round(area * lamina_mm * 10 / 10) * 10)         # 1 mm em 1 ha = 10 m³
            candidatos = [
                ("irrigacao", agua, area * (0.30 * lamina_mm * 10 + 120), deficit_hidrico),
                ("adubacao", 0, area * rng.uniform(450, 650), deficit_nutrientes),
                ("calagem", 0, area * rng.uniform(300, 450), acidez),
            ]
            for tipo, agua_m3, custo, intensidade in candidatos:
                ganho_sc = area * GANHO_SC_HA[tipo][cultura] * intensidade
                itens.append({
                    "item": len(itens), "setor": nome, "talhao_id": int(talhao["ID_TALHAO"]),
                    "cultura": cultura, "intervencao": tipo, "area_ha": area,
                    "agua_m3": agua_m3, "custo_rs": int(round(custo / 100) * 100),
                    "ganho_sacas": round(ganho_sc, 2),
                    "receita_rs": int(round(ganho_sc * PRECO_SACA[cultura])),
                })
    df = pd.DataFrame(itens)
    restricoes = {
        "agua_disponivel_m3": int(round(df["agua_m3"].sum() * 0.45 / 10) * 10),
        "orcamento_rs": int(round(df["custo_rs"].sum() * 0.40 / 100) * 100),
        "unidade_agua_m3": 10, "unidade_custo_rs": 100, "semente": semente,
        "descricao": "45% da água e 40% do orçamento necessários para todas as intervenções",
    }
    return df, restricoes


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    df, restricoes = gerar()
    SAIDA.mkdir(parents=True, exist_ok=True)
    df.to_csv(SAIDA / "ag_entrada_intervencoes.csv", index=False)
    (SAIDA / "ag_restricoes.json").write_text(json.dumps(restricoes, indent=2, ensure_ascii=False),
                                              encoding="utf-8")
    print(f"{len(df)} intervenções salvas; restrições: {restricoes}")


if __name__ == "__main__":
    main()

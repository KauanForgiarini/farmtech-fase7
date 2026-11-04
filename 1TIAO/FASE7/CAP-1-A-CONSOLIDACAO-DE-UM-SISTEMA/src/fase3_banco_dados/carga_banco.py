"""
FarmTech Solutions - Fase 3: ETL do sistema integrado.

Recria o esquema relacional e carrega no banco (SQLite ou Oracle) os arquivos
produzidos pelos demais serviços em data/:

    fase1_talhoes.csv / fase1_insumos.csv  -> TALHAO, APLICACAO_INSUMO
    fase2_leituras_sensores.csv            -> LEITURA_SENSOR
    fase4_previsoes.csv                    -> PREVISAO_ML
    fase6_deteccoes.csv                    -> DETECCAO_VISAO
    fase7_alertas.csv                      -> ALERTA

Uso:
    python src/fase3_banco_dados/carga_banco.py              # carga + consultas
    python src/fase3_banco_dados/carga_banco.py --silencioso # só a carga
    FARMTECH_DB=oracle python src/fase3_banco_dados/carga_banco.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from farmtech_core.config import ARQUIVOS, configurar_saida
from fase3_banco_dados.banco import Banco, TABELAS, ler_consultas_nomeadas
from fase7_alertas_aws.lambda_alertas.regras_alerta import CULTURAS

# arquivo de origem e colunas aceitas por tabela (a ordem segue as chaves estrangeiras)
FONTES = [
    ("TALHAO", "talhoes"),
    ("APLICACAO_INSUMO", "insumos"),
    ("LEITURA_SENSOR", "leituras"),
    ("PREVISAO_ML", "previsoes"),
    ("DETECCAO_VISAO", "deteccoes"),
    ("ALERTA", "alertas"),
]


def registros_do_csv(chave: str, colunas_validas: set[str]) -> list[dict]:
    arquivo = ARQUIVOS[chave]
    if not arquivo.exists():
        return []
    df = pd.read_csv(arquivo)
    df = df[[c for c in df.columns if c in colunas_validas]]
    return df.astype(object).where(pd.notna(df), None).to_dict(orient="records")


def colunas_da_tabela(banco: Banco, tabela: str) -> set[str]:
    cursor = banco.conexao.cursor()
    cursor.execute(f"SELECT * FROM {tabela} WHERE 1 = 0")
    return {d[0].upper() for d in cursor.description}


def carregar(banco: Banco) -> dict[str, int]:
    banco.recriar_esquema()
    banco.inserir("CULTURA", [
        {"ID_CULTURA": c["id"], "NOME": c["nome"], "PH_MIN": c["ph_min"],
         "PH_MAX": c["ph_max"], "UMIDADE_MIN": c["umidade_min"],
         "UMIDADE_MAX": c["umidade_max"], "ESPACAMENTO_M": c["espacamento_m"]}
        for c in CULTURAS.values()
    ])
    for tabela, chave in FONTES:
        banco.inserir(tabela, registros_do_csv(chave, colunas_da_tabela(banco, tabela)))
    return banco.contagens()


def imprimir_consultas(banco: Banco) -> None:
    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 12)
    for nome, sql in ler_consultas_nomeadas().items():
        print(f"\n--- Consulta: {nome} ---")
        df = banco.dataframe(sql)
        print(df.to_string(index=False) if not df.empty else "(sem registros)")


def main() -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(description="ETL e consultas do banco FarmTech (Fase 3)")
    parser.add_argument("--backend", choices=["sqlite", "oracle"],
                        help="sobrepõe a variável FARMTECH_DB")
    parser.add_argument("--silencioso", action="store_true", help="não imprime as consultas")
    parser.add_argument("--somente-consultas", action="store_true",
                        help="executa as consultas sem recarregar")
    args = parser.parse_args()

    with Banco(args.backend) as banco:
        if not args.somente_consultas:
            contagens = carregar(banco)
            resumo = ", ".join(f"{t}={contagens[t]}" for t in TABELAS)
            print(f"Banco {banco.descricao} recarregado: {resumo}")
        if not args.silencioso:
            imprimir_consultas(banco)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

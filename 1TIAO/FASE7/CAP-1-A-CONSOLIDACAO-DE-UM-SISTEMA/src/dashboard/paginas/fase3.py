"""Fase 3: banco de dados relacional (SQLite ou Oracle) e consultas analíticas."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.componentes import banco_pronto, botao_servico, cabecalho, consulta_nomeada
from fase3_banco_dados.banco import PASTA_SQL, TABELAS, Banco, ler_consultas_nomeadas

RELACOES = """
CULTURA (1) ──< TALHAO (1) ──< APLICACAO_INSUMO        ← Fase 1
                   │
                   └──< LEITURA_SENSOR (1) ── (1) PREVISAO_ML   ← Fases 2 e 4
DETECCAO_VISAO                                                    ← Fase 6
ALERTA                                                            ← Fase 7
"""


def render() -> None:
    cabecalho("🗄️ Fase 3 — Banco de dados relacional",
              "Modelo normalizado que recebe os dados de todas as fases · Oracle (FIAP) ou SQLite")

    esquerda, direita = st.columns([2, 3])
    with esquerda:
        try:
            with Banco() as banco:
                st.metric("Banco em uso", banco.descricao)
                contagens = banco.contagens() if banco.tabelas_existem() else {}
        except Exception as erro:
            st.error(f"Não foi possível conectar: {erro}")
            contagens = {}
        botao_servico("fase3", rotulo="▶ Executar ETL e consultas")
        st.caption("Para usar o Oracle da FIAP, defina no `.env`: FARMTECH_DB=oracle, "
                   "ORACLE_USER e ORACLE_PASSWORD.")
    with direita:
        st.markdown("**Modelo entidade-relacionamento**")
        st.code(RELACOES, language="text")
        if contagens:
            st.dataframe(pd.DataFrame({"Tabela": list(contagens), "Registros": list(contagens.values())}),
                         hide_index=True, width="stretch")

    if not banco_pronto():
        st.info("Execute o ETL para criar as tabelas.")
        return
    st.subheader("Consultas analíticas (SQL padrão: Oracle e SQLite)")
    consultas = ler_consultas_nomeadas()
    nome = st.selectbox("Consulta", list(consultas), format_func=lambda n: n.replace("_", " "))
    st.code(consultas[nome], language="sql")
    st.dataframe(consulta_nomeada(nome), hide_index=True, width="stretch")

    with st.expander("Ver DDL Oracle (01_ddl_farmtech.sql)"):
        st.code((PASTA_SQL / "oracle" / "01_ddl_farmtech.sql").read_text(encoding="utf-8"),
                language="sql")
    with st.expander("Ver dados de uma tabela"):
        tabela = st.selectbox("Tabela", TABELAS, index=3)
        with Banco() as banco:
            st.dataframe(banco.dataframe(f"SELECT * FROM {tabela}"), hide_index=True,
                         width="stretch")

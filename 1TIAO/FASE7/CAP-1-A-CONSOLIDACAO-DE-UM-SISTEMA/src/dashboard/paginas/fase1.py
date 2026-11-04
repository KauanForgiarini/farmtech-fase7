"""Fase 1: talhões, área de plantio, manejo de insumos e estatística em R."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from dashboard.componentes import (botao_servico, cabecalho, ler_csv, mostrar_saida,
                                   rodar_servico)
from farmtech_core.config import DOCS


def render() -> None:
    cabecalho("🌱 Fase 1 — Plantio e manejo de insumos",
              "Python (cálculo de área por figura geométrica e insumos) + análise estatística em R")

    talhoes, insumos = ler_csv("talhoes"), ler_csv("insumos")
    col_dados, col_acoes = st.columns([3, 2])
    with col_acoes:
        st.subheader("Serviço da Fase 1")
        botao_servico("fase1", ["--exemplo"], "▶ Recarregar talhões de exemplo", "f1_exemplo")
        with st.form("novo_talhao"):
            st.markdown("**Novo talhão**")
            cultura = st.radio("Cultura", ["soja", "milho"], horizontal=True,
                               help="Soja: talhão retangular · Milho: pivô central circular")
            nome = st.text_input("Nome", "Talhão 5 - Soja Leste")
            d1 = st.number_input("Comprimento (soja) ou raio do pivô (milho) em m",
                                 min_value=1.0, value=300.0)
            d2 = st.number_input("Largura em m (somente soja)", min_value=1.0, value=200.0)
            enviar = st.form_submit_button("Cadastrar talhão", width="stretch")
        if enviar:
            args = ["--adicionar", cultura, nome, str(d1)] + ([str(d2)] if cultura == "soja" else [])
            rodar_servico("fase1", args, "f1_add")
        mostrar_saida("f1_add")
        if not talhoes.empty:
            remover = st.selectbox("Remover talhão", talhoes.loc[talhoes["ID_TALHAO"] != 1,
                                                                  "ID_TALHAO"].tolist() or [None])
            if remover:
                botao_servico("fase1", ["--remover", str(remover)], f"Remover talhão {remover}",
                              "f1_rem", tipo="secondary")

    with col_dados:
        if talhoes.empty:
            st.info("Nenhum talhão cadastrado: use o botão ao lado.")
            return
        a, b, c = st.columns(3)
        a.metric("Talhões", len(talhoes))
        b.metric("Área total", f"{talhoes['AREA_HA'].sum():.2f} ha")
        c.metric("Metros lineares de plantio", f"{talhoes['METROS_LINEARES'].sum():,.0f} m")
        st.dataframe(talhoes[["ID_TALHAO", "NOME", "CULTURA", "FORMA", "DIMENSAO_1_M",
                              "DIMENSAO_2_M", "AREA_HA", "NUM_RUAS", "METROS_LINEARES"]],
                     hide_index=True, width="stretch")
        st.plotly_chart(px.bar(talhoes, x="NOME", y="AREA_HA", color="CULTURA",
                               labels={"AREA_HA": "Área (ha)", "NOME": ""},
                               color_discrete_map={"soja": "#2d6a4f", "milho": "#d4a017"},
                               title="Área de plantio por talhão"), width="stretch")
        if not insumos.empty:
            st.markdown("**Manejo de insumos calculado**")
            tabela = insumos.merge(talhoes[["ID_TALHAO", "NOME"]], on="ID_TALHAO")
            st.dataframe(tabela[["NOME", "INSUMO", "DOSE", "UNIDADE", "QUANTIDADE_TOTAL",
                                 "UNIDADE_TOTAL"]], hide_index=True, width="stretch")

    st.divider()
    st.subheader("Análise estatística (R)")
    esquerda, direita = st.columns([2, 3])
    with esquerda:
        botao_servico("fase1-estatistica", rotulo="▶ Executar análise estatística")
        st.caption("Usa o Rscript se o R estiver instalado; caso contrário, aplica as mesmas "
                   "fórmulas em Python (desvio padrão amostral).")
    with direita:
        estatisticas = ler_csv("estatisticas")
        if not estatisticas.empty:
            st.caption(f"Calculado em: {estatisticas['ferramenta'].iloc[0]}")
            st.dataframe(estatisticas.drop(columns=["ferramenta"]), hide_index=True,
                         width="stretch")
        grafico_r = DOCS / "evidencias" / "r_umidade_por_decisao.png"
        if grafico_r.exists():
            st.image(str(grafico_r), caption="Gráfico gerado pelo script R")

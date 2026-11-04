"""Página inicial: visão geral do sistema integrado e execução do pipeline completo."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from dashboard.componentes import banco_pronto, cabecalho, consultar
from farmtech_core.config import ARQUIVOS, DOCS
from farmtech_core.servicos import ORDEM_PIPELINE, SERVICOS, executar

ARTEFATOS = [
    ("Fase 1", "Talhões e insumos", "talhoes"),
    ("Fase 1", "Estatística (R/Python)", "estatisticas"),
    ("Fase 2", "Leituras do ESP32", "leituras"),
    ("Fase 3", "Banco relacional", "banco_sqlite"),
    ("Fase 4", "Previsões dos modelos", "previsoes"),
    ("Fase 6", "Detecções YOLO", "deteccoes"),
    ("Fase 7", "Histórico de alertas", "alertas"),
    ("Fase 7", "Recursos AWS implantados", "aws_config"),
]


def render() -> None:
    cabecalho("🌱 FarmTech Solutions — Sistema Integrado de Gestão da Fazenda",
              "Fase 7 · Consolidação das Fases 1 a 6 + serviço de alertas na AWS")

    if banco_pronto():
        total = consultar("""
            SELECT (SELECT COUNT(*) FROM TALHAO) AS TALHOES,
                   (SELECT ROUND(SUM(AREA_HA), 1) FROM TALHAO) AS AREA,
                   (SELECT COUNT(*) FROM LEITURA_SENSOR) AS LEITURAS,
                   (SELECT SUM(BOMBA_LIGADA) FROM LEITURA_SENSOR) AS IRRIGANDO,
                   (SELECT COUNT(*) FROM DETECCAO_VISAO) AS DETECCOES,
                   (SELECT COUNT(*) FROM ALERTA) AS ALERTAS
            FROM CULTURA WHERE ID_CULTURA = 1""")
        if not total.empty:
            t = total.iloc[0]
            colunas = st.columns(6)
            colunas[0].metric("Talhões (Fase 1)", int(t["TALHOES"] or 0))
            colunas[1].metric("Área plantada", f"{t['AREA'] or 0} ha")
            colunas[2].metric("Leituras ESP32 (Fase 2)", int(t["LEITURAS"] or 0))
            colunas[3].metric("Leituras irrigando", int(t["IRRIGANDO"] or 0))
            colunas[4].metric("Detecções YOLO (Fase 6)", int(t["DETECCOES"] or 0))
            colunas[5].metric("Alertas (Fase 7)", int(t["ALERTAS"] or 0))
    else:
        st.warning("O banco ainda não foi criado. Execute o pipeline completo abaixo "
                   "ou `python farmtech.py pipeline` no terminal.")

    esquerda, direita = st.columns([3, 2])
    with esquerda:
        st.subheader("Arquitetura")
        figura = DOCS / "arquitetura" / "arquitetura_farmtech_fase7.png"
        if figura.exists():
            st.image(str(figura), width="stretch")
        st.markdown("""
        **Fluxo dos dados:** a Fase 1 cadastra os talhões e o manejo de insumos; o ESP32 da
        Fase 2 mede o solo e decide a bomba; o banco da Fase 3 consolida tudo; os modelos da
        Fase 4 preveem irrigação, adubação e rendimento; a visão computacional da Fase 6 vigia
        as câmeras; e o serviço da Fase 7 (Lambda + SNS na infraestrutura AWS da Fase 5) envia
        aos funcionários os alertas com as ações corretivas.
        """)
    with direita:
        st.subheader("Executar o sistema completo")
        st.caption("Terminal: `python farmtech.py pipeline`")
        if st.button("▶ Executar pipeline (Fases 1 → 7)", type="primary",
                     width="stretch"):
            barra = st.progress(0.0)
            log = []
            for i, chave in enumerate(ORDEM_PIPELINE, start=1):
                barra.progress(i / len(ORDEM_PIPELINE), text=SERVICOS[chave].nome)
                resultado = executar(chave)
                log.append(f"### {SERVICOS[chave].fase} · {SERVICOS[chave].nome} "
                           f"({resultado['duracao_s']} s, código {resultado['codigo']})\n"
                           + resultado["saida"])
                if resultado["codigo"] != 0:
                    st.error(f"Falha em {chave}")
                    break
            st.session_state["log_pipeline"] = "\n\n".join(log)
            st.cache_data.clear()
            st.rerun()
        if st.session_state.get("log_pipeline"):
            with st.expander("Saída do pipeline"):
                st.code(st.session_state["log_pipeline"][-20000:], language="text")

        st.subheader("Estado dos serviços")
        linhas = []
        for fase, nome, chave in ARTEFATOS:
            arquivo = ARQUIVOS[chave]
            linhas.append({
                "Fase": fase, "Artefato": nome,
                "Status": "✅" if arquivo.exists() else "⏳",
                "Atualizado": (datetime.fromtimestamp(arquivo.stat().st_mtime)
                               .strftime("%d/%m %H:%M") if arquivo.exists() else "-"),
            })
        st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")

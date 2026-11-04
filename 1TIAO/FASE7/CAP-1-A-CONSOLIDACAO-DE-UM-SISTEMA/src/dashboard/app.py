"""
FarmTech Solutions - Dashboard final (evolução da dashboard da Fase 4).

Centraliza o sistema integrado: cada página corresponde a uma fase e tem um
botão que dispara o serviço correspondente (o mesmo comando de terminal do
farmtech.py). Os dados exibidos vêm do banco relacional da Fase 3.

Execução (na pasta do projeto):
    python farmtech.py dashboard
    # ou: streamlit run src/dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

st.set_page_config(page_title="FarmTech Solutions - Sistema Integrado", page_icon="🌱",
                   layout="wide", initial_sidebar_state="expanded")

from dashboard.componentes import banco_pronto  # noqa: E402
from dashboard.paginas import (alertas, fase1, fase2, fase3, fase4, fase5, fase6,  # noqa: E402
                               ir_alem, visao_geral)
from farmtech_core.config import ARQUIVOS  # noqa: E402
from farmtech_core.servicos import executar  # noqa: E402

# Primeiro acesso após clonar o repositório: monta o banco a partir dos CSVs versionados
if "banco_verificado" not in st.session_state:
    if not banco_pronto() and ARQUIVOS["leituras"].exists():
        with st.spinner("Criando o banco de dados da Fase 3 a partir dos arquivos de data/..."):
            executar("fase3", ["--silencioso"])
    st.session_state["banco_verificado"] = True

PAGINAS = [
    st.Page(visao_geral.render, title="Visão geral", icon="🏠", url_path="inicio", default=True),
    st.Page(fase1.render, title="Fase 1 · Plantio e insumos", icon="🌱", url_path="fase1"),
    st.Page(fase2.render, title="Fase 2 · Sensores e irrigação", icon="📡", url_path="fase2"),
    st.Page(fase3.render, title="Fase 3 · Banco de dados", icon="🗄️", url_path="fase3"),
    st.Page(fase4.render, title="Fase 4 · Previsões de ML", icon="🔮", url_path="fase4"),
    st.Page(fase5.render, title="Fase 5 · Infraestrutura AWS", icon="☁️", url_path="fase5"),
    st.Page(fase6.render, title="Fase 6 · Visão computacional", icon="👁️", url_path="fase6"),
    st.Page(alertas.render, title="Fase 7 · Alertas AWS", icon="🚨", url_path="alertas"),
    st.Page(ir_alem.render, title="Ir Além · Rekognition e AG", icon="🧬", url_path="ir-alem"),
]

with st.sidebar:
    st.markdown("### 🌱 FarmTech Solutions")
    st.caption("Fase 7 · A consolidação de um sistema\n\nGrupo 27 · FIAP Inteligência Artificial")

navegacao = st.navigation(PAGINAS)
navegacao.run()

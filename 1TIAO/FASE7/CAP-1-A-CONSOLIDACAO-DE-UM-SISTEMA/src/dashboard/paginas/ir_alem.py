"""Ir Além: Amazon Rekognition (1) e algoritmo genético para alocação de recursos (2)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.componentes import cabecalho
from farmtech_core.config import RAIZ

IR_ALEM = RAIZ / "IR-ALEM"


def render() -> None:
    cabecalho("🧬 Ir Além — IA gerenciada na AWS e algoritmos genéticos",
              "Desafios opcionais da Fase 7 (documentação completa em IR-ALEM/)")
    aba1, aba2 = st.tabs(["Ir Além 1 · Amazon Rekognition", "Ir Além 2 · Algoritmo genético"])

    with aba1:
        st.image(str(IR_ALEM / "docs" / "arquitetura_rekognition.png"), width="stretch")
        st.markdown("""
        A Lambda `farmtech-rekognition` recebe cada foto enviada ao bucket (`imagens/`), chama o
        **DetectLabels** do Amazon Rekognition e reaproveita as mesmas regras de alerta da Fase 7.

        ```bash
        python IR-ALEM/src/rekognition/deploy_rekognition.py            # cria a Lambda e o gatilho
        python IR-ALEM/src/rekognition/deploy_rekognition.py --enviar data/fase6_imagens_campo/pessoa_038.jpg
        python IR-ALEM/src/rekognition/deploy_rekognition.py --comparar # Rekognition x YOLO
        ```
        """)
        comparacao = IR_ALEM / "data" / "rekognition_vs_yolo.csv"
        if comparacao.exists():
            st.dataframe(pd.read_csv(comparacao), hide_index=True, width="stretch")
        else:
            st.info("A comparação Rekognition x YOLO aparece aqui depois de rodar `--comparar` "
                    "com credenciais válidas do Learner Lab.")

    with aba2:
        resumo = IR_ALEM / "data" / "ag_resumo.csv"
        st.image(str(IR_ALEM / "docs" / "figura_fluxo_ag.png"), width="stretch")
        if resumo.exists():
            st.markdown("**Resultados (20 execuções por configuração, mesma entrada salva em arquivo)**")
            st.dataframe(pd.read_csv(resumo), hide_index=True, width="stretch")
        for nome in ["ag_comparacao_resultados.png", "ag_plano_manejo.png"]:
            if (IR_ALEM / "docs" / nome).exists():
                st.image(str(IR_ALEM / "docs" / nome), width="stretch")
        st.caption("Notebook: IR-ALEM/notebooks/ir_alem_2_algoritmo_genetico.ipynb")

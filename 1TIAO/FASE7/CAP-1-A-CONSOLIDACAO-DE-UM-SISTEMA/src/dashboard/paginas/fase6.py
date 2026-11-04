"""Fase 6: visão computacional com YOLO nas câmeras da fazenda."""

from __future__ import annotations

import json
from datetime import datetime

import streamlit as st

from dashboard.componentes import botao_servico, cabecalho, ler_csv, mostrar_saida, rodar_servico
from farmtech_core.config import (DATA, DOCS, MODELO_YOLO, PASTA_IMAGENS_VISAO,
                                  PASTA_RESULTADOS_VISAO)

BASELINE = MODELO_YOLO.with_name("yolov8n.pt")
MODELOS = {"YOLO personalizado da Fase 6 (30 épocas)": None,
           "YOLOv8n pré-treinado COCO (baseline)": str(BASELINE)}


def render() -> None:
    cabecalho("👁️ Fase 6 — Visão computacional (YOLO)",
              "Detecção de pessoas e veículos nas câmeras da propriedade")

    metricas_arquivo = MODELO_YOLO.with_name("metricas_yolo.json")
    esquerda, direita = st.columns([2, 3])
    with esquerda:
        escolha = st.radio("Modelo", list(MODELOS))
        conf = st.slider("Confiança mínima", 0.10, 0.90, 0.25, 0.05)
        args = ["--conf", str(conf)] + (["--modelo", MODELOS[escolha]] if MODELOS[escolha] else [])
        botao_servico("fase6", args, "▶ Processar imagens das câmeras", "f6_cameras")
        enviado = st.file_uploader("Ou envie uma foto (jpg/png)", type=["jpg", "jpeg", "png"])
        local = st.text_input("Local da câmera", "Portaria principal")
        if enviado and st.button("Detectar na foto enviada", width="stretch"):
            pasta = DATA / "fase6_uploads"
            pasta.mkdir(exist_ok=True)
            destino = pasta / f"{datetime.now():%Y%m%d_%H%M%S}_{enviado.name}"
            destino.write_bytes(enviado.getvalue())
            rodar_servico("fase6", args + ["--imagens", str(destino), "--local", local], "f6_upload")
        mostrar_saida("f6_upload")
    with direita:
        if metricas_arquivo.exists():
            m = json.loads(metricas_arquivo.read_text(encoding="utf-8"))
            st.markdown(f"**Modelo personalizado** · base {m['base']} · {m['epocas']} épocas · "
                        f"treino {m['tempo_treino_s']:.0f} s (CPU)")
            c = st.columns(4)
            for coluna, (nome, valor) in zip(c, m["teste"].items()):
                coluna.metric(f"{nome} (teste)", f"{valor:.3f}")
        deteccoes = ler_csv("deteccoes")
        if not deteccoes.empty:
            st.dataframe(deteccoes[["IMAGEM", "LOCAL_CAMERA", "CLASSE", "CONFIANCA", "MODELO"]],
                         hide_index=True, width="stretch", height=260)

    anotadas = sorted(PASTA_RESULTADOS_VISAO.glob("anotada_*"),
                      key=lambda p: p.stat().st_mtime, reverse=True)
    if anotadas:
        st.subheader("Imagens anotadas")
        cameras = {}
        if (PASTA_IMAGENS_VISAO / "cameras.json").exists():
            cameras = json.loads((PASTA_IMAGENS_VISAO / "cameras.json").read_text(encoding="utf-8"))
        colunas = st.columns(4)
        for i, imagem in enumerate(anotadas[:12]):
            original = imagem.name.removeprefix("anotada_")
            colunas[i % 4].image(str(imagem), caption=cameras.get(original, original),
                                 width="stretch")
    with st.expander("Curvas de treino e matriz de confusão"):
        for nome in ["fase6_curvas_treino.png", "fase6_matriz_confusao.png"]:
            if (DOCS / "evidencias" / nome).exists():
                st.image(str(DOCS / "evidencias" / nome))

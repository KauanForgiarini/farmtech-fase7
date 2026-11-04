"""
Configuração compartilhada: caminhos dos arquivos de dados e variáveis de ambiente.

Todos os serviços leem e gravam na pasta data/ do projeto, que funciona como a
área de troca entre as fases. O banco da Fase 3 consolida esses arquivos.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]          # pasta única do projeto
SRC = RAIZ / "src"
DATA = RAIZ / "data"
DOCS = RAIZ / "docs"

ARQUIVOS = {
    "talhoes": DATA / "fase1_talhoes.csv",
    "insumos": DATA / "fase1_insumos.csv",
    "estatisticas": DATA / "fase1_estatisticas.csv",
    "leituras": DATA / "fase2_leituras_sensores.csv",
    "clima": DATA / "fase2_clima_open_meteo.json",
    "historico_ml": DATA / "fase4_historico_treino.csv",
    "previsoes": DATA / "fase4_previsoes.csv",
    "deteccoes": DATA / "fase6_deteccoes.csv",
    "alertas": DATA / "fase7_alertas.csv",
    "aws_config": DATA / "aws_config.json",
    "banco_sqlite": DATA / "farmtech.db",
}

PASTA_IMAGENS_VISAO = DATA / "fase6_imagens_campo"
PASTA_RESULTADOS_VISAO = DATA / "fase6_resultados"
PASTA_DATASET_VISAO = DATA / "fase6_dataset"
PASTA_MODELOS_ML = SRC / "fase4_modelos_preditivos" / "modelos"
MODELO_YOLO = SRC / "fase6_visao_computacional" / "modelos" / "yolo_farmtech_30ep.pt"

SEMENTE = 574005   # RM do integrante, usada em todas as simulações


def carregar_env(arquivo: Path = RAIZ / ".env") -> None:
    """Carrega um arquivo .env simples (CHAVE=valor) sem dependências externas."""
    if not arquivo.exists():
        return
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


def configurar_saida() -> None:
    """Garante UTF-8 no terminal do Windows (acentos nas mensagens)."""
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


carregar_env()

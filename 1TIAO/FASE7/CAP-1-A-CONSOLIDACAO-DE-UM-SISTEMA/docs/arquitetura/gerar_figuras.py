"""
Gera as figuras autorais de arquitetura do projeto (matplotlib).

Uso (na pasta do projeto):
    python docs/arquitetura/gerar_figuras.py

Saídas:
    docs/arquitetura/arquitetura_farmtech_fase7.png  - sistema integrado (Fases 1 a 7)
    IR-ALEM/docs/arquitetura_rekognition.png         - Ir Além 1
    IR-ALEM/docs/figura_fluxo_ag.png                 - Ir Além 2
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
CORES = {"fase": "#d8f3dc", "borda": "#2d6a4f", "aws": "#fde7c8", "aws_borda": "#c2410c",
         "local": "#e0e7ff", "local_borda": "#3730a3", "pessoas": "#fee2e2", "pessoas_borda": "#b42318"}


def caixa(ax, x, y, w, h, titulo, texto="", cor="fase", borda="borda", tamanho=10):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.15",
                                facecolor=CORES[cor], edgecolor=CORES[borda], linewidth=1.8))
    ax.text(x + w / 2, y + h - 0.28, titulo, ha="center", va="top", fontsize=tamanho,
            fontweight="bold", color="#111827")
    if texto:
        ax.text(x + w / 2, y + h - 0.68, texto, ha="center", va="top", fontsize=tamanho - 2.2,
                color="#1f2937", linespacing=1.35)


def seta(ax, origem, destino, texto="", cor="#374151", curva=0.0):
    ax.add_patch(FancyArrowPatch(origem, destino, arrowstyle="-|>", mutation_scale=16, lw=1.6,
                                 color=cor, connectionstyle=f"arc3,rad={curva}"))
    if texto:
        meio = ((origem[0] + destino[0]) / 2, (origem[1] + destino[1]) / 2)
        ax.text(meio[0], meio[1] + 0.12, texto, ha="center", va="bottom", fontsize=7.5,
                color=cor, bbox=dict(facecolor="white", edgecolor="none", pad=1))


def novo(largura, altura, titulo):
    fig, ax = plt.subplots(figsize=(largura, altura))
    ax.set_xlim(0, largura * 1.2)
    ax.set_ylim(0, altura * 1.2)
    ax.axis("off")
    ax.set_title(titulo, fontsize=14, fontweight="bold", color="#1b4332", pad=12)
    return fig, ax


def arquitetura_sistema() -> None:
    fig, ax = novo(15, 8.2, "FarmTech Solutions — arquitetura do sistema integrado (Fase 7)")
    # camada de campo/serviços locais
    caixa(ax, 0.3, 6.6, 3.2, 2.5, "Fase 1 · Plantio", "Python: área (retângulo/círculo)\n"
          "ruas e insumos · R: estatística\ndata/fase1_*.csv")
    caixa(ax, 0.3, 3.6, 3.2, 2.6, "Fase 2 · ESP32", "NPK (botões) · pH (LDR)\nDHT22 · relé da bomba\n"
          "simulador ou Serial/Wokwi\n+ Open-Meteo (chuva)")
    caixa(ax, 0.3, 0.6, 3.2, 2.6, "Fase 6 · Visão", "YOLOv8n personalizado\n(pessoa, carro)\n"
          "câmeras: portaria,\ntalhões, depósito")
    caixa(ax, 4.6, 3.6, 3.4, 2.6, "Fase 3 · Banco", "Oracle FIAP ou SQLite\n7 tabelas normalizadas\n"
          "ETL de todas as fases\nconsultas analíticas", cor="local", borda="local_borda")
    caixa(ax, 4.6, 6.6, 3.4, 2.5, "Fase 4 · ML", "4 regressores · CV 5-fold\nvolume de irrigação,\n"
          "adubação e rendimento")
    caixa(ax, 4.6, 0.6, 3.4, 2.6, "Dashboard final", "Streamlit (evolução da Fase 4)\n"
          "botão por serviço =\npython farmtech.py <serviço>", cor="local", borda="local_borda")
    # nuvem
    ax.add_patch(FancyBboxPatch((9.0, 0.4), 6.0, 8.9, boxstyle="round,pad=0.02,rounding_size=0.3",
                                facecolor="#fff7ed", edgecolor=CORES["aws_borda"], lw=1.4,
                                linestyle="--"))
    ax.text(12.0, 9.05, "AWS · infraestrutura da Fase 5 (us-east-1)", ha="center",
            fontsize=9.5, color=CORES["aws_borda"], fontweight="bold")
    caixa(ax, 9.4, 6.0, 2.5, 2.3, "Amazon S3", "sensores/*.json\nvisao/*.json\nprivado · SSE",
          cor="aws", borda="aws_borda")
    caixa(ax, 12.3, 6.0, 2.4, 2.3, "AWS Lambda", "farmtech-alertas\nregras +\nações corretivas",
          cor="aws", borda="aws_borda")
    caixa(ax, 12.3, 2.9, 2.4, 2.3, "Amazon SNS", "tópico\nfarmtech-alertas\nfiltro severidade",
          cor="aws", borda="aws_borda")
    caixa(ax, 9.4, 2.9, 2.5, 2.3, "CloudWatch", "logs de cada\nexecução", cor="aws", borda="aws_borda")
    caixa(ax, 10.6, 0.7, 3.4, 1.7, "Funcionários", "e-mail (relatório) · SMS (crítico)",
          cor="pessoas", borda="pessoas_borda")

    seta(ax, (3.5, 7.8), (4.6, 7.8), "talhões")
    seta(ax, (3.5, 7.2), (4.6, 5.6), "CSV")
    seta(ax, (3.5, 4.9), (4.6, 4.9), "leituras")
    seta(ax, (3.5, 1.9), (4.6, 4.0), "detecções")
    seta(ax, (6.3, 6.6), (6.3, 6.2), "")
    seta(ax, (6.0, 6.2), (6.0, 6.6), "")
    seta(ax, (6.3, 3.6), (6.3, 3.2), "dados")
    seta(ax, (8.0, 2.0), (9.4, 6.4), "publicar_alerta.py", cor=CORES["aws_borda"])
    seta(ax, (11.9, 7.15), (12.3, 7.15), "gatilho", cor=CORES["aws_borda"])
    seta(ax, (13.5, 6.0), (13.5, 5.2), "publish", cor=CORES["aws_borda"])
    seta(ax, (12.3, 6.3), (11.9, 4.6), "", cor=CORES["aws_borda"])
    seta(ax, (13.5, 2.9), (12.9, 2.4), "", cor=CORES["pessoas_borda"])
    fig.savefig(RAIZ / "docs" / "arquitetura" / "arquitetura_farmtech_fase7.png", dpi=140,
                bbox_inches="tight")
    plt.close(fig)


def arquitetura_rekognition() -> None:
    fig, ax = novo(13, 5.2, "Ir Além 1 — reconhecimento de imagens na AWS com Amazon Rekognition")
    caixa(ax, 0.2, 2.2, 2.5, 2.4, "Câmera / dashboard", "foto do acesso\nou do talhão\n+ metadado 'local'",
          cor="local", borda="local_borda")
    caixa(ax, 3.4, 2.2, 2.5, 2.4, "Amazon S3", "imagens/*.jpg\nbucket privado\n(Fase 7)",
          cor="aws", borda="aws_borda")
    caixa(ax, 6.6, 2.2, 2.6, 2.4, "AWS Lambda", "farmtech-rekognition\nmapeia Person→pessoa\nCar/Truck→carro",
          cor="aws", borda="aws_borda")
    caixa(ax, 6.6, 4.9, 2.6, 1.3, "Amazon Rekognition", "DetectLabels (≥ 70%)", cor="aws",
          borda="aws_borda", tamanho=9)
    caixa(ax, 9.9, 2.2, 2.4, 2.4, "Amazon SNS", "mesmas regras e\nações corretivas\nda Fase 7",
          cor="aws", borda="aws_borda")
    caixa(ax, 9.9, 0.2, 2.4, 1.5, "Funcionários", "e-mail / SMS", cor="pessoas", borda="pessoas_borda")
    caixa(ax, 3.4, 0.2, 5.8, 1.5, "Comparação local", "deploy_rekognition.py --comparar:\n"
          "Rekognition x YOLO da Fase 6 nas mesmas 8 imagens")
    seta(ax, (2.7, 3.4), (3.4, 3.4), "upload")
    seta(ax, (5.9, 3.4), (6.6, 3.4), "evento", cor=CORES["aws_borda"])
    seta(ax, (7.9, 4.6), (7.9, 4.9), "", cor=CORES["aws_borda"])
    seta(ax, (8.3, 4.9), (8.3, 4.6), "", cor=CORES["aws_borda"])
    seta(ax, (9.2, 3.4), (9.9, 3.4), "publish", cor=CORES["aws_borda"])
    seta(ax, (11.1, 2.2), (11.1, 1.7), "", cor=CORES["pessoas_borda"])
    fig.savefig(RAIZ / "IR-ALEM" / "docs" / "arquitetura_rekognition.png", dpi=140,
                bbox_inches="tight")
    plt.close(fig)


def fluxo_algoritmo_genetico() -> None:
    fig, ax = novo(13, 5.6, "Ir Além 2 — fluxo do algoritmo genético (mochila com água e orçamento)")
    etapas = [
        ("Entrada salva", "ag_entrada_\nintervencoes.csv\n+ restrições.json"),
        ("População", "60 cromossomos\nbinários (36 genes)"),
        ("Aptidão", "receita − penalidade\npor excesso de\nágua/orçamento"),
        ("selection()", "roleta (base)\nou torneio k=3"),
        ("crossover()", "1 ponto (base)\nou uniforme"),
        ("mutation()", "bit-flip (base)\nou bit-flip + reparo"),
    ]
    for i, (titulo, texto) in enumerate(etapas):
        caixa(ax, 0.2 + i * 2.6, 3.6, 2.2, 2.4, titulo, texto,
              cor="local" if i in (3, 4, 5) else "fase",
              borda="local_borda" if i in (3, 4, 5) else "borda")
        if i:
            seta(ax, (0.2 + i * 2.6 - 0.4, 4.8), (0.2 + i * 2.6, 4.8))
    caixa(ax, 10.6, 0.4, 4.6, 2.3, "Saída", "melhor plano viável · gap para o ótimo\n"
          "exato (programação dinâmica) · tempo", cor="aws", borda="aws_borda")
    caixa(ax, 4.0, 0.4, 5.2, 2.3, "Elitismo + nova geração", "2 melhores preservados ·\n"
          "150 gerações · 20 sementes por configuração")
    seta(ax, (14.0, 3.6), (9.2, 1.6), "nova geração", curva=-0.15)
    seta(ax, (4.0, 1.6), (3.5, 3.6), "repete", curva=-0.3)
    seta(ax, (9.2, 1.1), (10.6, 1.1), "fim")
    fig.savefig(RAIZ / "IR-ALEM" / "docs" / "figura_fluxo_ag.png", dpi=140, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    arquitetura_sistema()
    arquitetura_rekognition()
    fluxo_algoritmo_genetico()
    print("Figuras geradas.")

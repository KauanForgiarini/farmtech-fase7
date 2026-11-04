"""
FarmTech Solutions - Fase 6: treinamento do YOLO personalizado.

Reproduz localmente (CPU ou GPU) a configuração vencedora da Fase 6:
YOLOv8n pré-treinado no COCO, ajustado por 30 épocas no dataset FarmTech
(80 imagens do Open Images V7: pessoa e carro, divisão 64/8/8).

Uso:
    python src/fase6_visao_computacional/treinar_yolo.py [--epocas 30] [--dados data/fase6_dataset]

Saídas:
    src/fase6_visao_computacional/modelos/yolo_farmtech_30ep.pt  (pesos usados pela dashboard)
    src/fase6_visao_computacional/modelos/metricas_yolo.json     (métricas no conjunto de teste)
    docs/evidencias/fase6_*.png                                  (curvas e matriz de confusão)
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from farmtech_core.config import DOCS, MODELO_YOLO, PASTA_DATASET_VISAO, configurar_saida

PASTA = Path(__file__).resolve().parent
CLASSES = ["pessoa", "carro"]          # mesma ordem dos rótulos YOLO da Fase 6
SEMENTE = 42                           # semente usada no notebook da Fase 6


def escrever_yaml(dados: Path, destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    nomes = "\n".join(f"  {i}: {nome}" for i, nome in enumerate(CLASSES))
    destino.write_text(
        f"path: {dados.resolve().as_posix()}\n"
        "train: images/train\nval: images/val\ntest: images/test\n"
        f"names:\n{nomes}\n", encoding="utf-8")
    return destino


def main() -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(description="Treina o YOLO FarmTech (Fase 6)")
    parser.add_argument("--dados", type=Path, default=PASTA_DATASET_VISAO)
    parser.add_argument("--epocas", type=int, default=30)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    args = parser.parse_args()

    from ultralytics import YOLO  # import tardio: biblioteca pesada

    yaml_dados = escrever_yaml(args.dados, PASTA / "runs" / "farmtech_dataset.yaml")
    modelo = YOLO(str(PASTA / "modelos" / "yolov8n.pt"))
    inicio = time.perf_counter()
    modelo.train(data=str(yaml_dados), epochs=args.epocas, imgsz=args.imgsz,
                 batch=args.batch, seed=SEMENTE, deterministic=True, workers=0,
                 optimizer="SGD", lr0=0.01, lrf=0.01, cos_lr=False, patience=0,
                 close_mosaic=0, project=str(PASTA / "runs"), name=f"yolo_{args.epocas}",
                 exist_ok=True, plots=True, verbose=False)
    duracao = time.perf_counter() - inicio

    pasta_treino = Path(modelo.trainer.save_dir)
    melhor = YOLO(str(pasta_treino / "weights" / "best.pt"))
    teste = melhor.val(data=str(yaml_dados), split="test", workers=0, plots=False,
                       project=str(PASTA / "runs"), name="teste", exist_ok=True,
                       verbose=False)

    MODELO_YOLO.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pasta_treino / "weights" / "best.pt", MODELO_YOLO)
    metricas = {
        "modelo": MODELO_YOLO.name, "base": "yolov8n.pt (COCO)", "epocas": args.epocas,
        "imgsz": args.imgsz, "tempo_treino_s": round(duracao, 1),
        "teste": {"precision": round(float(teste.box.mp), 4),
                  "recall": round(float(teste.box.mr), 4),
                  "mAP50": round(float(teste.box.map50), 4),
                  "mAP50_95": round(float(teste.box.map), 4)},
        "classes": CLASSES,
    }
    (MODELO_YOLO.parent / "metricas_yolo.json").write_text(
        json.dumps(metricas, indent=2, ensure_ascii=False), encoding="utf-8")

    evidencias = DOCS / "evidencias"
    evidencias.mkdir(parents=True, exist_ok=True)
    for origem, destino in [("results.png", "fase6_curvas_treino.png"),
                            ("confusion_matrix.png", "fase6_matriz_confusao.png")]:
        if (pasta_treino / origem).exists():
            shutil.copy2(pasta_treino / origem, evidencias / destino)

    print(json.dumps(metricas, indent=2, ensure_ascii=False))
    print(f"Pesos salvos em {MODELO_YOLO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

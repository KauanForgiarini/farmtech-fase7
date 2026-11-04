"""
FarmTech Solutions - Fase 6: serviço de visão computacional (YOLO).

Processa as imagens das câmeras da fazenda com o YOLO personalizado da Fase 6
(pessoa e carro), salva as imagens anotadas e registra as detecções em
data/fase6_deteccoes.csv, que é carregado no banco (Fase 3) e monitorado pelo
serviço de alertas na AWS (Fase 7).

Sem os pesos personalizados, usa o YOLOv8n pré-treinado no COCO (baseline da
Fase 6), mapeando person -> pessoa e car/truck/bus -> carro.

Uso:
    python src/fase6_visao_computacional/detectar.py                    # pasta padrão
    python src/fase6_visao_computacional/detectar.py --imagens foto.jpg --local "Portaria"
    python src/fase6_visao_computacional/detectar.py --modelo yolov8n.pt
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from farmtech_core.config import (ARQUIVOS, MODELO_YOLO, PASTA_IMAGENS_VISAO,
                                  PASTA_RESULTADOS_VISAO, configurar_saida)

PASTA = Path(__file__).resolve().parent
EXTENSOES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
MAPA_COCO = {"person": "pessoa", "car": "carro", "truck": "carro", "bus": "carro",
             "motorcycle": "carro"}
COLUNAS = ["ID_DETECCAO", "DATA_HORA", "LOCAL_CAMERA", "IMAGEM", "CLASSE", "CONFIANCA",
           "X1", "Y1", "X2", "Y2", "MODELO"]


def listar_imagens(origem: Path) -> list[Path]:
    if origem.is_file():
        return [origem]
    return sorted(p for p in origem.glob("*") if p.suffix.lower() in EXTENSOES)


def carregar_cameras(pasta: Path) -> dict[str, str]:
    """cameras.json associa cada arquivo ao local da câmera (portaria, talhão...)."""
    arquivo = pasta / "cameras.json"
    if arquivo.exists():
        return json.loads(arquivo.read_text(encoding="utf-8"))
    return {}


def escolher_modelo(caminho: str | None):
    from ultralytics import YOLO  # import tardio: biblioteca pesada

    if caminho:
        return YOLO(caminho), Path(caminho).name
    if MODELO_YOLO.exists():
        return YOLO(str(MODELO_YOLO)), MODELO_YOLO.name
    print("[AVISO] Pesos personalizados não encontrados; usando YOLOv8n (COCO).")
    return YOLO(str(PASTA / "modelos" / "yolov8n.pt")), "yolov8n.pt"


def detectar(imagens: list[Path], modelo, nome_modelo: str, conf: float,
             cameras: dict[str, str], local_padrao: str) -> list[dict]:
    PASTA_RESULTADOS_VISAO.mkdir(parents=True, exist_ok=True)
    deteccoes = []
    for imagem in imagens:
        inicio = time.perf_counter()
        resultado = modelo.predict(str(imagem), conf=conf, verbose=False)[0]
        ms = (time.perf_counter() - inicio) * 1000
        resultado.save(filename=str(PASTA_RESULTADOS_VISAO / f"anotada_{imagem.name}"))
        local = cameras.get(imagem.name, local_padrao)
        quando = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        encontrados = []
        for caixa in resultado.boxes:
            rotulo = resultado.names[int(caixa.cls)]
            classe = rotulo if rotulo in {"pessoa", "carro"} else MAPA_COCO.get(rotulo)
            if classe is None:
                continue
            x1, y1, x2, y2 = (round(float(v), 1) for v in caixa.xyxy[0])
            deteccoes.append({
                "ID_DETECCAO": len(deteccoes) + 1, "DATA_HORA": quando, "LOCAL_CAMERA": local,
                "IMAGEM": imagem.name, "CLASSE": classe,
                "CONFIANCA": round(float(caixa.conf), 4),
                "X1": x1, "Y1": y1, "X2": x2, "Y2": y2, "MODELO": nome_modelo,
            })
            encontrados.append(f"{classe} {float(caixa.conf):.0%}")
        print(f"  {imagem.name:<18} {local:<34} {ms:6.0f} ms  "
              f"{', '.join(encontrados) or 'nenhuma detecção'}")
    return deteccoes


def main() -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(description="Visão computacional FarmTech (Fase 6)")
    parser.add_argument("--imagens", type=Path, default=PASTA_IMAGENS_VISAO,
                        help="imagem ou pasta de imagens")
    parser.add_argument("--modelo", help="pesos YOLO (padrão: modelo personalizado)")
    parser.add_argument("--conf", type=float, default=0.25, help="confiança mínima")
    parser.add_argument("--local", default="Câmera da fazenda",
                        help="local da câmera quando não houver cameras.json")
    args = parser.parse_args()

    imagens = listar_imagens(args.imagens)
    if not imagens:
        print(f"Nenhuma imagem encontrada em {args.imagens}")
        return 1
    modelo, nome_modelo = escolher_modelo(args.modelo)
    pasta_cameras = args.imagens if args.imagens.is_dir() else args.imagens.parent
    print(f"Modelo: {nome_modelo} | {len(imagens)} imagem(ns) | confiança >= {args.conf}")
    deteccoes = detectar(imagens, modelo, nome_modelo, args.conf,
                         carregar_cameras(pasta_cameras), args.local)

    with open(ARQUIVOS["deteccoes"], "w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS)
        escritor.writeheader()
        escritor.writerows(deteccoes)
    por_classe: dict[str, int] = {}
    for d in deteccoes:
        por_classe[d["CLASSE"]] = por_classe.get(d["CLASSE"], 0) + 1
    print(f"\n{len(deteccoes)} detecções: "
          + (", ".join(f"{c}={n}" for c, n in por_classe.items()) or "nenhuma"))
    print(f"Imagens anotadas em data/{PASTA_RESULTADOS_VISAO.name}/ | "
          f"registros em data/{ARQUIVOS['deteccoes'].name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

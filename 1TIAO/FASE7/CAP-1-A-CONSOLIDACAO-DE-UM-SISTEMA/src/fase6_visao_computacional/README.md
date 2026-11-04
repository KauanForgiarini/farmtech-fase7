# Fase 6 — Visão computacional (YOLO)

| Arquivo | Função |
|---|---|
| `treinar_yolo.py` | Reproduz o treino vencedor da Fase 6 (YOLOv8n, 30 épocas, SGD, semente 42) no dataset `data/fase6_dataset` |
| `detectar.py` | Detecta pessoa/carro nas câmeras (`data/fase6_imagens_campo` + `cameras.json`), salva imagens anotadas e `data/fase6_deteccoes.csv` |
| `modelos/yolo_farmtech_30ep.pt` | Pesos personalizados usados pela dashboard e pelos alertas |
| `modelos/metricas_yolo.json` | Precision, recall, mAP50 e mAP50-95 no teste |

O notebook original (Colab/GPU) está em `notebooks/fase6_yolo_original_colab.ipynb`.
```bash
python farmtech.py fase6
python farmtech.py fase6 --modelo src/fase6_visao_computacional/modelos/yolov8n.pt   # baseline COCO
```

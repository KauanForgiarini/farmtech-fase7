# data/ — área de troca entre as fases

| Arquivo / pasta | Produzido por | Consumido por |
|---|---|---|
| `fase1_talhoes.csv`, `fase1_insumos.csv` | Fase 1 (`farmtech_fase1.py`) | R, ETL (Fase 3), Ir Além 2 |
| `fase1_estatisticas.csv` | `analise_estatistica.R` / `.py` | dashboard |
| `fase2_leituras_sensores.csv` | Fase 2 (`simulador_esp32.py`) | R, Fase 4, ETL, alertas |
| `fase2_clima_open_meteo.json` | `clima_open_meteo.py` | dashboard |
| `fase4_historico_treino.csv`, `fase4_previsoes.csv` | Fase 4 | ETL, alertas (volume previsto) |
| `fase6_dataset/` | Fase 6 (Open Images V7, 64/8/8) | `treinar_yolo.py` |
| `fase6_imagens_campo/` (+ `cameras.json`) | câmeras da fazenda | `detectar.py` |
| `fase6_resultados/`, `fase6_deteccoes.csv` | Fase 6 (`detectar.py`) | ETL, alertas, dashboard |
| `fase7_alertas.csv` | Fase 7 (`publicar_alerta.py`) | ETL (tabela ALERTA), dashboard |
| `farmtech.db` (não versionado) | ETL da Fase 3 (SQLite) | dashboard e alertas |
| `aws_config.json` (não versionado) | `deploy_aws.py` | alertas e Ir Além 1 |

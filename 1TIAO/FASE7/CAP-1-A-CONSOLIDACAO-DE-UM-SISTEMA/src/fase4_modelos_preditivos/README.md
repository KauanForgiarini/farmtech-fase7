# Fase 4 — Modelos preditivos (Scikit-Learn)

| Arquivo | Função |
|---|---|
| `gerar_historico.py` | 200 leituras históricas com os alvos agronômicos (semente 574005) |
| `treinar_modelos.py` | Linear, Ridge, Random Forest e Gradient Boosting com CV 5-fold; salva o melhor por alvo em `modelos/` e prevê as leituras atuais (`data/fase4_previsoes.csv`) |
| `modelos/metadata.json` | Métricas MAE, RMSE, R² e CV-R² de todos os modelos |
| `farmtech_suggestions.cpp` | Motor de sugestões de manejo em C++ da Fase 4 (mantido como histórico) |

A dashboard da Fase 4 evoluiu para a dashboard final em `src/dashboard/`.
```bash
python farmtech.py fase4
```

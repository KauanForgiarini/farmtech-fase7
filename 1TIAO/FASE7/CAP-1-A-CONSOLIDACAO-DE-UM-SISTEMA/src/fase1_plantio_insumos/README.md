# Fase 1 — Plantio, insumos e estatística (Python + R)

| Arquivo | Função |
|---|---|
| `farmtech_fase1.py` | CRUD de talhões em vetores (menu: entrada, saída, atualização, deleção, sair); área por figura (soja = retângulo, milho = círculo), ruas, metros lineares e insumos; exporta `data/fase1_talhoes.csv` e `data/fase1_insumos.csv` |
| `analise_estatistica.R` | R base: média, desvio padrão, mediana, mínimo, máximo e CV dos talhões e sensores; gráfico em `docs/evidencias/`; clima Open-Meteo (se `jsonlite`) |
| `analise_estatistica.py` | Executa o R se houver `Rscript`; senão aplica as mesmas fórmulas em Python |

```bash
python farmtech.py fase1 --menu
python farmtech.py fase1 --adicionar soja "Talhão 5" 300 200
Rscript src/fase1_plantio_insumos/analise_estatistica.R
```

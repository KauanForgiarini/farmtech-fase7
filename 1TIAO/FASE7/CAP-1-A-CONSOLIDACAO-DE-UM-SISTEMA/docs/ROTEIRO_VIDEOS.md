# Roteiros dos vídeos (YouTube, "não listado")

Antes de gravar: Learner Lab iniciado, credenciais em `~/.aws/credentials`, `aws-deploy` feito e
assinatura de e-mail confirmada; `python farmtech.py pipeline` rodado; dashboard aberta
(`python farmtech.py dashboard`); console da AWS aberto em outra aba; caixa de e-mail aberta.

## Vídeo principal — até 10 minutos

| Tempo | Tela | Fala / ação |
|---|---|---|
| 0:00–0:40 | README no GitHub | "Sou Kauan Maciel Forgiarini, RM 574005, Grupo 27. Na Fase 7 a FarmTech integra as Fases 1 a 6 em um único sistema e cria um serviço de alertas na AWS." Mostrar a figura de arquitetura. |
| 0:40–1:30 | VS Code com a pasta única | Mostrar `src/` com uma subpasta por fase, `farmtech.py --listar` no terminal e o `tasks.json` (Run Task). Explicar: botão da dashboard = mesmo comando de terminal. |
| 1:30–2:30 | Dashboard → Fase 1 | Cadastrar um talhão de soja pelo formulário; mostrar área, ruas e insumos. Clicar em "Executar análise estatística" (R/Python) e mostrar média e desvio padrão. |
| 2:30–3:40 | Dashboard → Fase 2 | Mostrar o firmware e o circuito Wokwi (pode abrir o wokwi.com rapidamente). Escolher o cenário "Seca", marcar Open-Meteo, coletar leituras; explicar a regra da bomba nos gráficos. |
| 3:40–4:20 | Dashboard → Fase 3 | Mostrar as 7 tabelas, o modelo relacional e 2 consultas (motivos de decisão, previsões por decisão). Citar que o mesmo ETL roda no Oracle da FIAP. |
| 4:20–5:00 | Dashboard → Fase 4 | Tabela de métricas (CV-R²), mover os sliders e mostrar previsão + recomendação. |
| 5:00–5:40 | Dashboard → Fase 5 | Arquitetura serverless, controles de segurança e custos (Fase 5 x Fase 7). |
| 5:40–6:30 | Dashboard → Fase 6 | Processar as imagens das câmeras; mostrar caixas e a comparação personalizado x baseline (análise crítica do recall de pessoa). |
| 6:30–8:40 | Dashboard → Fase 7 + console AWS + e-mail | Mostrar os cartões de alerta com ações corretivas. Escolher "S3 → gatilho → Lambda → SNS" e disparar. No console: objeto novo no S3, gatilho na Lambda, log no CloudWatch, tópico SNS. Abrir o e-mail recebido e ler uma ação corretiva. (Opcional: SMS.) |
| 8:40–9:30 | Terminal | `python farmtech.py pipeline` (trecho) e `python -m pytest tests` (16 testes passando). |
| 9:30–10:00 | README | Recapitular: 6 fases integradas, dashboard, alertas na AWS; citar os Ir Além. |

## Ir Além 1 (Rekognition) — até 4 minutos

| Tempo | Conteúdo |
|---|---|
| 0:00–0:30 | Objetivo e figura `IR-ALEM/docs/arquitetura_rekognition.png` |
| 0:30–1:15 | Console Rekognition → *Label detection* com uma foto da fazenda (rótulos e confiança) |
| 1:15–2:15 | `deploy_rekognition.py` (código comentado) e a Lambda criada com gatilho `imagens/`; variáveis de ambiente |
| 2:15–3:15 | `--enviar pessoa_038.jpg` → log no CloudWatch → e-mail do alerta; `--comparar` com o YOLO |
| 3:15–4:00 | Telas do Custom Labels até antes de confirmar o treino e a justificativa crítica (custo, latência, LGPD, solução híbrida) |

## Ir Além 2 (algoritmo genético) — até 4 minutos

| Tempo | Conteúdo |
|---|---|
| 0:00–0:40 | Problema: 36 intervenções, água e orçamento limitados (mochila com 2 restrições); figura do fluxo |
| 0:40–1:20 | Entrada salva em arquivo (`ag_entrada_intervencoes.csv`) e ótimo exato por programação dinâmica |
| 1:20–2:30 | Código do AG no notebook: fitness com penalidade, `selection()` roleta/torneio, `crossover()` 1 ponto/uniforme, `mutation()` bit-flip/reparo |
| 2:30–3:30 | Tabela de resultados e gráficos (convergência, gap, tempo) |
| 3:30–4:00 | Conclusão: combinada acerta 20/20; plano de manejo sugerido |

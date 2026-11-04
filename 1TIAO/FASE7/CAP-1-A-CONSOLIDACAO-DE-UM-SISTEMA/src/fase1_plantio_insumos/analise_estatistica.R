# ============================================================
#  FarmTech Solutions - Fase 1: análise estatística em R
#  Kauan Maciel Forgiarini | RM 574005 | FIAP IA
# ============================================================
#  Entradas (geradas pelos serviços em Python):
#    data/fase1_talhoes.csv           - talhões e áreas (Fase 1)
#    data/fase1_insumos.csv           - manejo de insumos (Fase 1)
#    data/fase2_leituras_sensores.csv - leituras do ESP32 (Fase 2)
#  Saídas:
#    data/fase1_estatisticas.csv      - média, desvio padrão, mediana, mín., máx.
#    docs/evidencias/r_*.png          - gráficos
#
#  Usa apenas o R base (sem pacotes extras). A consulta ao clima usa o
#  pacote jsonlite somente se estiver instalado (Ir Além da Fase 1).
#
#  Execução (na pasta do projeto):  Rscript src/fase1_plantio_insumos/analise_estatistica.R
# ============================================================

args <- commandArgs(trailingOnly = TRUE)
raiz <- if (length(args) >= 1) args[1] else "."
caminho <- function(...) file.path(raiz, ...)

cat("============================================================\n")
cat(" FarmTech Solutions - Estatística descritiva (R)\n")
cat("============================================================\n")

resumir <- function(valores, grupo, variavel) {
  valores <- as.numeric(valores)
  valores <- valores[!is.na(valores)]
  data.frame(
    grupo = grupo,
    variavel = variavel,
    n = length(valores),
    media = round(mean(valores), 4),
    desvio_padrao = round(if (length(valores) > 1) sd(valores) else 0, 4),
    mediana = round(median(valores), 4),
    minimo = round(min(valores), 4),
    maximo = round(max(valores), 4),
    coef_variacao_pct = round(if (mean(valores) != 0 && length(valores) > 1)
      100 * sd(valores) / mean(valores) else 0, 2),
    stringsAsFactors = FALSE
  )
}

resultados <- list()

# ---------------- 1. Talhões (Fase 1) ----------------
arq_talhoes <- caminho("data", "fase1_talhoes.csv")
if (file.exists(arq_talhoes)) {
  talhoes <- read.csv(arq_talhoes, encoding = "UTF-8", stringsAsFactors = FALSE)
  for (cultura in unique(talhoes$CULTURA)) {
    sub <- talhoes[talhoes$CULTURA == cultura, ]
    resultados[[length(resultados) + 1]] <- resumir(sub$AREA_HA, paste0("talhoes_", cultura), "area_ha")
    resultados[[length(resultados) + 1]] <- resumir(sub$NUM_RUAS, paste0("talhoes_", cultura), "num_ruas")
  }
  cat("\nÁrea plantada por cultura (ha):\n")
  print(aggregate(AREA_HA ~ CULTURA, data = talhoes, FUN = sum))
}

# ---------------- 2. Insumos (Fase 1) ----------------
arq_insumos <- caminho("data", "fase1_insumos.csv")
if (file.exists(arq_insumos)) {
  insumos <- read.csv(arq_insumos, encoding = "UTF-8", stringsAsFactors = FALSE)
  cat("\nTotal de cada insumo para todos os talhões:\n")
  print(aggregate(QUANTIDADE_TOTAL ~ INSUMO + UNIDADE_TOTAL, data = insumos, FUN = sum))
}

# ---------------- 3. Sensores (Fase 2) ----------------
arq_leituras <- caminho("data", "fase2_leituras_sensores.csv")
if (file.exists(arq_leituras)) {
  leituras <- read.csv(arq_leituras, encoding = "UTF-8", stringsAsFactors = FALSE)
  for (variavel in c("UMIDADE_SOLO_PCT", "PH_SOLO", "TEMPERATURA_C", "CHUVA_PREVISTA_MM")) {
    resultados[[length(resultados) + 1]] <- resumir(leituras[[variavel]], "sensores", tolower(variavel))
  }
  cat("\nFrequência das decisões da bomba:\n")
  print(table(leituras$MOTIVO_DECISAO))
  cat(sprintf("\nBomba ligada em %.1f%% das leituras.\n", 100 * mean(leituras$BOMBA_LIGADA)))
  cat(sprintf("Correlação umidade x temperatura: %.3f\n",
              cor(leituras$UMIDADE_SOLO_PCT, leituras$TEMPERATURA_C)))

  dir.create(caminho("docs", "evidencias"), showWarnings = FALSE, recursive = TRUE)
  png(caminho("docs", "evidencias", "r_umidade_por_decisao.png"), width = 900, height = 520)
  par(mar = c(9, 5, 4, 2))
  boxplot(UMIDADE_SOLO_PCT ~ MOTIVO_DECISAO, data = leituras, las = 2,
          col = "#7fb77e", ylab = "Umidade do solo (%)", xlab = "",
          main = "FarmTech - Umidade do solo por decisão do ESP32 (R)")
  abline(h = c(40, 60, 80), lty = 2, col = c("#b23b3b", "#c98a1b", "#3b6fb2"))
  dev.off()
}

tabela <- do.call(rbind, resultados)
if (!is.null(tabela)) {
  tabela$ferramenta <- "R"
  write.csv(tabela, caminho("data", "fase1_estatisticas.csv"), row.names = FALSE,
            fileEncoding = "UTF-8")
  cat("\nEstatísticas descritivas:\n")
  print(tabela[, c("grupo", "variavel", "n", "media", "desvio_padrao", "mediana")],
        row.names = FALSE)
}

# ---------------- 4. Ir Além: clima atual (Open-Meteo) ----------------
if (requireNamespace("jsonlite", quietly = TRUE)) {
  url <- paste0("https://api.open-meteo.com/v1/forecast?latitude=-29.6842",
                "&longitude=-53.8069&current=temperature_2m,relative_humidity_2m,precipitation")
  clima <- tryCatch(jsonlite::fromJSON(url), error = function(e) NULL)
  if (!is.null(clima)) {
    cat(sprintf("\nClima agora em Santa Maria-RS: %.1f °C, umidade do ar %d%%, chuva %.1f mm\n",
                clima$current$temperature_2m, clima$current$relative_humidity_2m,
                clima$current$precipitation))
  }
}
cat("\nAnálise em R concluída.\n")

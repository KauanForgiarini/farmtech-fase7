-- ============================================================
-- FarmTech Solutions - Consultas analíticas do sistema integrado
-- SQL padrão: roda igual no Oracle (SQL Developer) e no SQLite.
-- Cada bloco começa com "-- nome:" para ser lido pela dashboard.
-- ============================================================

-- nome: talhoes_cadastrados
-- Fase 1: talhões, cultura e área de plantio
SELECT T.ID_TALHAO, T.NOME, C.NOME AS CULTURA, T.FORMA, T.AREA_HA,
       T.NUM_RUAS, T.METROS_LINEARES
FROM TALHAO T
JOIN CULTURA C ON C.ID_CULTURA = T.ID_CULTURA
ORDER BY T.ID_TALHAO;

-- nome: insumos_por_talhao
-- Fase 1: quantidade total de cada insumo por talhão
SELECT T.NOME AS TALHAO, I.INSUMO, I.DOSE, I.UNIDADE,
       ROUND(I.QUANTIDADE_TOTAL, 2) AS QUANTIDADE_TOTAL, I.UNIDADE_TOTAL
FROM APLICACAO_INSUMO I
JOIN TALHAO T ON T.ID_TALHAO = I.ID_TALHAO
ORDER BY T.NOME, I.INSUMO;

-- nome: medias_diarias_sensores
-- Fase 2: médias diárias das leituras do ESP32 e horas de bomba ligada
SELECT SUBSTR(DATA_HORA, 1, 10) AS DIA,
       COUNT(*) AS LEITURAS,
       ROUND(AVG(UMIDADE_SOLO_PCT), 1) AS UMIDADE_MEDIA,
       ROUND(AVG(PH_SOLO), 2) AS PH_MEDIO,
       ROUND(AVG(TEMPERATURA_C), 1) AS TEMPERATURA_MEDIA,
       SUM(BOMBA_LIGADA) AS LEITURAS_IRRIGANDO
FROM LEITURA_SENSOR
GROUP BY SUBSTR(DATA_HORA, 1, 10)
ORDER BY DIA;

-- nome: motivos_decisao
-- Fase 2/3: distribuição das decisões do firmware
SELECT MOTIVO_DECISAO, COUNT(*) AS OCORRENCIAS,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM LEITURA_SENSOR), 1) AS PERCENTUAL
FROM LEITURA_SENSOR
GROUP BY MOTIVO_DECISAO
ORDER BY OCORRENCIAS DESC;

-- nome: leituras_fora_da_faixa
-- Fase 3: leituras que exigem ação corretiva (insumo dos alertas)
SELECT SUM(CASE WHEN PH_SOLO < 5.5 THEN 1 ELSE 0 END) AS PH_ACIDO,
       SUM(CASE WHEN PH_SOLO > 7.0 THEN 1 ELSE 0 END) AS PH_ALCALINO,
       SUM(CASE WHEN UMIDADE_SOLO_PCT < 40 THEN 1 ELSE 0 END) AS UMIDADE_CRITICA,
       SUM(CASE WHEN UMIDADE_SOLO_PCT >= 80 THEN 1 ELSE 0 END) AS SOLO_SATURADO,
       SUM(CASE WHEN P_PRESENTE = 0 AND K_PRESENTE = 0 THEN 1 ELSE 0 END) AS SEM_P_E_K
FROM LEITURA_SENSOR;

-- nome: previsoes_por_decisao
-- Fase 4: previsões médias do modelo agrupadas pela decisão da bomba
SELECT L.MOTIVO_DECISAO,
       COUNT(*) AS LEITURAS,
       ROUND(AVG(P.VOLUME_IRRIGACAO_L), 2) AS VOLUME_PREVISTO_L_M2,
       ROUND(AVG(P.NECESSIDADE_FERT_KGHA), 1) AS FERTILIZACAO_KGHA,
       ROUND(AVG(P.RENDIMENTO_ESPERADO_SCHA), 1) AS RENDIMENTO_SCHA
FROM LEITURA_SENSOR L
JOIN PREVISAO_ML P ON P.ID_LEITURA = L.ID_LEITURA
GROUP BY L.MOTIVO_DECISAO
ORDER BY VOLUME_PREVISTO_L_M2 DESC;

-- nome: deteccoes_por_local
-- Fase 6: detecções do YOLO por câmera e classe
SELECT LOCAL_CAMERA, CLASSE, COUNT(*) AS DETECCOES,
       ROUND(AVG(CONFIANCA), 3) AS CONFIANCA_MEDIA,
       ROUND(MAX(CONFIANCA), 3) AS CONFIANCA_MAXIMA
FROM DETECCAO_VISAO
GROUP BY LOCAL_CAMERA, CLASSE
ORDER BY LOCAL_CAMERA, CLASSE;

-- nome: alertas_por_severidade
-- Fase 7: alertas gerados e status de envio pela AWS
SELECT SEVERIDADE, ORIGEM, STATUS_ENVIO, COUNT(*) AS ALERTAS
FROM ALERTA
GROUP BY SEVERIDADE, ORIGEM, STATUS_ENVIO
ORDER BY ALERTAS DESC;

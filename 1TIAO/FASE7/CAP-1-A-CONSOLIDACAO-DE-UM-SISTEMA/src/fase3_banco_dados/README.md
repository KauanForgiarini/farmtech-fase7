# Fase 3 — Banco de dados relacional (Oracle FIAP / SQLite)

| Arquivo | Função |
|---|---|
| `sql/oracle/01_ddl_farmtech.sql` | DDL Oracle: CULTURA, TALHAO, APLICACAO_INSUMO, LEITURA_SENSOR, PREVISAO_ML, DETECCAO_VISAO, ALERTA (PK, FK, CHECK, índices) |
| `sql/sqlite_schema.sql` | Mesmo modelo em SQLite (padrão offline) |
| `sql/consultas.sql` | 8 consultas analíticas em SQL padrão (blocos `-- nome:`) |
| `banco.py` | Conexão (`FARMTECH_DB=sqlite|oracle`), criação do esquema, inserção e consultas com parâmetros nomeados |
| `carga_banco.py` | ETL: recria o esquema e carrega os CSVs de todas as fases |

```bash
python farmtech.py fase3                    # SQLite
python farmtech.py fase3 --backend oracle   # requer ORACLE_USER / ORACLE_PASSWORD no .env
```
No SQL Developer: executar `01_ddl_farmtech.sql` (F5) e depois `consultas.sql`.

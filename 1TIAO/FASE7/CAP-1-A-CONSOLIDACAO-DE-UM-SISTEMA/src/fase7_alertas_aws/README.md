# Fase 7 — Serviço de alertas na AWS (S3 → Lambda → SNS)

| Arquivo | Função |
|---|---|
| `lambda_alertas/regras_alerta.py` | Fonte única dos limites, da regra de irrigação e das regras de alerta/ações corretivas (Python puro) |
| `lambda_alertas/lambda_function.py` | Handler da Lambda: aceita invocação direta, evento S3 ou API Gateway e publica no SNS (e-mail + SMS) |
| `deploy_aws.py` | Cria/atualiza tópico SNS, bucket S3 seguro, Lambda (LabRole) e gatilho; `--testar` e `--remover` |
| `publicar_alerta.py` | Lê sensores e visão do banco e envia à AWS (`--modo s3|lambda|sns|local|auto`) |
| `aws_config.py` · `aws_config.example.json` | Nomes/ARNs dos recursos (sem credenciais) |

Passo a passo e prints: `docs/aws/GUIA_AWS.md`.

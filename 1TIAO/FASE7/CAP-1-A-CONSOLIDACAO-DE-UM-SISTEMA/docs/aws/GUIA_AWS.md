# Guia de implantação do serviço de alertas no AWS Academy Learner Lab

Serviço: **Amazon S3 → AWS Lambda → Amazon SNS** (e-mail e SMS), região `us-east-1`.
Tempo estimado: 15 minutos. Custo: dentro dos créditos do Learner Lab (centavos).

## 1. Iniciar o laboratório e configurar as credenciais

1. No AWS Academy, abra o curso → **Modules → Launch AWS Academy Learner Lab** → **Start Lab**.
   Aguarde a bolinha ficar verde.
2. Clique em **AWS Details → AWS CLI: Show** e copie o bloco `[default] aws_access_key_id=...`.
3. Cole o bloco no arquivo `C:\Users\<você>\.aws\credentials` (crie a pasta `.aws` se não existir).
   Essas credenciais expiram a cada sessão (cerca de 4 horas): repita o passo ao reiniciar o lab.
   **Nunca** coloque essas chaves no projeto ou no GitHub.
4. Confira: na dashboard, página **Fase 5 → Verificar credenciais AWS** (ou
   `python -c "import boto3; print(boto3.client('sts').get_caller_identity()['Arn'])"`).

## 2. Implantar

Na pasta do projeto:

```bash
python farmtech.py aws-deploy --email seu.email@exemplo.com
# opcional: SMS para alertas ALTO/CRITICO (no Learner Lab o SMS pode ficar no sandbox)
python farmtech.py aws-deploy --email seu.email@exemplo.com --telefone +5555999999999
```

O script (`src/fase7_alertas_aws/deploy_aws.py`) cria, de forma idempotente:

| Recurso | Nome | Configuração |
|---|---|---|
| Tópico SNS | `farmtech-alertas` | DisplayName "FarmTech"; assinatura e-mail; SMS com `FilterPolicy {"severidade": ["CRITICO","ALTO"]}` |
| Bucket S3 | `farmtech-alertas-<conta>-us-east-1` | Block Public Access, SSE-S3 (AES-256), política que nega acesso sem HTTPS |
| Função Lambda | `farmtech-alertas` | Python 3.12, 128 MB, 30 s, role `LabRole`, variáveis `TOPIC_ARN`, `SEVERIDADE_MINIMA=MEDIO` |
| Gatilho | S3 → Lambda | `s3:ObjectCreated:*` em `sensores/*.json` e `visao/*.json` |

Os nomes/ARNs ficam em `data/aws_config.json` (ignorado pelo Git).

3. **Confirme a assinatura**: abra o e-mail "AWS Notification - Subscription Confirmation" e clique em
   *Confirm subscription*. Sem isso o SNS não entrega as mensagens.

## 3. Testar

```bash
python farmtech.py aws-deploy --testar     # invoca a Lambda com uma leitura crítica sintética
python farmtech.py alertas --modo s3       # dados reais do banco: S3 -> gatilho -> Lambda -> SNS
python farmtech.py alertas --modo lambda   # invocação direta da Lambda
```

Ou, na dashboard, página **Fase 7 · Alertas AWS** → canal "S3 → gatilho → Lambda → SNS" →
**Disparar serviço de alertas**. O histórico mostra o status e o `MessageId` de cada envio.

## 4. Prints para o README (salvar em `docs/aws/prints/` com estes nomes)

| Arquivo | Onde capturar | O que deve aparecer |
|---|---|---|
| `01_sns_topico.png` | SNS → Topics → `farmtech-alertas` | aba *Subscriptions* com o e-mail em **Confirmed** (e o SMS, se criado) |
| `02_lambda_visao_geral.png` | Lambda → Functions → `farmtech-alertas` | diagrama com o gatilho **S3** e a aba *Code* com `lambda_function.py` e `regras_alerta.py` |
| `03_lambda_configuracao.png` | Lambda → Configuration → Environment variables | `TOPIC_ARN`, `SEVERIDADE_MINIMA`, `NOME_FAZENDA`; em *General/Permissions*: runtime e `LabRole` |
| `04_lambda_teste.png` | Lambda → Test | evento com uma leitura crítica (copie o JSON abaixo) e o resultado `"status": "enviado"` |
| `05_s3_eventos.png` | S3 → bucket → Objects | pastas `sensores/` e `visao/` com os JSON; em *Properties → Event notifications* os 2 gatilhos |
| `06_cloudwatch_logs.png` | CloudWatch → Log groups → `/aws/lambda/farmtech-alertas` | log com `payloads`, `alertas` e `origem` |
| `07_email_recebido.png` | sua caixa de entrada | e-mail "[FarmTech][...]" com as ações corretivas |

Evento de teste para o console da Lambda (botão **Test**):

```json
{
  "origem": "sensores",
  "leituras": [
    {"data_hora": "2026-11-05 14:00:00", "talhao": "Talhão 1 - Soja Norte", "umidade": 34,
     "ph": 4.8, "temperatura": 36, "chuva_mm": 0, "n": 1, "p": 0, "k": 0, "bomba": 0,
     "motivo": "ph_fora_faixa"}
  ]
}
```

Evento de teste da visão computacional:

```json
{"origem": "visao", "deteccoes": [{"classe": "pessoa", "confianca": 0.91,
  "local": "Depósito de defensivos", "imagem": "pessoa_038.jpg", "data_hora": "2026-11-05 14:05:00"}]}
```

## 5. Desfazer (economizar créditos)

```bash
python farmtech.py aws-deploy --remover
```

## Problemas comuns

| Sintoma | Causa / solução |
|---|---|
| `ExpiredToken` ou `InvalidClientTokenId` | credenciais do lab expiraram: repita o passo 1.3 |
| Lambda não cria: `AccessDenied ... iam:PassRole` | use a `LabRole` (padrão do script); não crie roles novas no Learner Lab |
| E-mail não chega | assinatura não confirmada, ou caixa de spam; veja o status em SNS → Subscriptions |
| SMS não chega | contas de estudante ficam no *SMS sandbox*: registre e verifique o número em SNS → Text messaging, ou use só e-mail |
| Região errada | o Learner Lab aceita apenas `us-east-1` e `us-west-2` |

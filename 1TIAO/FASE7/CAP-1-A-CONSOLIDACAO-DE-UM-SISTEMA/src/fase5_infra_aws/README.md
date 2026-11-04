# Fase 5 — Infraestrutura e segurança na AWS

- `comparacao_custos_fase5.png`: estimativa da Fase 5 (EC2 t3.micro + EBS 50 GB): US$ 11,59/mês em
  us-east-1 e US$ 19,86/mês em sa-east-1; escolha de sa-east-1 pela restrição de armazenar no Brasil.
- `politica_minimo_privilegio.json`: política IAM de produção para a Lambda de alertas (somente
  `sns:Publish` no tópico, `s3:GetObject` nos prefixos de eventos, `rekognition:DetectLabels` e logs).
- Controles aplicados no deploy da Fase 7: bucket privado, SSE-S3, negação de acesso sem HTTPS,
  credenciais fora do código, assinaturas SNS confirmadas, filtro de severidade no SMS e logs no CloudWatch.
- Detalhes: página "Fase 5" da dashboard e `docs/aws/GUIA_AWS.md`.

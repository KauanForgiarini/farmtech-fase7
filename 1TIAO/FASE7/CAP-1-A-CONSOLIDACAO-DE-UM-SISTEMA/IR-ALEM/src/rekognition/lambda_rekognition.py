"""
Ir Além 1 - Função AWS Lambda "farmtech-rekognition".

Leva o reconhecimento de imagens da Fase 6 para a nuvem:

  câmera/dashboard --upload--> S3 imagens/*.jpg --gatilho--> esta Lambda
      --> Amazon Rekognition DetectLabels (pessoas e veículos, com caixas)
      --> mesmas regras de alerta da Fase 7 (regras_alerta.py)
      --> Amazon SNS (e-mail/SMS com a ação corretiva)

Variáveis de ambiente:
  TOPIC_ARN        tópico SNS criado pelo deploy da Fase 7
  CONFIANCA_MIN    confiança mínima do Rekognition em % (padrão 70)
  LOCAL_PADRAO     nome da câmera quando o objeto não traz metadado "local"
"""

import json
import os
import urllib.parse

import boto3

import regras_alerta as regras  # copiado para o pacote pelo deploy_rekognition.py

TOPIC_ARN = os.environ.get("TOPIC_ARN", "")
CONFIANCA_MIN = float(os.environ.get("CONFIANCA_MIN", "70"))
LOCAL_PADRAO = os.environ.get("LOCAL_PADRAO", "Câmera da fazenda")
ROTULOS = {"Person": "pessoa", "Human": "pessoa", "Car": "carro", "Vehicle": "carro",
           "Truck": "carro", "Pickup Truck": "carro", "Tractor": "carro"}

rekognition = boto3.client("rekognition")
s3 = boto3.client("s3")
sns = boto3.client("sns")


def detectar(bucket, chave):
    """Chama o DetectLabels e devolve detecções no mesmo formato do YOLO da Fase 6."""
    resposta = rekognition.detect_labels(
        Image={"S3Object": {"Bucket": bucket, "Name": chave}},
        MaxLabels=20, MinConfidence=CONFIANCA_MIN)
    metadados = s3.head_object(Bucket=bucket, Key=chave).get("Metadata", {})
    local = urllib.parse.unquote(metadados.get("local", LOCAL_PADRAO))
    deteccoes = []
    for rotulo in resposta["Labels"]:
        classe = ROTULOS.get(rotulo["Name"])
        if classe is None:
            continue
        # Instances traz uma caixa por objeto; sem instâncias, registra o rótulo da imagem
        instancias = rotulo.get("Instances") or [{"Confidence": rotulo["Confidence"]}]
        for instancia in instancias:
            deteccoes.append({
                "classe": classe, "confianca": round(instancia["Confidence"] / 100, 4),
                "local": local, "imagem": chave.split("/")[-1],
                "caixa": instancia.get("BoundingBox"), "rotulo_aws": rotulo["Name"],
            })
    return deteccoes, resposta["Labels"]


def lambda_handler(event, context):
    deteccoes, rotulos = [], []
    for registro in event.get("Records", []):
        bucket = registro["s3"]["bucket"]["name"]
        chave = urllib.parse.unquote_plus(registro["s3"]["object"]["key"])
        novas, todos = detectar(bucket, chave)
        deteccoes += novas
        rotulos += [{"imagem": chave, "rotulo": r["Name"], "confianca": round(r["Confidence"], 1)}
                    for r in todos]
    print(json.dumps({"rotulos": rotulos, "deteccoes": len(deteccoes)}, ensure_ascii=False))

    alertas = regras.avaliar_payload({"origem": "visao", "deteccoes": deteccoes})
    if not alertas or not TOPIC_ARN:
        return {"status": "sem_alertas" if not alertas else "sem_topico",
                "deteccoes": deteccoes, "rotulos": rotulos}
    mensagem = regras.montar_mensagem(alertas, "Fazenda FarmTech - Rekognition")
    resposta = sns.publish(
        TopicArn=TOPIC_ARN, Subject=mensagem["assunto"], MessageStructure="json",
        Message=json.dumps({"default": mensagem["corpo"], "email": mensagem["corpo"],
                            "sms": mensagem["sms"]}, ensure_ascii=False),
        MessageAttributes={
            "severidade": {"DataType": "String", "StringValue": mensagem["severidade"]},
            "origem": {"DataType": "String", "StringValue": "rekognition"}})
    return {"status": "enviado", "message_id": resposta["MessageId"],
            "alertas": len(alertas), "deteccoes": deteccoes}

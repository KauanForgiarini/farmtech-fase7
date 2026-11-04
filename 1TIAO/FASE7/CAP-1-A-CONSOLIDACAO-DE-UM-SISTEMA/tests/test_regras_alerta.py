"""Testes das regras agronômicas, da decisão de irrigação e da mensagem SNS."""

from fase7_alertas_aws.lambda_alertas import regras_alerta as regras


def leitura(**valores):
    base = {"umidade": 65, "ph": 6.3, "temperatura": 25, "chuva_mm": 0, "n": 1, "p": 1, "k": 1,
            "bomba": 0, "motivo": "umidade_adequada", "talhao": "Talhão 1", "data_hora": "2026-11-04 10:00:00"}
    base.update(valores)
    return base


def test_decisao_igual_ao_firmware():
    # mesma ordem de testes de deveIrrigar() no ESP32
    assert regras.decidir_irrigacao(50, 6.0, 8.0, True, True) == (False, "chuva_prevista")
    assert regras.decidir_irrigacao(85, 6.0, 0, True, True) == (False, "solo_saturado")
    assert regras.decidir_irrigacao(50, 4.8, 0, True, True) == (False, "ph_fora_faixa")
    assert regras.decidir_irrigacao(65, 6.0, 0, True, True) == (False, "umidade_adequada")
    assert regras.decidir_irrigacao(50, 6.0, 0, False, True) == (True, "irrigando")
    assert regras.decidir_irrigacao(50, 6.0, 0, False, False) == (False, "sem_nutrientes")


def test_leitura_normal_nao_gera_alerta():
    assert regras.avaliar_leitura(leitura()) == []


def test_umidade_critica_gera_alerta_critico_com_volume_do_modelo():
    alertas = regras.avaliar_leitura(leitura(umidade=32, volume_previsto=3.456))
    critico = next(a for a in alertas if a["codigo"] == "UMIDADE_CRITICA")
    assert critico["severidade"] == "CRITICO"
    assert "3.46 L/m²" in critico["acao"] and "Fase 4" in critico["acao"]


def test_ph_que_bloqueia_irrigacao_e_critico():
    alertas = {a["codigo"]: a for a in regras.avaliar_leitura(leitura(ph=4.7))}
    assert alertas["PH_ACIDO"]["severidade"] == "CRITICO"
    alertas = {a["codigo"]: a for a in regras.avaliar_leitura(leitura(ph=5.3))}
    assert alertas["PH_ACIDO"]["severidade"] == "ALTO"


def test_aceita_formato_do_banco_em_maiusculas():
    registro = {"DATA_HORA": "2026-11-04 10:00:00", "TALHAO": "Talhão 1", "UMIDADE_SOLO_PCT": 52,
                "PH_SOLO": 6.1, "TEMPERATURA_C": 26, "CHUVA_PREVISTA_MM": 0, "N_PRESENTE": 1,
                "P_PRESENTE": 0, "K_PRESENTE": 0, "BOMBA_LIGADA": 0, "MOTIVO_DECISAO": "sem_nutrientes"}
    codigos = [a["codigo"] for a in regras.avaliar_leitura(registro)]
    assert codigos == ["IRRIGACAO_BLOQUEADA_NPK"]


def test_deteccoes_de_visao_respeitam_confianca_minima():
    assert regras.avaliar_deteccao({"classe": "pessoa", "confianca": 0.3}) == []
    alerta = regras.avaliar_deteccao({"classe": "person", "confianca": 0.9, "local": "Portaria"})[0]
    assert alerta["codigo"] == "PESSOA_DETECTADA" and alerta["local"] == "Portaria"
    assert regras.avaliar_deteccao({"CLASSE": "carro", "CONFIANCA": 0.8,
                                    "LOCAL_CAMERA": "Galpão"})[0]["local"] == "Galpão"


def test_payload_consolida_repeticoes_e_ordena_por_severidade():
    payload = {"leituras": [leitura(ph=5.2, data_hora=f"2026-11-04 0{h}:00:00") for h in range(4)]
               + [leitura(umidade=30)],
               "deteccoes": [{"classe": "carro", "confianca": 0.9, "local": "Portaria"}] * 3}
    alertas = regras.avaliar_payload(payload)
    assert alertas[0]["severidade"] == "CRITICO"
    ph = next(a for a in alertas if a["codigo"] == "PH_ACIDO")
    assert ph["ocorrencias"] == 4
    assert next(a for a in alertas if a["codigo"] == "VEICULO_DETECTADO")["ocorrencias"] == 3


def test_mensagem_tem_assunto_ascii_curto_e_sms():
    alertas = regras.avaliar_payload({"leituras": [leitura(umidade=30, ph=4.6)]})
    mensagem = regras.montar_mensagem(alertas, "Fazenda São João")
    assert mensagem["assunto"].isascii() and len(mensagem["assunto"]) < 100
    assert "AÇÃO CORRETIVA" in mensagem["corpo"]
    assert mensagem["sms"].isascii() and mensagem["severidade"] == "CRITICO"


def test_filtro_de_severidade():
    alertas = [{"severidade": s} for s in regras.SEVERIDADES]
    assert [a["severidade"] for a in regras.filtrar_severidade(alertas, "ALTO")] == ["ALTO", "CRITICO"]

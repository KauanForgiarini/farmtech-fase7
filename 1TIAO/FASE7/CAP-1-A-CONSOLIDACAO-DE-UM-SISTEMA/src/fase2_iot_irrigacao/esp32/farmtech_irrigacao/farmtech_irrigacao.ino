/*
 * ============================================================
 *  FarmTech Solutions - Sistema de Irrigação Inteligente
 *  Fase 2 (revisado na Fase 7 - sistema integrado)
 *  Kauan Maciel Forgiarini | RM 574005 | FIAP IA
 * ============================================================
 *
 *  Cultura monitorada: SOJA (Talhão 1 - Soja Norte, cadastrado na Fase 1)
 *
 *  Sensores (substitutos do Wokwi):
 *    - Botão N  (GPIO 12) -> Nitrogênio presente/ausente
 *    - Botão P  (GPIO 13) -> Fósforo presente/ausente
 *    - Botão K  (GPIO 14) -> Potássio presente/ausente
 *    - LDR      (GPIO 34) -> pH do solo (0-4095 mapeado para 0-14)
 *    - DHT22    (GPIO 15) -> umidade (convertida em umidade do solo) e temperatura
 *  Atuadores:
 *    - Relé     (GPIO 26) -> bomba d'água
 *    - LED verde    (GPIO 2) -> irrigando
 *    - LED vermelho (GPIO 4) -> parado / alerta
 *
 *  Regra de irrigação (idêntica a decidir_irrigacao() em Python,
 *  src/fase7_alertas_aws/lambda_alertas/regras_alerta.py):
 *    1. chuva prevista               -> não irriga
 *    2. umidade do solo >= 80%        -> não irriga (saturado)
 *    3. pH fora de 5,0 a 7,5          -> não irriga (corrigir solo)
 *    4. umidade do solo >= 60%        -> não irriga (adequada)
 *    5. umidade < 60% e (P ou K)      -> IRRIGA
 *    6. caso contrário                -> não irriga (adubar antes)
 *
 *  Integração:
 *    - Serial (115200): recebe '1' (chuva prevista) ou '0' (sem chuva),
 *      enviados pelo simulador_esp32.py a partir da API Open-Meteo.
 *    - A cada ciclo imprime uma linha "CSV,..." lida pelo Python, que grava
 *      no banco (Fase 3), alimenta os modelos (Fase 4) e os alertas AWS (Fase 7).
 *
 *  Revisão Fase 7: pinos alinhados ao diagram.json (P=13, K=14), leitura da
 *  temperatura corrigida e limiares sincronizados com o restante do sistema.
 * ============================================================
 */

#include "DHTesp.h"

// -------- Pinos --------
#define PIN_BTN_N     12
#define PIN_BTN_P     13
#define PIN_BTN_K     14
#define PIN_LDR       34
#define PIN_DHT       15
#define PIN_RELAY     26
#define PIN_LED_ON     2
#define PIN_LED_OFF    4

// -------- Limiares (mesmos de regras_alerta.LIMITES) --------
const float UMIDADE_MIN   = 60.0;
const float UMIDADE_MAX   = 80.0;
const float PH_MIN        = 5.0;
const float PH_MAX        = 7.5;
const unsigned long CICLO_MS = 3000;

DHTesp dht;

// -------- Estado --------
bool  nitrogenio    = false;
bool  fosforo       = false;
bool  potassio      = false;
float phValor       = 0.0;
float umidadeSolo   = 0.0;
float temperatura   = 0.0;
bool  irrigando     = false;
int   previsaoChuva = 0;      // 0 = sem chuva, 1 = chuva prevista
const char* motivo  = "";

// -------- Protótipos --------
float ldrParaPH(int ldrRaw);
float simularUmidadeSolo(float umidadeAr);
bool  deveIrrigar();
void  lerSerial();
void  exibirStatus();

void setup() {
  Serial.begin(115200);
  dht.setup(PIN_DHT, DHTesp::DHT22);

  pinMode(PIN_BTN_N, INPUT_PULLUP);
  pinMode(PIN_BTN_P, INPUT_PULLUP);
  pinMode(PIN_BTN_K, INPUT_PULLUP);
  pinMode(PIN_RELAY, OUTPUT);
  pinMode(PIN_LED_ON, OUTPUT);
  pinMode(PIN_LED_OFF, OUTPUT);

  digitalWrite(PIN_RELAY, LOW);
  digitalWrite(PIN_LED_ON, LOW);
  digitalWrite(PIN_LED_OFF, HIGH);

  Serial.println("=== FarmTech Solutions - Irrigacao Inteligente (Fase 7) ===");
  Serial.println("Cultura: SOJA | Talhao 1 - Soja Norte");
  Serial.println("Envie '1' = chuva prevista | '0' = sem chuva");
  Serial.println("CSV,N,P,K,pH,UmidadeSolo,Temp,Chuva,Bomba,Motivo");
  delay(2000);
}

void loop() {
  // 1. Nutrientes (INPUT_PULLUP: pressionado = LOW = presente)
  nitrogenio = (digitalRead(PIN_BTN_N) == LOW);
  fosforo    = (digitalRead(PIN_BTN_P) == LOW);
  potassio   = (digitalRead(PIN_BTN_K) == LOW);

  // 2. pH via LDR
  phValor = ldrParaPH(analogRead(PIN_LDR));

  // 3. Umidade e temperatura via DHT22
  TempAndHumidity dados = dht.getTempAndHumidity();
  if (isnan(dados.humidity) || isnan(dados.temperature)) {
    Serial.println("[ERRO] Falha na leitura do DHT22!");
    delay(2000);
    return;
  }
  temperatura = dados.temperature;
  umidadeSolo = simularUmidadeSolo(dados.humidity);

  // 4. Previsão de chuva recebida do Python
  lerSerial();

  // 5. Decisão e acionamento
  irrigando = deveIrrigar();
  digitalWrite(PIN_RELAY, irrigando ? HIGH : LOW);
  digitalWrite(PIN_LED_ON, irrigando ? HIGH : LOW);
  digitalWrite(PIN_LED_OFF, irrigando ? LOW : HIGH);

  exibirStatus();
  delay(CICLO_MS);
}

// LDR 0-4095 -> pH 0-14. No Wokwi o LDR escuro retorna valores muito baixos;
// abaixo de 300 assume-se pH 6,5 para a simulação partir de um solo adequado.
float ldrParaPH(int ldrRaw) {
  if (ldrRaw < 300) {
    return 6.5;
  }
  return (float)ldrRaw * 14.0 / 4095.0;
}

// O DHT22 mede umidade do AR. A conversão abaixo (fator 0,65) representa a
// umidade do SOLO: ar a 100% -> solo 65%; ar a 70% -> solo 45% (seco).
float simularUmidadeSolo(float umidadeAr) {
  return umidadeAr * 0.65;
}

bool deveIrrigar() {
  if (previsaoChuva == 1)                  { motivo = "chuva_prevista";   return false; }
  if (umidadeSolo >= UMIDADE_MAX)          { motivo = "solo_saturado";    return false; }
  if (phValor < PH_MIN || phValor > PH_MAX){ motivo = "ph_fora_faixa";    return false; }
  if (umidadeSolo >= UMIDADE_MIN)          { motivo = "umidade_adequada"; return false; }
  if (fosforo || potassio)                 { motivo = "irrigando";        return true;  }
  motivo = "sem_nutrientes";
  return false;
}

void lerSerial() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '0') {
      previsaoChuva = 0;
    } else if (c == '1') {
      previsaoChuva = 1;
    }
  }
}

void exibirStatus() {
  Serial.println("--------------------------------------------------");
  Serial.printf("NPK -> N:%s | P:%s | K:%s\n", nitrogenio ? "SIM" : "NAO",
                fosforo ? "SIM" : "NAO", potassio ? "SIM" : "NAO");
  Serial.printf("pH: %.2f | Umidade solo: %.1f%% | Temp: %.1f C | Chuva prevista: %s\n",
                phValor, umidadeSolo, temperatura, previsaoChuva ? "SIM" : "NAO");
  Serial.printf("Bomba: %s (%s)\n", irrigando ? "LIGADA" : "DESLIGADA", motivo);

  // Linha estruturada lida pelo Python (src/fase2_iot_irrigacao/simulador_esp32.py --serial)
  Serial.printf("CSV,%d,%d,%d,%.2f,%.1f,%.1f,%d,%d,%s\n",
                nitrogenio ? 1 : 0, fosforo ? 1 : 0, potassio ? 1 : 0,
                phValor, umidadeSolo, temperatura, previsaoChuva,
                irrigando ? 1 : 0, motivo);
}

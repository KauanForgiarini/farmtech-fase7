# Fase 2 — ESP32, sensores e irrigação automática

| Arquivo | Função |
|---|---|
| `esp32/farmtech_irrigacao/farmtech_irrigacao.ino` | Firmware: botões N/P/K (GPIO 12/13/14), LDR→pH (GPIO 34), DHT22 (GPIO 15), relé da bomba (GPIO 26), LEDs; linha `CSV,...` na Serial |
| `esp32/farmtech_irrigacao/diagram.json` | Circuito para importar no [Wokwi](https://wokwi.com) |
| `esp32/platformio.ini` · `esp32/wokwi.toml` | Opcional: compilar com PlatformIO e simular no Wokwi for VS Code (porta RFC2217 4000) |
| `simulador_esp32.py` | Leituras horárias com a mesma regra do firmware (5 cenários) ou leitura da Serial real/Wokwi (`--serial`) |
| `clima_open_meteo.py` | Previsão de chuva gratuita (Open-Meteo) enviada ao ESP32 |

```bash
python farmtech.py fase2 --leituras 72 --cenario realista --clima
python farmtech.py fase2 --serial rfc2217://localhost:4000 --leituras 10
```

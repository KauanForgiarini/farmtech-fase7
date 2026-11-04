/*
 * FarmTech Solutions — Fase 4
 * Sugestões de Irrigação e Manejo Agrícola
 * Kauan Maciel Forgiarini | RM574005 | FIAP IA
 *
 * Recebe as previsões geradas pelo modelo Python (Scikit-Learn)
 * e traduz em ações concretas de manejo para o ESP32 / terminal.
 *
 * Compilar:
 *   g++ -std=c++17 -o farmtech_suggestions c_suggestions/farmtech_suggestions.cpp
 * Executar:
 *   ./farmtech_suggestions
 */

#include <iostream>
#include <iomanip>
#include <string>
#include <vector>
#include <cmath>
#include <sstream>

// ─────────────────────────────────────────────
// ESTRUTURAS DE DADOS
// ─────────────────────────────────────────────

struct LeituraSensor {
    float umidade_pct;
    float ph_solo;
    float temperatura_c;
    float chuva_prevista_mm;
    float n_kgha;
    float p_kgha;
    float k_kgha;
};

struct PrevisaoML {
    float volume_irrigacao_L;      // L/m² — saída do modelo Python
    float necessidade_fert_kgha;   // kg/ha
    float rendimento_esperado_scha; // sc/ha
};

struct RecomendacaoManejo {
    std::string acao_irrigacao;
    std::string acao_fertilizacao;
    std::string acao_ph;
    std::string status_rendimento;
    bool bomba_ligar;
    float volume_aplicar;
    std::vector<std::string> alertas;
    int prioridade;  // 1=baixa, 2=media, 3=alta, 4=urgente
};

// ─────────────────────────────────────────────
// CONSTANTES AGRÍCOLAS — SOJA (Embrapa 2023)
// ─────────────────────────────────────────────

const float PH_MINIMO        = 5.5f;
const float PH_MAXIMO        = 7.0f;
const float UMIDADE_CRITICA  = 40.0f;  // abaixo: irrigação urgente
const float UMIDADE_MINIMA   = 60.0f;  // abaixo: irrigar
const float UMIDADE_MAXIMA   = 80.0f;  // acima: solo saturado
const float CHUVA_LIMITE_MM  = 5.0f;   // acima: não irrigar
const float RENDIMENTO_MEDIO = 55.0f;  // sc/ha referência RS

// ─────────────────────────────────────────────
// FUNÇÕES AUXILIARES
// ─────────────────────────────────────────────

std::string separador(char c = '-', int n = 60) {
    return std::string(n, c);
}

void imprimir_leitura(const LeituraSensor& s) {
    std::cout << separador() << "\n";
    std::cout << "  LEITURA DOS SENSORES ESP32\n";
    std::cout << separador() << "\n";
    std::cout << std::fixed << std::setprecision(1);
    std::cout << "  Umidade do solo : " << s.umidade_pct        << " %\n";
    std::cout << "  pH do solo      : " << s.ph_solo            << "\n";
    std::cout << "  Temperatura     : " << s.temperatura_c      << " °C\n";
    std::cout << "  Chuva prevista  : " << s.chuva_prevista_mm  << " mm\n";
    std::cout << "  N (Nitrogênio)  : " << s.n_kgha             << " kg/ha\n";
    std::cout << "  P (Fósforo)     : " << s.p_kgha             << " kg/ha\n";
    std::cout << "  K (Potássio)    : " << s.k_kgha             << " kg/ha\n";
    std::cout << separador() << "\n";
}

void imprimir_previsao(const PrevisaoML& p) {
    std::cout << "\n  PREVISÕES DO MODELO DE IA (Python/Scikit-Learn)\n";
    std::cout << separador() << "\n";
    std::cout << std::fixed << std::setprecision(2);
    std::cout << "  Vol. irrigação  : " << p.volume_irrigacao_L        << " L/m²\n";
    std::cout << "  Fertilização    : " << p.necessidade_fert_kgha     << " kg/ha\n";
    std::cout << "  Rendimento est. : " << p.rendimento_esperado_scha  << " sc/ha\n";
    std::cout << separador() << "\n";
}

// ─────────────────────────────────────────────
// ENGINE DE DECISÃO
// ─────────────────────────────────────────────

RecomendacaoManejo gerar_recomendacao(
    const LeituraSensor& sensor,
    const PrevisaoML&    previsao
) {
    RecomendacaoManejo rec;
    rec.bomba_ligar   = false;
    rec.volume_aplicar = 0.0f;
    rec.prioridade    = 1;

    // ── IRRIGAÇÃO ──────────────────────────────
    if (sensor.chuva_prevista_mm > CHUVA_LIMITE_MM) {
        rec.acao_irrigacao = "NAO_IRRIGAR — chuva prevista (" +
            std::to_string((int)sensor.chuva_prevista_mm) + " mm). Economia hidrica ativada.";
        rec.bomba_ligar = false;

    } else if (sensor.umidade_pct >= UMIDADE_MAXIMA) {
        rec.acao_irrigacao = "NAO_IRRIGAR — solo saturado (" +
            std::to_string((int)sensor.umidade_pct) + "%). Risco de encharcamento.";
        rec.alertas.push_back("ALERTA: Solo com excesso de umidade — verificar drenagem.");
        rec.bomba_ligar = false;

    } else if (sensor.umidade_pct < UMIDADE_CRITICA) {
        rec.acao_irrigacao = "IRRIGACAO_URGENTE — umidade critica (" +
            std::to_string((int)sensor.umidade_pct) +
            "%). Aplicar " + std::to_string(previsao.volume_irrigacao_L).substr(0,4) + " L/m2 imediatamente.";
        rec.bomba_ligar    = true;
        rec.volume_aplicar = previsao.volume_irrigacao_L;
        rec.prioridade     = 4;

    } else if (sensor.umidade_pct < UMIDADE_MINIMA) {
        rec.acao_irrigacao = "IRRIGAR — umidade abaixo do ideal (" +
            std::to_string((int)sensor.umidade_pct) +
            "%). Volume recomendado: " + std::to_string(previsao.volume_irrigacao_L).substr(0,4) + " L/m2.";
        rec.bomba_ligar    = true;
        rec.volume_aplicar = previsao.volume_irrigacao_L;
        rec.prioridade     = std::max(rec.prioridade, 3);

    } else {
        rec.acao_irrigacao = "AGUARDAR — umidade adequada (" +
            std::to_string((int)sensor.umidade_pct) + "%). Proxima verificacao em 3h.";
    }

    // ── CORREÇÃO DE pH ─────────────────────────
    if (sensor.ph_solo < PH_MINIMO) {
        float deficit = PH_MINIMO - sensor.ph_solo;
        float calcario_tha = deficit * 2.5f;
        std::ostringstream oss;
        oss << std::fixed << std::setprecision(2);
        oss << "CORRECAO_PH — pH acido (" << sensor.ph_solo << "). "
            << "Aplicar aprox. " << calcario_tha << " t/ha de calcario dolomitico.";
        rec.acao_ph = oss.str();
        rec.alertas.push_back("ALERTA: pH abaixo de 5.5 reduz disponibilidade de nutrientes e prejudica raizes.");
        rec.prioridade = std::max(rec.prioridade, 3);

    } else if (sensor.ph_solo > PH_MAXIMO) {
        float excesso = sensor.ph_solo - PH_MAXIMO;
        std::ostringstream oss;
        oss << std::fixed << std::setprecision(2);
        oss << "CORRECAO_PH — pH alcalino (" << sensor.ph_solo << "). "
            << "Aplicar enxofre elementar para reducao de " << excesso << " unidades.";
        rec.acao_ph = oss.str();
        rec.alertas.push_back("ALERTA: pH acima de 7.0 limita absorcao de micronutrientes.");
        rec.prioridade = std::max(rec.prioridade, 2);

    } else {
        std::ostringstream oss;
        oss << std::fixed << std::setprecision(2);
        oss << "pH_IDEAL — " << sensor.ph_solo << " dentro da faixa ideal para soja (5.5-7.0).";
        rec.acao_ph = oss.str();
    }

    // ── FERTILIZAÇÃO ──────────────────────────
    std::ostringstream oss_fert;
    oss_fert << std::fixed << std::setprecision(1);
    if (previsao.necessidade_fert_kgha > 20.0f) {
        oss_fert << "FERTILIZACAO_ALTA — Aplicar " << previsao.necessidade_fert_kgha
                 << " kg/ha. Priorizar NPK balanceado (formulacao 05-25-25).";
        rec.prioridade = std::max(rec.prioridade, 3);
        rec.alertas.push_back("ALERTA: Deficiencia nutricional pode reduzir rendimento em ate 30%.");
    } else if (previsao.necessidade_fert_kgha > 10.0f) {
        oss_fert << "FERTILIZACAO_MODERADA — Aplicar " << previsao.necessidade_fert_kgha
                 << " kg/ha. Realizar analise foliar para confirmar.";
        rec.prioridade = std::max(rec.prioridade, 2);
    } else {
        oss_fert << "SOLO_NUTRIDO — Necessidade minima de " << previsao.necessidade_fert_kgha
                 << " kg/ha. Manutencao de rotina suficiente.";
    }
    rec.acao_fertilizacao = oss_fert.str();

    // ── RENDIMENTO ────────────────────────────
    std::ostringstream oss_rend;
    oss_rend << std::fixed << std::setprecision(1);
    float desvio_pct = ((previsao.rendimento_esperado_scha - RENDIMENTO_MEDIO) / RENDIMENTO_MEDIO) * 100.0f;
    oss_rend << "Estimativa: " << previsao.rendimento_esperado_scha << " sc/ha";
    if (desvio_pct >= 5.0f) {
        oss_rend << " (++" << std::abs(desvio_pct) << "% acima da media regional). Otimo potencial.";
    } else if (desvio_pct >= -5.0f) {
        oss_rend << " (dentro da media regional de " << RENDIMENTO_MEDIO << " sc/ha).";
    } else {
        oss_rend << " (" << std::abs(desvio_pct) << "% abaixo da media). Revisar manejo.";
        rec.alertas.push_back("ATENCAO: Rendimento projetado abaixo da media. Verificar irrigacao e NPK.");
        rec.prioridade = std::max(rec.prioridade, 2);
    }
    rec.status_rendimento = oss_rend.str();

    return rec;
}

// ─────────────────────────────────────────────
// IMPRESSÃO DA RECOMENDAÇÃO
// ─────────────────────────────────────────────

void imprimir_recomendacao(const RecomendacaoManejo& rec) {
    const std::string cores_prioridade[] = {
        "", "[BAIXA]", "[MEDIA]", "[ALTA]", "[URGENTE]"
    };

    std::cout << "\n" << separador('=') << "\n";
    std::cout << "  RECOMENDACOES DE MANEJO — FarmTech Solutions\n";
    std::cout << "  Prioridade: " << cores_prioridade[rec.prioridade] << "\n";
    std::cout << separador('=') << "\n";

    std::cout << "\n  [IRRIGACAO]\n    " << rec.acao_irrigacao << "\n";
    if (rec.bomba_ligar) {
        std::cout << "    >> BOMBA: LIGAR | Volume: "
                  << std::fixed << std::setprecision(2)
                  << rec.volume_aplicar << " L/m2\n";
    } else {
        std::cout << "    >> BOMBA: MANTER DESLIGADA\n";
    }

    std::cout << "\n  [CORRECAO DE PH]\n    " << rec.acao_ph << "\n";

    std::cout << "\n  [FERTILIZACAO]\n    " << rec.acao_fertilizacao << "\n";

    std::cout << "\n  [RENDIMENTO ESPERADO]\n    " << rec.status_rendimento << "\n";

    if (!rec.alertas.empty()) {
        std::cout << "\n  [ALERTAS]\n";
        for (const auto& a : rec.alertas) {
            std::cout << "    !! " << a << "\n";
        }
    }

    std::cout << separador('=') << "\n";
}

// ─────────────────────────────────────────────
// ENTRADA INTERATIVA
// ─────────────────────────────────────────────

LeituraSensor entrada_interativa() {
    LeituraSensor s;
    std::cout << "\n  [ENTRADA MANUAL DOS SENSORES]\n";
    std::cout << "  Umidade do solo (%): ";   std::cin >> s.umidade_pct;
    std::cout << "  pH do solo:          ";   std::cin >> s.ph_solo;
    std::cout << "  Temperatura (C):     ";   std::cin >> s.temperatura_c;
    std::cout << "  Chuva prevista (mm): ";   std::cin >> s.chuva_prevista_mm;
    std::cout << "  N - Nitrogenio (kg/ha): "; std::cin >> s.n_kgha;
    std::cout << "  P - Fosforo    (kg/ha): "; std::cin >> s.p_kgha;
    std::cout << "  K - Potassio   (kg/ha): "; std::cin >> s.k_kgha;
    return s;
}

PrevisaoML entrada_previsao() {
    PrevisaoML p;
    std::cout << "\n  [ENTRADA DAS PREVISOES DO MODELO PYTHON]\n";
    std::cout << "  Volume irrigacao (L/m2):  "; std::cin >> p.volume_irrigacao_L;
    std::cout << "  Fertilizacao (kg/ha):     "; std::cin >> p.necessidade_fert_kgha;
    std::cout << "  Rendimento esperado (sc/ha): "; std::cin >> p.rendimento_esperado_scha;
    return p;
}

// ─────────────────────────────────────────────
// MAIN
// ─────────────────────────────────────────────

int main() {
    std::cout << "\n" << separador('=') << "\n";
    std::cout << "  FARMTECH SOLUTIONS — FASE 4\n";
    std::cout << "  Assistente de Manejo Agricola Inteligente\n";
    std::cout << "  Kauan Maciel Forgiarini | RM574005 | FIAP IA\n";
    std::cout << separador('=') << "\n";

    int opcao = 0;
    std::cout << "\n  Modo de operacao:\n";
    std::cout << "    1 - Usar valores pre-definidos (demo)\n";
    std::cout << "    2 - Inserir valores manualmente\n";
    std::cout << "  Opcao: ";
    std::cin >> opcao;

    LeituraSensor sensor;
    PrevisaoML    previsao;

    if (opcao == 2) {
        sensor   = entrada_interativa();
        previsao = entrada_previsao();
    } else {
        // Cenário demo — leitura típica com umidade baixa e pH fora da faixa
        sensor   = {48.5f, 5.1f, 27.3f, 0.0f, 82.0f, 55.0f, 78.0f};
        previsao = {2.45f, 18.7f, 38.2f};
        std::cout << "\n  [MODO DEMO] Usando leitura de exemplo.\n";
    }

    imprimir_leitura(sensor);
    imprimir_previsao(previsao);

    RecomendacaoManejo rec = gerar_recomendacao(sensor, previsao);
    imprimir_recomendacao(rec);

    // Loop de monitoramento contínuo simulado
    std::cout << "\n  Pressione ENTER para simular nova leitura (+3h) ou 'q' para sair: ";
    std::cin.ignore();
    std::string resp;
    std::getline(std::cin, resp);

    if (resp != "q") {
        // Simula melhora gradual após irrigação
        if (rec.bomba_ligar) {
            sensor.umidade_pct = std::min(75.0f, sensor.umidade_pct + previsao.volume_irrigacao_L * 4.0f);
        }
        previsao.rendimento_esperado_scha += 1.2f;

        std::cout << "\n  [CICLO +3H — POS-IRRIGACAO]\n";
        imprimir_leitura(sensor);
        imprimir_previsao(previsao);
        RecomendacaoManejo rec2 = gerar_recomendacao(sensor, previsao);
        imprimir_recomendacao(rec2);
    }

    std::cout << "\n  FarmTech Solutions — Ciclo encerrado.\n\n";
    return 0;
}

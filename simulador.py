import math
import os
import random

import pandas as pd

import config


HORAS_POR_PASSO = config.PASSO_MINUTOS / 60

FAIXAS_CHEGADA = [
    (7.0, 9.5, 6),
    (12.5, 14.5, 4),
    (18.0, 19.5, 6),
]


def hora_do_passo(passo):
    return passo * HORAS_POR_PASSO


def formatar_horario(hora):
    horas = int(hora)
    minutos = round((hora - horas) * 60)
    return f"{horas:02d}:{minutos:02d}"


def eh_horario_ponta(hora):
    return config.DIA_UTIL and config.INICIO_PONTA <= hora < config.FIM_PONTA


def tarifa_da_hora(hora):
    if eh_horario_ponta(hora):
        return config.TARIFA_PONTA
    return config.TARIFA_FORA_PONTA


def gerar_solar(hora, nuvem):
    if hora < config.INICIO_SOL or hora >= config.FIM_SOL:
        return 0.0

    duracao_sol = config.FIM_SOL - config.INICIO_SOL
    curva = math.sin(math.pi * (hora - config.INICIO_SOL) / duracao_sol)
    return round(config.POTENCIA_SOLAR_KWP * curva * nuvem, 2)


def gerar_carga_predio(hora):
    if 7 <= hora < 23:
        carga = 38 + 10 * math.sin(math.pi * (hora - 7) / 16)
    else:
        carga = 22

    carga += random.uniform(-2, 2)
    return round(carga, 2)


def gerar_veiculos():
    veiculos = []

    for inicio, fim, quantidade in FAIXAS_CHEGADA:
        for i in range(quantidade):
            hora_chegada = random.uniform(inicio, fim)
            passo_chegada = int(hora_chegada / HORAS_POR_PASSO)
            permanencia = random.uniform(2, 4.5)
            passo_saida = min(passo_chegada + int(permanencia / HORAS_POR_PASSO), config.PASSOS_POR_DIA)

            if random.random() < config.CHANCE_RECARGA_RAPIDA:
                tipo = "rapida"
                potencia = config.POTENCIA_RAPIDA_KW
            else:
                tipo = "normal"
                potencia = config.POTENCIA_NORMAL_KW

            veiculos.append({
                "passo_chegada": passo_chegada,
                "passo_saida": passo_saida,
                "tipo_recarga": tipo,
                "potencia_kw": potencia,
                "energia_pedida_kwh": round(random.uniform(10, 40), 1),
            })

    veiculos.sort(key=lambda v: v["passo_chegada"])

    for numero, veiculo in enumerate(veiculos, start=1):
        veiculo["veiculo"] = f"Veiculo {numero:02d}"

    return veiculos


def distribuir_vagas(veiculos):
    vaga_livre_em = [0] * config.QTD_VAGAS
    aceitos = []
    recusados = []

    for veiculo in veiculos:
        vaga_escolhida = None

        for vaga in range(config.QTD_VAGAS):
            if vaga_livre_em[vaga] <= veiculo["passo_chegada"]:
                vaga_escolhida = vaga
                break

        if vaga_escolhida is None:
            recusados.append(veiculo["veiculo"])
            continue

        veiculo["vaga"] = f"Vaga {vaga_escolhida + 1}"
        vaga_livre_em[vaga_escolhida] = veiculo["passo_saida"]
        aceitos.append(veiculo)

    return aceitos, recusados


def recarga_sem_controle(veiculos):
    falta_carregar = {v["veiculo"]: v["energia_pedida_kwh"] for v in veiculos}
    demanda_por_passo = []
    conectados_por_passo = []

    for passo in range(config.PASSOS_POR_DIA):
        demanda = 0.0
        conectados = 0

        for v in veiculos:
            if v["passo_chegada"] <= passo < v["passo_saida"]:
                conectados += 1
                restante = falta_carregar[v["veiculo"]]

                if restante > 0:
                    potencia = min(v["potencia_kw"], restante / HORAS_POR_PASSO)
                    falta_carregar[v["veiculo"]] -= potencia * HORAS_POR_PASSO
                    demanda += potencia

        demanda_por_passo.append(round(demanda, 2))
        conectados_por_passo.append(conectados)

    for v in veiculos:
        entregue = v["energia_pedida_kwh"] - falta_carregar[v["veiculo"]]
        v["energia_entregue_sem_controle_kwh"] = round(entregue, 2)

    return demanda_por_passo, conectados_por_passo


def simular_dia():
    random.seed(config.SEMENTE)

    veiculos = gerar_veiculos()
    veiculos, recusados = distribuir_vagas(veiculos)
    demanda_ev, conectados = recarga_sem_controle(veiculos)

    linhas = []
    nuvem = 1.0

    for passo in range(config.PASSOS_POR_DIA):
        hora = hora_do_passo(passo)

        nuvem += random.uniform(-0.08, 0.08)
        nuvem = max(0.6, min(1.0, nuvem))

        solar = gerar_solar(hora, nuvem)
        predio = gerar_carga_predio(hora)

        linhas.append({
            "passo": passo,
            "horario": formatar_horario(hora),
            "hora": hora,
            "ponta": eh_horario_ponta(hora),
            "tarifa_kwh": tarifa_da_hora(hora),
            "solar_kw": solar,
            "carga_predio_kw": predio,
            "carros_conectados": conectados[passo],
            "demanda_ev_sem_controle_kw": demanda_ev[passo],
            "demanda_total_sem_controle_kw": round(predio + demanda_ev[passo], 2),
        })

    tabela = pd.DataFrame(linhas)

    colunas_sessoes = [
        "veiculo", "vaga", "tipo_recarga", "potencia_kw",
        "passo_chegada", "passo_saida", "energia_pedida_kwh",
        "energia_entregue_sem_controle_kwh",
    ]
    sessoes = pd.DataFrame(veiculos)[colunas_sessoes]

    return tabela, sessoes, recusados


def salvar_simulacao(tabela, sessoes):
    os.makedirs(config.PASTA_DADOS, exist_ok=True)
    tabela.to_csv(config.ARQUIVO_SIMULACAO, index=False)
    sessoes.to_csv(config.ARQUIVO_SESSOES, index=False)


def mostrar_resumo(tabela, sessoes, recusados):
    linha_pico = tabela.loc[tabela["demanda_total_sem_controle_kw"].idxmax()]
    energia_solar = tabela["solar_kw"].sum() * HORAS_POR_PASSO
    energia_ev = tabela["demanda_ev_sem_controle_kw"].sum() * HORAS_POR_PASSO
    passos_acima = (tabela["demanda_total_sem_controle_kw"] > config.DEMANDA_CONTRATADA_KW).sum()

    print("=" * 58)
    print(" ChargeGrid Intelligence - Simulador do dia")
    print("=" * 58)
    print(f" Veiculos atendidos ......... {len(sessoes)}")
    print(f" Veiculos sem vaga .......... {len(recusados)}")
    print(f" Energia pedida pelos EVs ... {energia_ev:.1f} kWh")
    print(f" Geracao solar no dia ....... {energia_solar:.1f} kWh")
    print(f" Pico de demanda ............ {linha_pico['demanda_total_sem_controle_kw']:.1f} kW as {linha_pico['horario']}")
    print(f" Demanda contratada ......... {config.DEMANDA_CONTRATADA_KW} kW")
    print(f" Intervalos acima do limite . {passos_acima} de {config.PASSOS_POR_DIA}")
    print("=" * 58)


if __name__ == "__main__":
    tabela, sessoes, recusados = simular_dia()
    salvar_simulacao(tabela, sessoes)
    mostrar_resumo(tabela, sessoes, recusados)
    print(" Arquivos salvos na pasta 'dados'")
import os

import pandas as pd

import config
from simulador import HORAS_POR_PASSO


def calcular_multa(pico_kw):
    limite_tolerancia = config.DEMANDA_CONTRATADA_KW * (1 + config.TOLERANCIA_ULTRAPASSAGEM)
    if pico_kw <= limite_tolerancia:
        return 0.0
    excesso = pico_kw - config.DEMANDA_CONTRATADA_KW
    return excesso * config.TARIFA_DEMANDA_KW * 2


def calcular_cenario(rede_kw, tarifas):
    energia_rede = rede_kw.sum() * HORAS_POR_PASSO
    custo_energia_dia = (rede_kw * tarifas).sum() * HORAS_POR_PASSO
    pico = rede_kw.max()
    multa = calcular_multa(pico)
    custo_demanda = config.DEMANDA_CONTRATADA_KW * config.TARIFA_DEMANDA_KW
    custo_mes = custo_energia_dia * config.DIAS_UTEIS_MES + custo_demanda + multa

    return {
        "energia_rede_kwh": energia_rede,
        "custo_energia_dia": custo_energia_dia,
        "pico_kw": pico,
        "intervalos_acima": int((rede_kw > config.DEMANDA_CONTRATADA_KW).sum()),
        "multa_mes": multa,
        "custo_mes": custo_mes,
        "co2_dia_kg": energia_rede * config.FATOR_CO2_KG_KWH,
    }


def analisar(tabela, otimizado, sessoes):
    sem = calcular_cenario(tabela["demanda_total_sem_controle_kw"], tabela["tarifa_kwh"])
    com = calcular_cenario(otimizado["rede_kw"], otimizado["tarifa_kwh"])

    ponta_sem = tabela.loc[tabela["ponta"], "demanda_total_sem_controle_kw"].sum() * HORAS_POR_PASSO
    ponta_com = otimizado.loc[otimizado["ponta"], "rede_kw"].sum() * HORAS_POR_PASSO

    consumo_total = (otimizado["carga_predio_kw"].sum() + otimizado["demanda_ev_kw"].sum()) * HORAS_POR_PASSO
    solar_gerado = otimizado["solar_kw"].sum() * HORAS_POR_PASSO
    solar_usado = (otimizado["solar_usado_kw"].sum() + otimizado["bateria_carga_solar_kw"].sum()) * HORAS_POR_PASSO
    renovavel = otimizado["renovavel_kw"].sum() * HORAS_POR_PASSO
    energia_bateria = otimizado["bateria_descarga_kw"].sum() * HORAS_POR_PASSO

    economia_mes = sem["custo_mes"] - com["custo_mes"]
    co2_evitado_dia = sem["co2_dia_kg"] - com["co2_dia_kg"]

    resumo = {
        "veiculos_atendidos": len(sessoes),
        "energia_ev_sem_kwh": sessoes["energia_entregue_sem_controle_kwh"].sum(),
        "energia_ev_com_kwh": sessoes["energia_entregue_com_chargegrid_kwh"].sum(),
        "pico_sem_kw": sem["pico_kw"],
        "pico_com_kw": com["pico_kw"],
        "reducao_pico_pct": (sem["pico_kw"] - com["pico_kw"]) / sem["pico_kw"] * 100,
        "intervalos_acima_sem": sem["intervalos_acima"],
        "intervalos_acima_com": com["intervalos_acima"],
        "energia_rede_sem_kwh": sem["energia_rede_kwh"],
        "energia_rede_com_kwh": com["energia_rede_kwh"],
        "energia_ponta_sem_kwh": ponta_sem,
        "energia_ponta_com_kwh": ponta_com,
        "custo_dia_sem": sem["custo_energia_dia"],
        "custo_dia_com": com["custo_energia_dia"],
        "multa_mes_sem": sem["multa_mes"],
        "multa_mes_com": com["multa_mes"],
        "custo_mes_sem": sem["custo_mes"],
        "custo_mes_com": com["custo_mes"],
        "economia_mes": economia_mes,
        "economia_pct": economia_mes / sem["custo_mes"] * 100,
        "economia_ano": economia_mes * 12,
        "solar_gerado_kwh": solar_gerado,
        "solar_aproveitado_pct": solar_usado / solar_gerado * 100 if solar_gerado > 0 else 0,
        "energia_bateria_kwh": energia_bateria,
        "renovavel_pct": renovavel / consumo_total * 100,
        "co2_sem_dia_kg": sem["co2_dia_kg"],
        "co2_com_dia_kg": com["co2_dia_kg"],
        "co2_evitado_dia_kg": co2_evitado_dia,
        "co2_evitado_ano_kg": co2_evitado_dia * config.DIAS_UTEIS_MES * 12,
    }

    return resumo


def montar_tabela_resultados(resumo):
    linhas = [
        ("Pico de demanda", resumo["pico_sem_kw"], resumo["pico_com_kw"], "kW"),
        ("Intervalos acima do contratado", resumo["intervalos_acima_sem"], resumo["intervalos_acima_com"], "de 96"),
        ("Energia comprada da rede (dia)", resumo["energia_rede_sem_kwh"], resumo["energia_rede_com_kwh"], "kWh"),
        ("Energia da rede no horario de ponta", resumo["energia_ponta_sem_kwh"], resumo["energia_ponta_com_kwh"], "kWh"),
        ("Energia entregue aos veiculos", resumo["energia_ev_sem_kwh"], resumo["energia_ev_com_kwh"], "kWh"),
        ("Custo de energia (dia)", resumo["custo_dia_sem"], resumo["custo_dia_com"], "R$"),
        ("Multa de ultrapassagem (mes)", resumo["multa_mes_sem"], resumo["multa_mes_com"], "R$"),
        ("Custo total estimado (mes)", resumo["custo_mes_sem"], resumo["custo_mes_com"], "R$"),
        ("Emissao de CO2 (dia)", resumo["co2_sem_dia_kg"], resumo["co2_com_dia_kg"], "kg"),
    ]

    tabela = pd.DataFrame(linhas, columns=["indicador", "sem_chargegrid", "com_chargegrid", "unidade"])
    tabela["sem_chargegrid"] = tabela["sem_chargegrid"].astype(float).round(2)
    tabela["com_chargegrid"] = tabela["com_chargegrid"].astype(float).round(2)
    return tabela


def salvar_resultados(tabela_resultados):
    os.makedirs(config.PASTA_DADOS, exist_ok=True)
    tabela_resultados.to_csv(config.ARQUIVO_RESULTADOS, index=False)


def mostrar_resultados(resumo):
    print("=" * 58)
    print(" ChargeGrid Intelligence - Resultados do dia")
    print("=" * 58)
    print(f"{'':32}{'SEM':>12}{'COM':>12}")
    print(f" {'Pico de demanda (kW)':31}{resumo['pico_sem_kw']:>12.1f}{resumo['pico_com_kw']:>12.1f}")
    print(f" {'Intervalos acima de 80 kW':31}{resumo['intervalos_acima_sem']:>12}{resumo['intervalos_acima_com']:>12}")
    print(f" {'Rede no horario de ponta (kWh)':31}{resumo['energia_ponta_sem_kwh']:>12.1f}{resumo['energia_ponta_com_kwh']:>12.1f}")
    print(f" {'Energia da rede no dia (kWh)':31}{resumo['energia_rede_sem_kwh']:>12.1f}{resumo['energia_rede_com_kwh']:>12.1f}")
    print(f" {'Multa no mes (R$)':31}{resumo['multa_mes_sem']:>12.2f}{resumo['multa_mes_com']:>12.2f}")
    print(f" {'Custo total no mes (R$)':31}{resumo['custo_mes_sem']:>12.2f}{resumo['custo_mes_com']:>12.2f}")
    print("-" * 58)
    print(f" Economia mensal ........... R$ {resumo['economia_mes']:.2f} ({resumo['economia_pct']:.1f}%)")
    print(f" Economia anual estimada ... R$ {resumo['economia_ano']:.2f}")
    print(f" Reducao do pico ........... {resumo['reducao_pico_pct']:.1f}%")
    print(f" Solar aproveitado ......... {resumo['solar_aproveitado_pct']:.1f}%")
    print(f" Consumo vindo do sol ...... {resumo['renovavel_pct']:.1f}%")
    print(f" CO2 evitado por ano ....... {resumo['co2_evitado_ano_kg']:.0f} kg")
    print("=" * 58)


if __name__ == "__main__":
    from simulador import simular_dia
    from otimizador import otimizar_dia

    tabela, sessoes, recusados = simular_dia()
    otimizado, sessoes, alertas = otimizar_dia(tabela, sessoes)
    resumo = analisar(tabela, otimizado, sessoes)
    salvar_resultados(montar_tabela_resultados(resumo))
    mostrar_resultados(resumo)
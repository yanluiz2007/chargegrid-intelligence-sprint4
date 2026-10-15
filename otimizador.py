import os

import pandas as pd

import config
from simulador import HORAS_POR_PASSO


LIMITE_REDE_KW = config.DEMANDA_CONTRATADA_KW * config.LIMITE_PEAK_SHAVING


class Bateria:

    def __init__(self):
        self.capacidade = config.BATERIA_CAPACIDADE_KWH
        self.energia = self.capacidade * config.BATERIA_SOC_INICIAL
        self.energia_solar = 0.0

    def soc(self):
        return self.energia / self.capacidade

    def fracao_solar(self):
        if self.energia <= 0:
            return 0.0
        return self.energia_solar / self.energia

    def descarregar(self, potencia_pedida):
        disponivel = self.energia - self.capacidade * config.BATERIA_SOC_MIN
        if disponivel <= 0 or potencia_pedida <= 0:
            return 0.0

        potencia_maxima = min(config.BATERIA_POTENCIA_KW,
                              disponivel * config.BATERIA_EFICIENCIA / HORAS_POR_PASSO)
        potencia = min(potencia_pedida, potencia_maxima)

        energia_retirada = potencia * HORAS_POR_PASSO / config.BATERIA_EFICIENCIA
        self.energia_solar -= energia_retirada * self.fracao_solar()
        self.energia -= energia_retirada
        return potencia

    def potencia_disponivel(self):
        disponivel = self.energia - self.capacidade * config.BATERIA_SOC_MIN
        return max(0.0, disponivel * config.BATERIA_EFICIENCIA / HORAS_POR_PASSO)

    def carregar(self, potencia_oferecida, veio_do_sol, soc_limite=config.BATERIA_SOC_MAX, ja_usado_kw=0.0):
        espaco = self.capacidade * soc_limite - self.energia
        if espaco <= 0 or potencia_oferecida <= 0:
            return 0.0

        potencia_maxima = min(config.BATERIA_POTENCIA_KW - ja_usado_kw,
                              espaco / (config.BATERIA_EFICIENCIA * HORAS_POR_PASSO))
        if potencia_maxima <= 0:
            return 0.0
        potencia = min(potencia_oferecida, potencia_maxima)

        energia_guardada = potencia * HORAS_POR_PASSO * config.BATERIA_EFICIENCIA
        self.energia += energia_guardada
        if veio_do_sol:
            self.energia_solar += energia_guardada
        return potencia


def calcular_urgencia(carro, passo):
    horas_restantes = max((carro["passo_saida"] - passo) * HORAS_POR_PASSO, HORAS_POR_PASSO)
    return carro["falta_kwh"] / horas_restantes


def distribuir_potencia(carros, potencia_total, passo):
    carros_ordenados = sorted(carros, key=lambda c: calcular_urgencia(c, passo), reverse=True)
    sobra = potencia_total

    for carro in carros_ordenados:
        potencia = min(carro["pedido_kw"], sobra)
        carro["falta_kwh"] -= potencia * HORAS_POR_PASSO
        carro["entregue_kwh"] += potencia * HORAS_POR_PASSO
        sobra -= potencia


def otimizar_dia(tabela, sessoes):
    bateria = Bateria()
    carros = sessoes.to_dict("records")

    for carro in carros:
        carro["falta_kwh"] = carro["energia_pedida_kwh"]
        carro["entregue_kwh"] = 0.0

    linhas = []
    alertas = []
    peak_shaving_antes = False
    avisou_bateria_baixa = False

    for _, linha in tabela.iterrows():
        passo = int(linha["passo"])
        hora = linha["hora"]
        horario = linha["horario"]
        ponta = bool(linha["ponta"])
        solar = linha["solar_kw"]
        predio = linha["carga_predio_kw"]

        if ponta and passo > 0 and not tabela.loc[passo - 1, "ponta"]:
            alertas.append(f"{horario} - Inicio do horario de ponta: bateria passa a abastecer o estacionamento")

        presentes = [c for c in carros
                     if c["passo_chegada"] <= passo < c["passo_saida"] and c["falta_kwh"] > 0.001]

        for carro in presentes:
            carro["pedido_kw"] = min(carro["potencia_kw"], carro["falta_kwh"] / HORAS_POR_PASSO)

        ev_desejada = sum(c["pedido_kw"] for c in presentes)
        consumo = predio + ev_desejada

        solar_usado = min(solar, consumo)
        sobra_solar = solar - solar_usado
        falta = consumo - solar_usado

        carga_solar = bateria.carregar(sobra_solar, veio_do_sol=True)
        excedente = sobra_solar - carga_solar

        fracao_solar = bateria.fracao_solar()
        descarga = 0.0
        if falta > 0:
            necessario_limite = max(0.0, falta - LIMITE_REDE_KW)

            if ponta:
                passos_ponta_restantes = int(tabela.loc[passo:, "ponta"].sum())
                cota = bateria.potencia_disponivel() / max(passos_ponta_restantes, 1)
                descarga = bateria.descarregar(max(min(falta, cota), necessario_limite))
            else:
                descarga = bateria.descarregar(necessario_limite)

        rede = falta - descarga

        corte = 0.0
        if rede > LIMITE_REDE_KW:
            corte = min(rede - LIMITE_REDE_KW, ev_desejada)
            rede -= corte

        ev_entregue = ev_desejada - corte
        distribuir_potencia(presentes, ev_entregue, passo)

        alvo = None
        if hora < config.INICIO_SOL:
            alvo = config.BATERIA_SOC_ALVO_MADRUGADA
        elif config.INICIO_PREPARO_PONTA <= hora < config.INICIO_PONTA:
            alvo = config.BATERIA_SOC_ALVO_PONTA

        carga_rede = 0.0
        if alvo is not None and not ponta and descarga == 0 and bateria.soc() < alvo:
            folga = LIMITE_REDE_KW - rede
            carga_rede = bateria.carregar(folga, veio_do_sol=False,
                                          soc_limite=alvo, ja_usado_kw=carga_solar)
            rede += carga_rede

        peak_shaving_agora = corte > 0
        if peak_shaving_agora and not peak_shaving_antes:
            alertas.append(f"{horario} - Peak shaving ativado: recarga reduzida em {corte:.1f} kW para segurar a demanda")
        if not peak_shaving_agora and peak_shaving_antes:
            alertas.append(f"{horario} - Peak shaving desligado: carregadores voltaram a potencia normal")
        peak_shaving_antes = peak_shaving_agora

        if bateria.soc() <= config.BATERIA_SOC_MIN + 0.01 and not avisou_bateria_baixa:
            alertas.append(f"{horario} - Bateria chegou ao nivel minimo de {config.BATERIA_SOC_MIN * 100:.0f}%")
            avisou_bateria_baixa = True
        if bateria.soc() > 0.30:
            avisou_bateria_baixa = False

        if rede > config.DEMANDA_CONTRATADA_KW:
            alertas.append(f"{horario} - ATENCAO: demanda da rede em {rede:.1f} kW, acima do contratado")

        linhas.append({
            "passo": passo,
            "horario": horario,
            "hora": hora,
            "ponta": ponta,
            "tarifa_kwh": linha["tarifa_kwh"],
            "solar_kw": solar,
            "solar_usado_kw": round(solar_usado, 2),
            "excedente_solar_kw": round(excedente, 2),
            "carga_predio_kw": predio,
            "demanda_ev_desejada_kw": round(ev_desejada, 2),
            "demanda_ev_kw": round(ev_entregue, 2),
            "corte_peak_shaving_kw": round(corte, 2),
            "bateria_carga_solar_kw": round(carga_solar, 2),
            "bateria_carga_rede_kw": round(carga_rede, 2),
            "bateria_descarga_kw": round(descarga, 2),
            "soc_bateria": round(bateria.soc() * 100, 1),
            "rede_kw": round(rede, 2),
            "renovavel_kw": round(solar_usado + descarga * fracao_solar, 2),
            "carros_carregando": len(presentes),
        })

    otimizado = pd.DataFrame(linhas)

    sessoes = sessoes.copy()
    entregue = {c["veiculo"]: round(c["entregue_kwh"], 2) for c in carros}
    sessoes["energia_entregue_com_chargegrid_kwh"] = sessoes["veiculo"].map(entregue)
    sessoes["atendimento_pct"] = (sessoes["energia_entregue_com_chargegrid_kwh"]
                                  / sessoes["energia_pedida_kwh"] * 100).round(1)

    return otimizado, sessoes, alertas


def salvar_otimizacao(otimizado, sessoes):
    os.makedirs(config.PASTA_DADOS, exist_ok=True)
    otimizado.to_csv(config.ARQUIVO_OTIMIZADO, index=False)
    sessoes.to_csv(config.ARQUIVO_SESSOES, index=False)


if __name__ == "__main__":
    from simulador import simular_dia

    tabela, sessoes, recusados = simular_dia()
    otimizado, sessoes, alertas = otimizar_dia(tabela, sessoes)
    salvar_otimizacao(otimizado, sessoes)

    print("=" * 58)
    print(" ChargeGrid Intelligence - Otimizador")
    print("=" * 58)
    print(f" Limite usado no peak shaving: {LIMITE_REDE_KW:.0f} kW")
    print(f" Pico da rede sem ChargeGrid : {tabela['demanda_total_sem_controle_kw'].max():.1f} kW")
    print(f" Pico da rede com ChargeGrid : {otimizado['rede_kw'].max():.1f} kW")
    print()
    print(" Eventos do dia:")
    for alerta in alertas:
        print(f"  {alerta}")
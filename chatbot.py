import os

import config


def montar_contexto(resumo, alertas):
    texto = f"""
Dados do dia simulado no estacionamento L1 da FIAP com o ChargeGrid Intelligence:
- Veiculos atendidos: {resumo['veiculos_atendidos']}
- Energia entregue aos carros: {resumo['energia_ev_com_kwh']:.1f} kWh
- Pico de demanda sem o sistema: {resumo['pico_sem_kw']:.1f} kW
- Pico de demanda com o sistema: {resumo['pico_com_kw']:.1f} kW (contratado: {config.DEMANDA_CONTRATADA_KW} kW)
- Reducao do pico: {resumo['reducao_pico_pct']:.1f}%
- Custo mensal sem o sistema: R$ {resumo['custo_mes_sem']:.2f}
- Custo mensal com o sistema: R$ {resumo['custo_mes_com']:.2f}
- Economia mensal: R$ {resumo['economia_mes']:.2f} ({resumo['economia_pct']:.1f}%)
- Multa evitada por mes: R$ {resumo['multa_mes_sem']:.2f}
- Geracao solar: {resumo['solar_gerado_kwh']:.1f} kWh, aproveitamento de {resumo['solar_aproveitado_pct']:.1f}%
- Consumo atendido pelo sol: {resumo['renovavel_pct']:.1f}%
- Energia fornecida pela bateria: {resumo['energia_bateria_kwh']:.1f} kWh
- CO2 evitado: {resumo['co2_evitado_dia_kg']:.1f} kg por dia e {resumo['co2_evitado_ano_kg']:.0f} kg por ano
- Horario de ponta: 17h30 as 20h30
Eventos do dia:
"""
    for alerta in alertas:
        texto += f"- {alerta}\n"
    return texto


def resposta_offline(pergunta, resumo):
    pergunta = pergunta.lower()

    if "econom" in pergunta or "custo" in pergunta or "dinheiro" in pergunta or "conta" in pergunta:
        return (f"Com o ChargeGrid o custo mensal cai de R$ {resumo['custo_mes_sem']:.2f} para "
                f"R$ {resumo['custo_mes_com']:.2f}, uma economia de R$ {resumo['economia_mes']:.2f} "
                f"({resumo['economia_pct']:.1f}%).")

    if "multa" in pergunta or "pico" in pergunta or "demanda" in pergunta:
        return (f"Sem controle o pico chegou a {resumo['pico_sem_kw']:.1f} kW e gerou multa de "
                f"R$ {resumo['multa_mes_sem']:.2f}. Com o peak shaving o pico ficou em "
                f"{resumo['pico_com_kw']:.1f} kW e a multa foi zerada.")

    if "bateria" in pergunta:
        return (f"A bateria entregou {resumo['energia_bateria_kwh']:.1f} kWh no dia, principalmente "
                f"no horario de ponta (17h30 as 20h30), quando a energia da rede e mais cara.")

    if "solar" in pergunta or "sol" in pergunta:
        return (f"Os paineis geraram {resumo['solar_gerado_kwh']:.1f} kWh e o sistema aproveitou "
                f"{resumo['solar_aproveitado_pct']:.1f}% disso. O sol atendeu {resumo['renovavel_pct']:.1f}% do consumo.")

    if "co2" in pergunta or "carbono" in pergunta or "ambiente" in pergunta or "sustent" in pergunta:
        return (f"O sistema evita {resumo['co2_evitado_dia_kg']:.1f} kg de CO2 por dia, "
                f"cerca de {resumo['co2_evitado_ano_kg']:.0f} kg por ano.")

    if "carro" in pergunta or "veiculo" in pergunta or "veículo" in pergunta or "recarga" in pergunta:
        return (f"Foram atendidos {resumo['veiculos_atendidos']} veiculos, que receberam "
                f"{resumo['energia_ev_com_kwh']:.1f} kWh no total.")

    return ("Posso responder sobre economia, pico de demanda, multa, bateria, energia solar, "
            "CO2 ou os carros atendidos. Tente perguntar sobre um desses assuntos.")


def responder(pergunta, resumo, alertas, historico=None):
    chave = os.environ.get("GROQ_API_KEY")

    if not chave:
        return resposta_offline(pergunta, resumo)

    try:
        from groq import Groq

        cliente = Groq(api_key=chave)
        mensagens = [{
            "role": "system",
            "content": (
                "Voce e o assistente virtual do ChargeGrid Intelligence, uma plataforma de gestao "
                "de energia para eletropostos com equipamentos GoodWe (carregador HCA G2, inversor "
                "hibrido e bateria). Responda sempre em portugues do Brasil, de forma curta e "
                "clara, usando apenas os dados abaixo. Se nao souber, diga que nao tem essa informacao.\n"
                + montar_contexto(resumo, alertas)
            ),
        }]

        if historico:
            mensagens.extend(historico)
        mensagens.append({"role": "user", "content": pergunta})

        resposta = cliente.chat.completions.create(
            model=config.MODELO_GROQ,
            messages=mensagens,
            temperature=0.3,
            max_tokens=400,
        )
        return resposta.choices[0].message.content

    except Exception as erro:
        print(f"Nao consegui falar com a Groq ({erro}). Usando modo offline.")
        return resposta_offline(pergunta, resumo)


if __name__ == "__main__":
    from simulador import simular_dia
    from otimizador import otimizar_dia
    from analise import analisar

    tabela, sessoes, recusados = simular_dia()
    otimizado, sessoes, alertas = otimizar_dia(tabela, sessoes)
    resumo = analisar(tabela, otimizado, sessoes)

    if os.environ.get("GROQ_API_KEY"):
        print("Assistente ChargeGrid (modo IA - Groq)")
    else:
        print("Assistente ChargeGrid (modo offline - sem GROQ_API_KEY)")
    print("Digite 'sair' para encerrar.\n")

    historico = []
    while True:
        pergunta = input("Voce: ").strip()
        if pergunta.lower() in ("sair", "exit", "tchau"):
            print("Assistente: Ate mais!")
            break
        if not pergunta:
            continue

        resposta = responder(pergunta, resumo, alertas, historico)
        historico.append({"role": "user", "content": pergunta})
        historico.append({"role": "assistant", "content": resposta})
        print(f"Assistente: {resposta}\n")
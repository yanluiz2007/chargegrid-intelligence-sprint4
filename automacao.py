import os
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config
from otimizador import LIMITE_REDE_KW


COR_SEM = "#eb6834"
COR_COM = "#2a78d6"
COR_SOLAR = "#eda100"
COR_BATERIA = "#1baf7a"
COR_REDE = "#2a78d6"
COR_TEXTO = "#52514e"
COR_PONTA = "#f3f0e8"


def preparar_eixo(ax, titulo, rotulo_y):
    ax.set_title(titulo, fontsize=13, loc="left", color="#0b0b0b")
    ax.set_ylabel(rotulo_y, color=COR_TEXTO)
    ax.set_xlabel("Hora do dia", color=COR_TEXTO)
    ax.set_xticks(range(0, 25, 2))
    ax.set_xlim(0, 24)
    ax.grid(axis="y", color="#e5e3dc", linewidth=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(colors=COR_TEXTO)
    ax.axvspan(config.INICIO_PONTA, config.FIM_PONTA, color=COR_PONTA, zorder=0, label="Horario de ponta")


def grafico_demanda(tabela, otimizado):
    fig, ax = plt.subplots(figsize=(11, 5))
    preparar_eixo(ax, "Demanda puxada da rede: sem vs. com ChargeGrid", "kW")

    ax.plot(tabela["hora"], tabela["demanda_total_sem_controle_kw"], color=COR_SEM, linewidth=2, label="Sem ChargeGrid")
    ax.plot(otimizado["hora"], otimizado["rede_kw"], color=COR_COM, linewidth=2, label="Com ChargeGrid")
    ax.axhline(config.DEMANDA_CONTRATADA_KW, color="#e34948", linestyle="--", linewidth=1.2,
               label=f"Demanda contratada ({config.DEMANDA_CONTRATADA_KW} kW)")
    ax.axhline(LIMITE_REDE_KW, color=COR_TEXTO, linestyle=":", linewidth=1.2,
               label=f"Gatilho do peak shaving ({LIMITE_REDE_KW:.0f} kW)")

    ax.legend(loc="upper left", frameon=False, fontsize=9)
    caminho = os.path.join(config.PASTA_GRAFICOS, "01_demanda_comparativa.png")
    fig.tight_layout()
    fig.savefig(caminho, dpi=120)
    plt.close(fig)
    return caminho


def grafico_fontes(otimizado):
    fig, ax = plt.subplots(figsize=(11, 5))
    preparar_eixo(ax, "De onde veio a energia com o ChargeGrid", "kW")

    ax.stackplot(
        otimizado["hora"],
        otimizado["solar_usado_kw"],
        otimizado["bateria_descarga_kw"],
        otimizado["rede_kw"],
        colors=[COR_SOLAR, COR_BATERIA, COR_REDE],
        labels=["Solar (inversor GoodWe)", "Bateria GoodWe", "Rede eletrica (inclui recarga da bateria)"],
        edgecolor="white",
        linewidth=0.5,
    )

    ax.legend(loc="upper left", frameon=False, fontsize=9)
    caminho = os.path.join(config.PASTA_GRAFICOS, "02_fontes_de_energia.png")
    fig.tight_layout()
    fig.savefig(caminho, dpi=120)
    plt.close(fig)
    return caminho


def grafico_bateria(otimizado):
    fig, ax = plt.subplots(figsize=(11, 4))
    preparar_eixo(ax, "Nivel de carga da bateria (SOC)", "%")

    ax.plot(otimizado["hora"], otimizado["soc_bateria"], color=COR_BATERIA, linewidth=2, label="SOC da bateria")
    ax.axhline(config.BATERIA_SOC_MIN * 100, color=COR_TEXTO, linestyle=":", linewidth=1.2, label="Nivel minimo")
    ax.set_ylim(0, 105)

    ax.legend(loc="upper left", frameon=False, fontsize=9)
    caminho = os.path.join(config.PASTA_GRAFICOS, "03_bateria_soc.png")
    fig.tight_layout()
    fig.savefig(caminho, dpi=120)
    plt.close(fig)
    return caminho


def grafico_custos(resumo):
    fig, ax = plt.subplots(figsize=(7, 5))

    nomes = ["Sem ChargeGrid", "Com ChargeGrid"]
    valores = [resumo["custo_mes_sem"], resumo["custo_mes_com"]]
    barras = ax.bar(nomes, valores, color=[COR_SEM, COR_COM], width=0.5)

    for barra, valor in zip(barras, valores):
        ax.text(barra.get_x() + barra.get_width() / 2, valor + 300, f"R$ {valor:,.0f}".replace(",", "."),
                ha="center", color="#0b0b0b", fontsize=11)

    ax.set_title(f"Custo mensal estimado (economia de {resumo['economia_pct']:.1f}%)", fontsize=13, loc="left")
    ax.set_ylabel("R$", color=COR_TEXTO)
    ax.set_ylim(0, max(valores) * 1.15)
    ax.grid(axis="y", color="#e5e3dc", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    caminho = os.path.join(config.PASTA_GRAFICOS, "04_custo_mensal.png")
    fig.tight_layout()
    fig.savefig(caminho, dpi=120)
    plt.close(fig)
    return caminho


def gerar_graficos(tabela, otimizado, resumo):
    os.makedirs(config.PASTA_GRAFICOS, exist_ok=True)
    return [
        grafico_demanda(tabela, otimizado),
        grafico_fontes(otimizado),
        grafico_bateria(otimizado),
        grafico_custos(resumo),
    ]


def dinheiro(valor):
    texto = f"{valor:,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_relatorio(resumo, alertas, tabela_resultados):
    os.makedirs(config.PASTA_RELATORIOS, exist_ok=True)
    agora = datetime.now()
    caminho = os.path.join(config.PASTA_RELATORIOS, "relatorio_diario.md")

    linhas = []
    linhas.append("# Relatorio diario - ChargeGrid Intelligence")
    linhas.append("")
    linhas.append(f"Gerado automaticamente em {agora.strftime('%d/%m/%Y %H:%M')}")
    linhas.append("")
    linhas.append("## Resumo")
    linhas.append("")
    linhas.append(f"- Veiculos atendidos: {resumo['veiculos_atendidos']}")
    linhas.append(f"- Pico de demanda: {resumo['pico_sem_kw']:.1f} kW sem o sistema e {resumo['pico_com_kw']:.1f} kW com o sistema")
    linhas.append(f"- Economia mensal estimada: {dinheiro(resumo['economia_mes'])} ({resumo['economia_pct']:.1f}%)")
    linhas.append(f"- Multa de ultrapassagem evitada: {dinheiro(resumo['multa_mes_sem'])} por mes")
    linhas.append(f"- Energia solar aproveitada: {resumo['solar_aproveitado_pct']:.1f}% do que foi gerado")
    linhas.append(f"- CO2 evitado: {resumo['co2_evitado_dia_kg']:.1f} kg no dia, {resumo['co2_evitado_ano_kg']:.0f} kg por ano")
    linhas.append("")
    linhas.append("## Comparativo")
    linhas.append("")
    linhas.append("| Indicador | Sem ChargeGrid | Com ChargeGrid | Unidade |")
    linhas.append("|---|---|---|---|")
    for _, linha in tabela_resultados.iterrows():
        linhas.append(f"| {linha['indicador']} | {linha['sem_chargegrid']:.2f} | {linha['com_chargegrid']:.2f} | {linha['unidade']} |")
    linhas.append("")
    linhas.append("## Eventos e alertas do dia")
    linhas.append("")
    if alertas:
        for alerta in alertas:
            linhas.append(f"- {alerta}")
    else:
        linhas.append("- Nenhum evento registrado")
    linhas.append("")

    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write("\n".join(linhas))

    return caminho


if __name__ == "__main__":
    from simulador import simular_dia
    from otimizador import otimizar_dia
    from analise import analisar, montar_tabela_resultados

    tabela, sessoes, recusados = simular_dia()
    otimizado, sessoes, alertas = otimizar_dia(tabela, sessoes)
    resumo = analisar(tabela, otimizado, sessoes)

    graficos = gerar_graficos(tabela, otimizado, resumo)
    relatorio = gerar_relatorio(resumo, alertas, montar_tabela_resultados(resumo))

    print("Graficos gerados:")
    for caminho in graficos:
        print(f"  {os.path.basename(caminho)}")
    print(f"Relatorio gerado: {os.path.basename(relatorio)}")
import os

import pandas as pd
import streamlit as st

import config
from simulador import simular_dia
from otimizador import otimizar_dia
from analise import analisar, montar_tabela_resultados
from chatbot import responder


st.set_page_config(page_title="ChargeGrid Intelligence", page_icon="⚡", layout="wide")


@st.cache_data
def carregar_dados():
    tabela, sessoes, recusados = simular_dia()
    otimizado, sessoes, alertas = otimizar_dia(tabela, sessoes)
    resumo = analisar(tabela, otimizado, sessoes)
    return tabela, otimizado, sessoes, alertas, resumo


def reais(valor):
    texto = f"{valor:,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


tabela, otimizado, sessoes, alertas, resumo = carregar_dados()

st.title("⚡ ChargeGrid Intelligence")
st.caption("Grupo 5 · Turma 1CCPY · FIAP 2026 · EV Challenge GoodWe — Sprint 4")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Pico de demanda", f"{resumo['pico_com_kw']:.1f} kW",
            f"{-resumo['reducao_pico_pct']:.1f}% vs. sem sistema", delta_color="inverse")
col2.metric("Economia por mês", reais(resumo["economia_mes"]), f"{resumo['economia_pct']:.1f}%")
col3.metric("Consumo vindo do sol", f"{resumo['renovavel_pct']:.1f}%")
col4.metric("CO₂ evitado por ano", f"{resumo['co2_evitado_ano_kg']:.0f} kg")

aba_demanda, aba_fontes, aba_bateria, aba_carros, aba_resultados, aba_assistente = st.tabs(
    ["Demanda", "Fontes de energia", "Bateria", "Veículos", "Resultados", "Assistente virtual"]
)

with aba_demanda:
    st.subheader("Demanda puxada da rede")
    st.write(f"Demanda contratada: **{config.DEMANDA_CONTRATADA_KW} kW** · "
             f"Peak shaving a partir de **{config.DEMANDA_CONTRATADA_KW * config.LIMITE_PEAK_SHAVING:.0f} kW** · "
             f"Ponta: **17h30 às 20h30**")

    grafico = pd.DataFrame({
        "Sem ChargeGrid": tabela["demanda_total_sem_controle_kw"].values,
        "Com ChargeGrid": otimizado["rede_kw"].values,
        "Contratado": [config.DEMANDA_CONTRATADA_KW] * len(otimizado),
    }, index=otimizado["horario"])
    st.line_chart(grafico, y_label="kW", x_label="Horário")

    if resumo["multa_mes_sem"] > 0:
        st.warning(f"Sem o sistema a demanda passa do contratado em {resumo['intervalos_acima_sem']} "
                   f"intervalos e gera multa de {reais(resumo['multa_mes_sem'])} por mês.")
    if resumo["intervalos_acima_com"] == 0:
        st.success("Com o ChargeGrid a demanda não passou do contratado em nenhum momento do dia.")

with aba_fontes:
    st.subheader("De onde veio a energia")
    fontes = pd.DataFrame({
        "Solar": otimizado["solar_usado_kw"].values,
        "Bateria": otimizado["bateria_descarga_kw"].values,
        "Rede": otimizado["rede_kw"].values,
    }, index=otimizado["horario"])
    st.area_chart(fontes, y_label="kW", x_label="Horário")
    st.write(f"Geração solar no dia: **{resumo['solar_gerado_kwh']:.1f} kWh** · "
             f"Aproveitamento: **{resumo['solar_aproveitado_pct']:.1f}%**")

with aba_bateria:
    st.subheader("Nível de carga da bateria (SOC)")
    soc = pd.DataFrame({"SOC (%)": otimizado["soc_bateria"].values}, index=otimizado["horario"])
    st.line_chart(soc, y_label="%", x_label="Horário")
    st.write(f"A bateria entregou **{resumo['energia_bateria_kwh']:.1f} kWh** no dia, "
             f"a maior parte no horário de ponta.")

with aba_carros:
    st.subheader("Sessões de recarga")
    tabela_carros = sessoes.copy()
    tabela_carros["chegada"] = tabela_carros["passo_chegada"].apply(lambda p: tabela.loc[p, "horario"])
    tabela_carros["saida"] = tabela_carros["passo_saida"].apply(
        lambda p: tabela.loc[p, "horario"] if p < len(tabela) else "24:00")
    st.dataframe(
        tabela_carros[["veiculo", "vaga", "tipo_recarga", "potencia_kw", "chegada", "saida",
                       "energia_pedida_kwh", "energia_entregue_com_chargegrid_kwh", "atendimento_pct"]],
        hide_index=True,
        width="stretch",
    )

    st.subheader("Eventos do dia")
    for alerta in alertas:
        st.write(f"• {alerta}")

with aba_resultados:
    st.subheader("Comparativo sem vs. com ChargeGrid")
    st.dataframe(montar_tabela_resultados(resumo), hide_index=True, width="stretch")

with aba_assistente:
    st.subheader("Assistente virtual ChargeGrid")
    if not os.environ.get("GROQ_API_KEY"):
        st.info("Rodando em modo offline. Para usar a IA da Groq, defina a variável GROQ_API_KEY.")

    if "historico" not in st.session_state:
        st.session_state.historico = []

    with st.form("form_chat", clear_on_submit=True):
        pergunta = st.text_input("Pergunte sobre economia, pico, bateria, solar ou CO₂")
        enviar = st.form_submit_button("Enviar")

    if enviar and pergunta.strip():
        resposta = responder(pergunta, resumo, alertas, st.session_state.historico)
        st.session_state.historico.append({"role": "user", "content": pergunta})
        st.session_state.historico.append({"role": "assistant", "content": resposta})

    for mensagem in st.session_state.historico:
        quem = "Você" if mensagem["role"] == "user" else "Assistente"
        texto = mensagem["content"].replace("$", "\\$")
        st.markdown(f"**{quem}:** {texto}")
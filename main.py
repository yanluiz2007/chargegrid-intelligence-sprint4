from simulador import simular_dia, salvar_simulacao
from otimizador import otimizar_dia, salvar_otimizacao
from analise import analisar, montar_tabela_resultados, salvar_resultados, mostrar_resultados
from automacao import gerar_graficos, gerar_relatorio


def executar():
    print("\n[1/4] Simulando o dia no estacionamento...")
    tabela, sessoes, recusados = simular_dia()
    salvar_simulacao(tabela, sessoes)

    print("[2/4] Aplicando o algoritmo do ChargeGrid...")
    otimizado, sessoes, alertas = otimizar_dia(tabela, sessoes)
    salvar_otimizacao(otimizado, sessoes)

    print("[3/4] Comparando os cenarios sem e com o sistema...")
    resumo = analisar(tabela, otimizado, sessoes)
    tabela_resultados = montar_tabela_resultados(resumo)
    salvar_resultados(tabela_resultados)

    print("[4/4] Gerando graficos e relatorio automatico...\n")
    gerar_graficos(tabela, otimizado, resumo)
    gerar_relatorio(resumo, alertas, tabela_resultados)

    mostrar_resultados(resumo)

    print("\n Eventos do dia:")
    for alerta in alertas:
        print(f"  {alerta}")

    print("\n Arquivos gerados nas pastas: dados, graficos e relatorios")
    print(" Para abrir o dashboard: streamlit run dashboard.py\n")


if __name__ == "__main__":
    executar()
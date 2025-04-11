import streamlit as st
import pandas as pd
import altair as alt
import matplotlib
from datetime import datetime


from rpy2.robjects import r
from rpy2.robjects.conversion import localconverter, rpy2py
from rpy2.robjects import default_converter, pandas2ri

pandas2ri.activate()

# ------------------------------
# Carregar dados do R
# ------------------------------
@st.cache_data(show_spinner=True)
def carregar_dados_emendas():
    r('library(orcamentoBR)')
    r('dados_total <- data.frame()')

    for ano in [2022, 2023, 2024, 2025]:
        r(f'''
            dados <- despesaDetalhada(
                exercicio = {ano},
                detalheMaximo = FALSE,
                Funcao = TRUE,
                Acao = TRUE,
                ModalidadeAplicacao = TRUE,
                ResultadoPrimario = TRUE,
                incluiDescricoes = TRUE
            )
            dados_emendas <- subset(dados, ResultadoPrimario_cod %in% c("6", "7", "8"))
            dados_emendas$Ano <- {ano}
            dados_total <- rbind(dados_total, dados_emendas)
        ''')

    with localconverter(default_converter + pandas2ri.converter):
        df = rpy2py(r['dados_total'])

    return df

# ------------------------------
# Transformações de variáveis
# ------------------------------
def aplicar_transformacoes(df):
    # tipo_emenda
    df["tipo_emenda"] = df.apply(
        lambda row: (
            "Bancada" if row["ResultadoPrimario_cod"] == "7" else
            "Comissão" if row["ResultadoPrimario_cod"] == "8" else
            "Individual - transferência especial (Pix)" if row["ResultadoPrimario_cod"] == "6" and row["Acao_cod"] == "0EC2" else
            "Individual - finalidade definida" if row["ResultadoPrimario_cod"] == "6" else
            None
        ),
        axis=1
    )

    # Reclassificar ModalidadeAplicacao_desc
    modalidades_outras = [
        "Aplicação Direta Decorrente de Operação entre Órgãos, Fundos e Entidades Integrantes dos Orçamentos F/S",
        "Execução Orçamentária Delegada a Estados e ao Distrito Federal",
        "Execução Orçamentária Delegada a Municípios",
        "Transferências a Consórcios Públicos mediante contrato de rateio",
        "Transferências a Instituições Multigovernamentais Nacionais",
        "Transferências ao Exterior"
    ]

    mapa_modalidade = {
        "Transferências a Estados e ao Distrito Federal": "Transf. Estados e DF",
        "Transferências a Estados e ao Distrito Federal - Fundo a Fundo": "Transf. Estados e DF - F/F",
        "Transferências a Municípios": "Transf. a Municípios",
        "Transferências a Municípios - Fundo a Fundo": "Transf. a Municípios - F/F",
        "Transferências a Instituições Privadas sem Fins Lucrativos": "Transf. a Inst. Priv. s/ fins lucr",
        "A DEFINIR": "A definir"
    }

    df["ModalidadeAplicacao_desc"] = df["ModalidadeAplicacao_desc"].replace(mapa_modalidade)
    df["ModalidadeAplicacao_desc"] = df["ModalidadeAplicacao_desc"].apply(
        lambda x: "Outras" if x in modalidades_outras else x
    )

    return df

# ------------------------------
# Streamlit layout
# ------------------------------
st.set_page_config(page_title="Emendas Parlamentares - Visualização", layout="wide")
st.title("Emendas Parlamentares em grandes números (2022–2025)")

with st.spinner("Carregando dados..."):
    df = carregar_dados_emendas()

df = aplicar_transformacoes(df)
st.success("Dados carregados com sucesso!")

# ---------------------------
# 1) Evolução ResultadoPrimario_desc × Ano
# ---------------------------
st.header("1. Tipo de emenda parlamentar")

# Paleta de cores por tipo de emenda
cores_tipo_emenda = {
    "Bancada": "#1B5DA3",
    "Comissão": "#77B5E5",
    "Individual - finalidade definida": "#E6332A",
    "Individual - transferência especial (Pix)": "#FCA3A0"
}

ordem_facetas = [
    "Bancada",
    "Comissão",
    "Individual - finalidade definida",
    "Individual - transferência especial (Pix)"
]

df1 = (
    df.groupby(["Ano", "tipo_emenda"], as_index=False)
      .agg({"loa_mais_credito": "sum"})
)

df1["dotacao"] = df1["loa_mais_credito"].apply(
    lambda x: f'{x / 1e9:,.1f} bi'.replace(",", "X").replace(".", ",").replace("X", ".")
)

df1["tipo_emenda"] = pd.Categorical(df1["tipo_emenda"], categories=ordem_facetas, ordered=True)

# Gráfico de barras
bar1 = (
    alt.Chart(df1)
    .mark_bar()
    .encode(
        x=alt.X("Ano:O", title="", sort=sorted(df1["Ano"].unique()), axis=alt.Axis(labelAngle=0)),
        y=alt.Y("loa_mais_credito:Q", axis=alt.Axis(title=None, labels=False, ticks=False)),
        color=alt.Color(
            "tipo_emenda:N",
            title="Tipo de Emenda",
            scale=alt.Scale(
                domain=ordem_facetas,
                range=[cores_tipo_emenda[t] for t in ordem_facetas]
            ),
            legend=alt.Legend(
                orient="top",
                direction="horizontal",
                columns=4,
                labelFontSize=9,
                titleFontSize=12
            )
        ),
        xOffset=alt.X("tipo_emenda:N", sort=ordem_facetas),
        tooltip=["Ano", "tipo_emenda", "dotacao"]
    )
    .properties(
        width=700,
        height=400,
        title="Dotação atualizada (R$ bilhões) por tipo de emenda parlamentar"
    )
)

# Texto no topo das barras
text1 = (
    alt.Chart(df1)
    .mark_text(align="center", dy=-8, fontSize=9)
    .encode(
        x=alt.X("Ano:O", sort=sorted(df1["Ano"].unique())),
        y="loa_mais_credito:Q",
        text=alt.Text("dotacao:N"),
        xOffset=alt.X("tipo_emenda:N", sort=ordem_facetas)
    )
)

# Gráfico final com barra + texto
chart1 = bar1 + text1

st.altair_chart(chart1, use_container_width=True)


# ---------------------------
# 2) Evolução Funcao_desc por ResultadoPrimario_desc × Ano
# ---------------------------
st.header("2. Função de governo")

df2 = (
    df.groupby(["Ano", "Funcao_desc", "tipo_emenda"], as_index=True)
      .agg({"loa_mais_credito": "sum"})
      .unstack("tipo_emenda")
      .fillna(0)
      .stack()
      .reset_index()
      .rename(columns={0: "loa_mais_credito"})
)

tipo_selecionado = st.selectbox("Selecione o tipo de emenda:", df2["tipo_emenda"].dropna().unique())

df_tipo = df2[df2["tipo_emenda"] == tipo_selecionado].copy()
df_tipo = df_tipo[df_tipo["loa_mais_credito"] > 0]

# Corrigir formatação
df_tipo["dotacao"] = df_tipo["loa_mais_credito"].apply(
    lambda x: f'{x / 1e9:,.1f} bi'.replace(",", "X").replace(".", ",").replace("X", ".")
)

# Cor da emenda selecionada
cor_emenda = cores_tipo_emenda.get(tipo_selecionado, "#333333")

# Gráfico de barras com cor fixa
bar = (
    alt.Chart(df_tipo)
    .mark_bar(color=cor_emenda)
    .encode(
        x=alt.X("Ano:O", title=""),
        y=alt.Y("loa_mais_credito:Q", axis=alt.Axis(title=None, labels=False, ticks=False)),
        tooltip=["Ano", "Funcao_desc", "dotacao"]
    )
    .properties(width=170, height=140)
)

# Texto no topo da barra
text = (
    alt.Chart(df_tipo)
    .mark_text(align="center", dy=-8, fontSize=9)
    .encode(
        x="Ano:O",
        y="loa_mais_credito:Q",
        text=alt.Text("dotacao:N")
    )
)

# Facet final
titulo = f"Dotação atualizada (R$ bilhões) por função de governo para as emendas {tipo_selecionado}"

chart_funcao = (
    (bar + text)
    .facet(
        facet=alt.Facet("Funcao_desc:N", title=None, header=alt.Header(labelFontWeight="bold")),
        columns=7,
        title=titulo
    )
    .resolve_scale(y='shared')
)

st.altair_chart(chart_funcao, use_container_width=True)


# ---------------------------
# 3) Evolução ModalidadeAplicacao_desc por ResultadoPrimario_desc × Ano
# ---------------------------
st.header("3. Modalidade de Aplicação")

# Agrupamento
df3 = (
    df.groupby(["Ano", "tipo_emenda", "ModalidadeAplicacao_desc"], as_index=True)
      .agg({"loa_mais_credito": "sum"})
      .unstack("ModalidadeAplicacao_desc")
      .fillna(0)
      .stack()
      .reset_index()
      .rename(columns={0: "loa_mais_credito"})
)

# Remove zero e cria coluna formatada
df3 = df3[df3["loa_mais_credito"] > 0].copy()
df3["dotacao"] = df3["loa_mais_credito"].apply(
    lambda x: f'{x / 1e9:,.1f} bi'.replace(",", "X").replace(".", ",").replace("X", ".")
)

# Paleta de cores por modalidade
cores_modalidades = {
    "Transf. Estados e DF": "#4578B5",
    "Transf. a Municípios": "#6BAAE1",
    "Transf. Estados e DF - F/F": "#BDBB45",
    "Transf. a Municípios - F/F": "#E8E379",
    "Transf. a Inst. Priv. s/ fins lucr": "#9355D3",
    "Aplicações Diretas": "#7EB37E",
    "Outras": "#A0B6C8",
    "A definir": "#999999"
}

# Gráfico de barras
bar3 = (
    alt.Chart(df3)
    .mark_bar()
    .encode(
        x=alt.X("ModalidadeAplicacao_desc:N", axis=alt.Axis(title=None, labels=False, ticks=False)),
        y=alt.Y("loa_mais_credito:Q", axis=alt.Axis(title=None, labels=False, ticks=False)),
        color=alt.Color(
            "ModalidadeAplicacao_desc:N",
            title="Modalidade de Aplicação",
            scale=alt.Scale(
                domain=list(cores_modalidades.keys()),
                range=list(cores_modalidades.values())
            ),
            legend=alt.Legend(
                orient="top",
                direction="horizontal",
                columns=8,
                labelFontSize=9,
                titleFontSize=12
            )
        ),
        tooltip=["Ano", "tipo_emenda", "ModalidadeAplicacao_desc", "dotacao"]
    )
    .properties(width=300, height=140)
)

# Texto no topo da barra
text3 = (
    alt.Chart(df3)
    .mark_text(align="center", dy=-8, fontSize=9)
    .encode(
        x="ModalidadeAplicacao_desc:N",
        y="loa_mais_credito:Q",
        text=alt.Text("dotacao:N")
    )
)

# Gráfico facetado por Ano (linha) e tipo_emenda (coluna)
chart3 = (
    (bar3 + text3)
    .facet(
        row=alt.Row(
            "Ano:O",
            title=None,
            sort=sorted(df3["Ano"].unique()),
            header=alt.Header(labelFontWeight="bold")
        ),
        column=alt.Column(
            "tipo_emenda:N",
            title=None,
            header=alt.Header(labelFontWeight="bold")
        ),
        title="Dotação atualizada (R$ bilhões) por modalidade de aplicação"
    )
    .resolve_scale(y='shared')
)

st.altair_chart(chart3, use_container_width=True)


# ---------------------------
# 4) Comparação de loa_mais_credito, empenhado e pago em 2025
# ---------------------------
st.header("4. Execução orçamentária (2025)")

# Função para formatar valores no padrão brasileiro em milhões
def formatar_valor_br(x):
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# Função para gerar barra visual
def barra_visual(pct):
    if pd.isna(pct):
        return ""
    blocos = int(pct // 10)
    return "▰" * blocos + "▱" * (10 - blocos)

# Filtra o ano de 2025
df_2025 = df[df["Ano"] == 2025].copy()

# Seletor de tipo de emenda
tipos_disponiveis = df_2025["tipo_emenda"].dropna().unique()
tipo_selecionado = st.selectbox("Selecione o tipo de emenda:", tipos_disponiveis)

# Seletor de critério de ordenação
criterio = st.selectbox(
    "Ordenar por:",
    options=["Dotação", "% Empenhado", "% Pago"]
)

# Mapeia para coluna numérica usada na ordenação
coluna_ordenacao = {
    "Dotação": "Dotacao_mi",
    "% Empenhado": "% Empenhado (num)",
    "% Pago": "% Pago (num)"
}[criterio]

# Filtra os dados para o tipo de emenda
df_emenda = df_2025[df_2025["tipo_emenda"] == tipo_selecionado].copy()

# Cria a coluna "Ação Governamental"
df_emenda["Ação Governamental"] = df_emenda["Acao_cod"] + " - " + df_emenda["Acao_desc"]

# Agrupa por Ação Governamental
df4 = (
    df_emenda
    .groupby("Ação Governamental", as_index=False)
    .agg({
        "loa_mais_credito": "sum",
        "empenhado": "sum",
        "pago": "sum"
    })
)

# Calcula percentuais
df4["% Empenhado (num)"] = (df4["empenhado"] / df4["loa_mais_credito"]) * 100
df4["% Pago (num)"] = (df4["pago"] / df4["loa_mais_credito"]) * 100

# Formata percentuais com barra visual
df4["% Empenhado"] = df4["% Empenhado (num)"].apply(barra_visual)
df4["% Pago"] = df4["% Pago (num)"].apply(barra_visual)

# Cria colunas numéricas em milhões
df4["Dotacao_mi"] = df4["loa_mais_credito"] / 1e6
df4["Empenhado_mi"] = df4["empenhado"] / 1e6
df4["Pago_mi"] = df4["pago"] / 1e6

# Ordena pelo critério escolhido
df4 = df4.sort_values(coluna_ordenacao, ascending=False).reset_index(drop=True)

# Formata para exibição
df4["Dotação (mi)"] = df4["Dotacao_mi"].apply(formatar_valor_br)
df4["Empenhado (mi)"] = df4["Empenhado_mi"].apply(formatar_valor_br)
df4["Pago (mi)"] = df4["Pago_mi"].apply(formatar_valor_br)

# Seleciona colunas finais para exibição
df_final = df4[[
    "Ação Governamental", "Dotação (mi)", "Empenhado (mi)", "Pago (mi)", "% Empenhado", "% Pago"
]]

# Exibe tabela final
st.dataframe(df_final, use_container_width=True)


# Pega a data atual no formato DD/MM/AAAA
hoje = datetime.now().strftime("%d/%m/%Y")

# Exibe a mensagem no final da página
st.warning(f"Última atualização da base realizada em {hoje}.")
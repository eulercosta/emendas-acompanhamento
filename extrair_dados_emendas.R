# Define a mesma pasta customizada para pacotes
custom_lib <- "/tmp/Rpackages"
Sys.setenv(R_LIBS_USER = custom_lib)
.libPaths(custom_lib)

# Agora tenta carregar o pacote orcamentoBR
library(orcamentoBR)

dados_total <- data.frame()

for (ano in c(2022, 2023, 2024, 2025)) {
  dados <- despesaDetalhada(
    exercicio = ano,
    detalheMaximo = FALSE,
    Funcao = TRUE,
    Acao = TRUE,
    ModalidadeAplicacao = TRUE,
    ResultadoPrimario = TRUE,
    incluiDescricoes = TRUE
  )

  dados_emendas <- subset(dados, ResultadoPrimario_cod %in% c("6", "7", "8"))
  dados_emendas$Ano <- ano
  dados_total <- rbind(dados_total, dados_emendas)
}

# Salva como CSV
write.csv(dados_total, "dados_emendas.csv", row.names = FALSE, fileEncoding = "UTF-8")
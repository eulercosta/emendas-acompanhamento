# Cria a pasta de bibliotecas se não existir
dir.create(Sys.getenv("R_LIBS_USER"), showWarnings = FALSE, recursive = TRUE)

# Instala o pacote 'remotes' (se necessário)
install.packages("remotes")

# Instala 'orcamentoBR' no diretório que definimos em R_LIBS_USER
remotes::install_cran("orcamentoBR",
                        lib = Sys.getenv("R_LIBS_USER"))
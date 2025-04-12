# Define o diretório gravável de pacotes (usado em deploy)
custom_lib <- "/tmp/Rpackages"
Sys.setenv(R_LIBS_USER = custom_lib)

# Cria a pasta se ela não existir
dir.create(custom_lib, showWarnings = FALSE, recursive = TRUE)

# Instala o pacote 'remotes' (se necessário)
install.packages("remotes")

# Instala orcamentoBR na pasta customizada
remotes::install_cran("orcamentoBR", lib = custom_lib)
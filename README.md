# 🚀 Análise de Dados Inteligente com Gemini e Streamlit

-----

## 💡 Sobre o Projeto

Este é um aplicativo **Streamlit** que automatiza e simplifica o processo de análise exploratória de dados (**EDA**). Ele integra o modelo **Gemini** para interpretar seus dados, construir consultas SQL e, por fim, analisar os resultados para gerar respostas detalhadas e gráficos relevantes.

## ✨ Fluxo de Trabalho (Como Funciona)

A solução segue uma sequência lógica para garantir uma análise rápida e eficiente:

### 1\. 📥 Upload Flexível de Dados

Você pode carregar seus dados em dois formatos práticos:

  * Arquivo **CSV** em texto claro.
  * Arquivo **CSV compactado** em formato **.zip**.

### 2\. 🧠 Análise e Estruturação (Assistida por IA)

Os dados carregados passam por uma etapa de análise inicial com a IA para estruturar as colunas e preparar a base para a inserção.

⚠️ **Atenção:** A análise de dados para criação do esquema de banco pode ser desafiadora para a IA. **Colunas com formatos de data variados ou ambíguos** são o principal ponto de atenção e podem exigir verificação.

### 3\. 💾 Armazenamento Otimizado

Para garantir **rapidez** e manter a **memória RAM leve**, os dados estruturados são inseridos em um banco de dados **SQLite** local.

### 4\. 🔑 Configuração e Consulta

No painel de análise, você deve:

  * Selecionar o **banco de dados** (SQLite) que deseja consultar.
  * Inserir um **breve descritivo** do que se trata o conjunto de dados.
  * Fornecer sua **Chave API do Gemini** para iniciar a consulta.

> **Importante:** A IA utiliza seus próprios créditos do Gemini/Google para processar as consultas. Cada usuário é responsável pelo seu consumo.

### 5\. 🛠️ Geração Inteligente de Consulta SQL

Com base na sua pergunta e no descritivo, a IA **monta o comando de consulta** necessário para extrair as informações corretas do seu banco de dados.

### 6\. 📊 Análise, Resposta e Visualização

Este é o passo final onde a mágica acontece:

1.  Com os dados extraídos, a IA do Gemini executa a **análise completa**.
2.  Gera uma **resposta clara e detalhada** para sua questão.
3.  **Sugere e plota um gráfico** (linhas, barras, etc.) para visualizar o *insight* imediatamente.

-----

## 🛠️ Tecnologias Utilizadas

  * **Streamlit:** Para a interface de usuário web.
  * **Gemini API (Google AI):** Para a inteligência de análise, consulta e resposta.
  * **SQLite:** Para o banco de dados leve e rápido.

-----

## ➡️ Como Começar (Instalação Local)

1.  Clone este repositório:
    ```bash
    git clone [SEU_LINK_DO_REPOSITORIO]
    cd [NOME_DO_SEU_PROJETO]
    ```
2.  Crie e ative um ambiente virtual (opcional, mas recomendado).
3.  Instale as dependências:
    ```bash
    pip install -r requirements.txt
    ```
4.  Execute o aplicativo Streamlit:
    ```bash
    streamlit run app.py
    ```
5.  Acesse o aplicativo no seu navegador.

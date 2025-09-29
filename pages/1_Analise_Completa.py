import streamlit as st
import pandas as pd
import sqlite3
import os
import requests
import json
import re
from typing import List

# ----------------------------------------------------------------------
# CONFIGURAÇÕES
# ----------------------------------------------------------------------
DB_FILE = "db.sqlite"
st.set_page_config(layout="wide")
st.title("Análise SQL via Gemini com Explicações e Gráficos")
st.markdown("Pergunte em linguagem natural → gera SQL → executa no SQLite → Gemini explica o resultado.")

# ----------------------------------------------------------------------
# FUNÇÕES SQLITE
# ----------------------------------------------------------------------
@st.cache_resource
def get_sqlite_connection_analysis():
    if not os.path.exists(DB_FILE):
        st.error(f"O banco de dados '{DB_FILE}' não foi encontrado.")
        st.stop()
    return sqlite3.connect(DB_FILE, timeout=30.0, check_same_thread=False)

def get_table_list(conn: sqlite3.Connection) -> List[str]:
    query = "SELECT name FROM sqlite_master WHERE type='table';"
    tables = pd.read_sql_query(query, conn)['name'].tolist()
    return [t for t in tables if not t.startswith('sqlite_')]

def get_table_sample(conn: sqlite3.Connection, table: str) -> pd.DataFrame:
    q = f"SELECT * FROM {table} LIMIT 3;"
    return pd.read_sql_query(q, conn)

# ----------------------------------------------------------------------
# FUNÇÃO PARA PARSE DO JSON GERADO PELO GEMINI
# ----------------------------------------------------------------------
def extrair_sql(resposta: str) -> str:
    """
    Extrai o comando SQL de uma resposta do Gemini.
    Funciona mesmo que o JSON venha embutido em texto.
    """
    try:
        match = re.search(r'\{.*\}', resposta, re.DOTALL)
        if match:
            json_text = match.group(0)
            data = json.loads(json_text)
            return data.get("comandosql", "").strip()
    except Exception as e:
        st.warning(f"Não foi possível interpretar a resposta como JSON: {e}")
    return resposta.strip()

# ----------------------------------------------------------------------
# ESCAPAR COLUNAS COM CARACTERES ESPECIAIS
# ----------------------------------------------------------------------
def escape_column_names(sql: str, df_columns: list) -> str:
    """
    Substitui nomes de colunas que contêm caracteres especiais por aspas duplas.
    """
    for col in df_columns:
        if not re.match(r'^[A-Za-z0-9_]+$', col):  # se tiver caractere especial
            sql = re.sub(rf'\b{re.escape(col)}\b', f'"{col}"', sql)
    return sql

# ----------------------------------------------------------------------
# CONFIGURAÇÃO GEMINI
# ----------------------------------------------------------------------
st.sidebar.header("Configuração do Gemini")
gemini_api_key = st.sidebar.text_input("Gemini API Key", type="password")

# ----------------------------------------------------------------------
# INTERFACE
# ----------------------------------------------------------------------
try:
    conn = get_sqlite_connection_analysis()
    available_tables = get_table_list(conn)
except Exception:
    available_tables = []

if available_tables and gemini_api_key:
    st.markdown("---")

    selected_table = st.selectbox("Selecione uma Tabela", available_tables, index=0)
    descricao_breve = st.text_area("Breve descrição sobre os dados", "Exemplo: Dados de vendas por cliente e produto.")
    pergunta = st.text_input("Digite sua pergunta em linguagem natural")

    if st.button("Gerar SQL, Executar e Analisar com Gemini"):
        # -----------------------------
        # Pega sample real da tabela (3 linhas)
        # -----------------------------
        sample_df = get_table_sample(conn, selected_table)
        sample_str = sample_df.to_string(index=False)

        # -----------------------------
        # Prompt para gerar SQL (usando somente a tabela selecionada)
        # -----------------------------
        prompt = f"""
Você deve gerar um comando SQL **apenas usando a tabela '{selected_table}'**.
Não use nenhuma outra tabela, apenas esta.

Aqui está uma amostra do conteúdo da tabela que vamos analisar (incluindo nomes das colunas):
{sample_str}

O breve descritivo sobre os dados é: {descricao_breve}

Responder com o comando SQL para sqlite que reúne os dados que precisa para responder a pergunta no formato:
{{"comandosql":"..."}}

Pergunta do usuário: {pergunta}
"""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_api_key}"

        # -----------------------------
        # Consulta Gemini para gerar SQL
        # -----------------------------
        with st.spinner("Consultando Gemini para gerar SQL..."):
            response = requests.post(
                url,
                headers={"Content-Type": "application/json"},
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=60
            )

        if response.status_code == 200:
            result = response.json()
            gemini_reply = result["candidates"][0]["content"]["parts"][0]["text"]
            st.subheader("Resposta do Gemini (Bruta)")
            st.text_area("Resposta Completa", gemini_reply, height=150)

            # -----------------------------
            # Extrai SQL
            # -----------------------------
            comando_sql = extrair_sql(gemini_reply)

            if comando_sql:
                # Escapa nomes de colunas especiais
                comando_sql_escaped = escape_column_names(comando_sql, sample_df.columns.tolist())

                st.success(f"SQL extraído (escapado): {comando_sql_escaped}")
                with st.spinner("Executando consulta no SQLite..."):
                    try:
                        df_result = pd.read_sql_query(comando_sql_escaped, conn)
                        st.subheader("Resultado da Consulta SQL")
                        st.dataframe(df_result, use_container_width=True)

                        # -----------------------------
                        # Prompt para explicação do resultado
                        # -----------------------------
                        explicacao_prompt = f"""
Na pergunta original, o usuário pediu: "{pergunta}".

O comando SQL executado foi:
{comando_sql_escaped}

O resultado retornado pelo SQLite foi:
{df_result.to_string(index=False)}

Explique em linguagem clara o que esse resultado significa,
faça considerações sobre os dados e sugira (ou descreva) um gráfico adequado para representar essas informações.
"""

                        with st.spinner("Consultando Gemini para explicar os resultados..."):
                            response2 = requests.post(
                                url,
                                headers={"Content-Type": "application/json"},
                                json={"contents": [{"parts": [{"text": explicacao_prompt}]}]},
                                timeout=60
                            )

                        if response2.status_code == 200:
                            result2 = response2.json()
                            explicacao = result2["candidates"][0]["content"]["parts"][0]["text"]
                            st.subheader("Considerações do Gemini sobre os resultados")
                            st.markdown(explicacao)

                            # -----------------------------
                            # Gráfico automático (duas primeiras colunas numéricas)
                            # -----------------------------
                            num_cols = df_result.select_dtypes(include='number').columns.tolist()
                            if len(num_cols) >= 2:
                                st.subheader("Visualização sugerida")
                                st.bar_chart(df_result, x=num_cols[0], y=num_cols[1])
                            elif len(num_cols) == 1:
                                st.subheader("Visualização sugerida")
                                st.line_chart(df_result[num_cols[0]])
                            else:
                                st.info("Não há colunas numéricas para gerar gráfico automaticamente.")

                        else:
                            st.error(f"Erro na análise do Gemini: {response2.status_code} - {response2.text}")

                    except Exception as e:
                        st.error(f"Erro ao executar SQL: {e}")

            else:
                st.error("Não foi possível extrair um comando SQL válido da resposta do Gemini.")
        else:
            st.error(f"Erro na API Gemini: {response.status_code} - {response.text}")

else:
    st.warning("Nenhuma tabela encontrada no banco de dados ou Gemini API Key não informada.")

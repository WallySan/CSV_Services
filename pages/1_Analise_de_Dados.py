import streamlit as st
import pandas as pd
import sqlite3
import os
from typing import List, Dict, Any

# ----------------------------------------------------------------------
# CONFIGURAÇÕES E CONEXÃO
# ----------------------------------------------------------------------

# O arquivo do banco de dados está na raiz do projeto, ao lado da pasta 'pages'
DB_FILE = "db.sqlite" 

st.set_page_config(layout="wide")
st.title("Página de Análise SQL e Visualização")
st.markdown("Use esta página para executar consultas SQL diretamente no banco de dados local **`db.sqlite`**.")

st.sidebar.success("Selecionar AAAA")


# ----------------------------------------------------------------------
# FUNÇÕES DE CONEXÃO E CONSULTA (Chave para o Streamlit Multi-página)
# ----------------------------------------------------------------------

@st.cache_resource
def get_sqlite_connection_analysis():
    """
    Retorna uma conexão SQLite. Usa cache para garantir que a conexão seja
    compartilhada de forma eficiente entre todas as páginas e sessões.
    
    check_same_thread=False é crucial para evitar o erro de thread do Streamlit.
    """
    # Verifica se o arquivo existe
    if not os.path.exists(DB_FILE):
        st.error(f"O banco de dados '{DB_FILE}' não foi encontrado. Por favor, volte para a página principal para importar o arquivo CSV.")
        st.stop()
        
    return sqlite3.connect(DB_FILE, timeout=30.0, check_same_thread=False)

@st.cache_data(ttl=3600)
def run_sqlite_query(query: str):
    """Executa uma consulta SQL e retorna o resultado como um DataFrame, com cache."""
    conn = get_sqlite_connection_analysis() 
    
    try:
        # Usa o Pandas para ler a consulta SQL diretamente do banco
        df = pd.read_sql_query(query, conn)
        return df
    except sqlite3.Error as e:
        st.error(f"Erro ao executar a consulta SQL: {e}")
        return pd.DataFrame()


def get_table_list(conn: sqlite3.Connection) -> List[str]:
    """Obtém a lista de tabelas no banco de dados."""
    query = "SELECT name FROM sqlite_master WHERE type='table';"
    tables = pd.read_sql_query(query, conn)['name'].tolist()
    # Filtra tabelas internas do SQLite
    return [t for t in tables if not t.startswith('sqlite_')]

# ----------------------------------------------------------------------
# INTERFACE DO USUÁRIO
# ----------------------------------------------------------------------

# Tenta obter a lista de tabelas logo no início
try:
    conn = get_sqlite_connection_analysis()
    available_tables = get_table_list(conn)
except Exception:
    available_tables = [] # Caso o arquivo db.sqlite ainda não exista

if available_tables:
    st.markdown("---")
    
    col1, col2 = st.columns([1, 4])
    
    with col1:
        # Permite ao usuário selecionar uma tabela existente
        selected_table = st.selectbox(
            "Selecione uma Tabela",
            available_tables,
            index=0
        )
    
    with col2:
        # Exibe o DDL da tabela selecionada (opcional, mas útil)
        try:
            ddl_query = pd.read_sql_query(f"SELECT sql FROM sqlite_master WHERE name='{selected_table}';", conn)['sql'].iloc[0]
            with st.expander("Ver Schema (DDL) da Tabela"):
                st.code(ddl_query, language='sql')
        except:
            st.warning("Não foi possível carregar o DDL da tabela.")

    # Área de Consulta SQL Customizada
    default_query = f"""
    -- Selecione, filtre e agregue seus dados aqui.
    SELECT 
        * FROM "{selected_table}" 
    LIMIT 500;
    """

    custom_query = st.text_area(
        "Insira sua Consulta SQL", 
        value=default_query,
        height=200
    )

    if st.button("Executar Consulta SQL"):
        if not custom_query.strip():
            st.warning("A consulta SQL não pode ser vazia.")
        else:
            # Substitui a placeholder da tabela, se estiver no formato padrão
            final_query = custom_query.replace("{}".format(selected_table), selected_table)
            
            with st.spinner("Executando consulta..."):
                df_result = run_sqlite_query(final_query)

            if not df_result.empty:
                st.success(f"Consulta executada com sucesso. {len(df_result)} linhas retornadas.")
                st.dataframe(df_result, use_container_width=True)
                
                st.subheader("Visualização Simples (Gráfico de Barras)")
                # Tenta plotar as duas primeiras colunas se houver mais de uma
                if len(df_result.columns) >= 2:
                    try:
                        st.bar_chart(df_result, x=df_result.columns[0], y=df_result.columns[1])
                    except Exception as e:
                        st.caption(f"Não foi possível gerar o gráfico de barras (erro de tipo de dado).")
            else:
                st.info("Nenhum resultado encontrado ou a consulta falhou (verifique a mensagem de erro acima).")

else:
    st.warning("Nenhuma tabela encontrada no banco de dados. Por favor, volte para a página de **Upload** e importe um arquivo CSV.")
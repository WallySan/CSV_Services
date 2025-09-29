import streamlit as st
import pandas as pd
import sqlite3
import os
import uuid
import zipfile
import re
import io
import numpy as np  # <--- ADICIONE ESTA LINHA!

from pathlib import Path
from typing import List, Dict, Any, Tuple

# ----------------------------------------------------------------------
# CONFIGURAÇÕES E INICIALIZAÇÃO
# ----------------------------------------------------------------------
st.set_page_config(layout="wide")
st.title("Processamento Monolítico (Streamlit) para SQLite Local")

# Pasta de dados para salvar temporariamente o arquivo (necessário para zip e segurança)
DATA_DIR = Path("./dados_temp")
DATA_DIR.mkdir(exist_ok=True)

# Arquivo do banco de dados SQLite local
DB_FILE = "db.sqlite"

# Tamanho do lote de inserção e chunking
CHUNK_SIZE = 50000 
BATCH_SIZE = 5000 

# ----------------------------------------------------------------------
# FUNÇÕES DE BANCO DE DADOS E PROCESSAMENTO
# ----------------------------------------------------------------------

@st.cache_resource
def get_sqlite_connection():
    """Retorna uma conexão SQLite segura e cached."""
    # CORREÇÃO: Adicione check_same_thread=False para evitar o erro de thread do Streamlit
    return sqlite3.connect(DB_FILE, timeout=30.0, check_same_thread=False)

def execute_batch_insert_sqlite(cursor: sqlite3.Cursor, table_name: str, columns: List[str], batch_data: List[Tuple]):
    """Executa um INSERT em lote usando executemany."""
    column_names = ', '.join(f'"{col}"' for col in columns)
    placeholders = ', '.join(['?'] * len(columns))
    insert_query_str = f"INSERT INTO \"{table_name}\" ({column_names}) VALUES ({placeholders})"
    cursor.executemany(insert_query_str, batch_data)

def execute_select_limit(conn: sqlite3.Connection, table_name: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Seleciona as primeiras N linhas da tabela para verificação."""
    query = f"SELECT * FROM \"{table_name}\" LIMIT {limit}"
    
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    cursor.execute(query)
    
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def get_csv_stream(file_path: Path):
    """Retorna o stream de texto para o CSV, seja ele solto ou dentro de um ZIP."""
    if file_path.suffix == ".zip":
        with zipfile.ZipFile(file_path, "r") as z:
            csv_files = [f for f in z.namelist() if f.endswith(".csv")]
            if not csv_files: raise ValueError("ZIP não contém arquivos CSV.")
            
            # Nota: Retornamos o stream aberto, quem chama é responsável por fechar o ZIP
            return z.open(csv_files[0], 'r')
    
    elif file_path.suffix == ".csv":
        return open(file_path, 'r', encoding='utf-8')
        
    else:
        raise ValueError("Formato inválido. Apenas .csv ou .zip.")

# ----------------------------------------------------------------------
# FUNÇÃO DE ANÁLISE E INSERÇÃO COMPLETA
# ----------------------------------------------------------------------

def process_full_workflow(file_path: Path, table_name: str):
    """Gerencia DDL, criação de tabela e inserção em lote."""
    
    conn = get_sqlite_connection()
    row_count = 0
    ddl_query = ""

    # 1. ANÁLISE DA ESTRUTURA E GERAÇÃO DO DDL
    st.info("Passo 1/4: Analisando a estrutura do arquivo em chunks para gerar o DDL...")
    
    # Esta função usa o chunking para inferir os tipos e nomes das colunas
    # (Adaptado da lógica anterior de análise)
    def generate_schema_from_chunks(file_path: Path):
        summary = {}
        
        # Leitura e Processamento em Chunks para inferir tipos
        with get_csv_stream(file_path) as f:
            # Envolve o stream binário em um stream de texto se for de um ZIP
            text_stream = io.TextIOWrapper(f, encoding='utf-8') if file_path.suffix == ".zip" else f
            
            for chunk in pd.read_csv(text_stream, chunksize=CHUNK_SIZE, encoding='utf-8', engine='python'):
                # Limpa e formata os nomes das colunas
                chunk.columns = [str(col).strip().replace(' ', '_').replace('.', '_') for col in chunk.columns]

                for col in chunk.columns:
                    data = chunk[col]
                    col = col.lower()

                    if col not in summary:
                        summary[col] = {'is_numeric': True, 'has_text': False} 

                    is_numeric_chunk = pd.api.types.is_numeric_dtype(data)
                    if summary[col]['has_text']: continue

                    if not is_numeric_chunk or data.dtype == np.dtype('object'):
                        # Tenta forçar conversão para float para determinar se a coluna é REAL
                        try:
                            data.astype(float)
                        except:
                            summary[col]['is_numeric'] = False
                            summary[col]['has_text'] = True
        
        # Monta DDL e lista final de colunas
        columns_for_insert = []
        create_table = f"CREATE TABLE IF NOT EXISTS \"{table_name}\" (\n"
        
        for col, info in summary.items():
            col_name_safe = col.replace('-', '_')
            columns_for_insert.append(col_name_safe)
            
            ddl_type = "REAL" if info['is_numeric'] and not info['has_text'] else "TEXT"
            create_table += f"    \"{col_name_safe}\" {ddl_type},\n"
        
        create_table = create_table.rstrip(",\n") + "\n);"

        return create_table, columns_for_insert

    try:
        ddl_query, columns_to_insert = generate_schema_from_chunks(file_path)
        
        if not columns_to_insert:
            st.error("O arquivo CSV não contém colunas válidas. Abortando.")
            return

        # 2. CRIAÇÃO DA TABELA
        st.info("Passo 2/4: Executando DDL para criar a tabela...")
        with conn: # 'with conn' garante o commit/rollback
            cursor = conn.cursor()
            cursor.execute(ddl_query)
        st.success("Tabela criada/verificada com sucesso.")
        
        
        # 3. INSERÇÃO DE DADOS EM LOTE
        st.info("Passo 3/4: Iniciando inserção de dados em lote (otimizado por stream)...")
        
        # Abertura do arquivo para a inserção (deve ser reaberto)
        with get_csv_stream(file_path) as f:
            text_stream = io.TextIOWrapper(f, encoding='utf-8') if file_path.suffix == ".zip" else f
            reader = csv.reader(text_stream)
            
            try:
                next(reader) # Pular o cabeçalho
            except StopIteration:
                st.warning("O arquivo CSV está vazio após o cabeçalho. Nada para inserir.")
                return ddl_query, 0, []
            
            batch_data = []
            
            # O processo de inserção precisa de uma transação ativa
            with conn: 
                cursor = conn.cursor()
                
                for row in reader:
                    if not row: continue
                    
                    if len(row) != len(columns_to_insert):
                        # Pula linhas com número incorreto de colunas
                        continue
                        
                    row_values = []
                    for value in row:
                        stripped_value = str(value).strip()
                        
                        if not stripped_value or stripped_value.upper() in ('NAN', 'NULL', '#N/A', 'N/A', 'NONE'):
                            row_values.append(None)
                            continue
                        
                        try:
                            # Tenta converter para numérico
                            num_value = float(stripped_value)
                            row_values.append(int(num_value) if num_value == int(num_value) else num_value)
                        except ValueError:
                            row_values.append(value)
                    
                    batch_data.append(tuple(row_values))
                    
                    if len(batch_data) >= BATCH_SIZE:
                        execute_batch_insert_sqlite(cursor, table_name, columns_to_insert, batch_data)
                        batch_data = []
                        
                    row_count += 1
                
                # Inserir lote restante
                if batch_data:
                    execute_batch_insert_sqlite(cursor, table_name, columns_to_insert, batch_data)

        st.success(f"Inserção em lote concluída! Total de {row_count} linhas inseridas.")


        # 4. VERIFICAÇÃO FINAL
        st.info("Passo 4/4: Selecionando as primeiras 50 linhas para verificação...")
        verification_rows = execute_select_limit(conn, table_name)
        
        return ddl_query, row_count, verification_rows

    except sqlite3.Error as db_error:
        st.error(f"Erro de Banco de Dados SQLite: {str(db_error)}")
        return None, 0, []
    except Exception as e:
        st.error(f"Erro Crítico durante o processamento: {str(e)}")
        return None, 0, []
    finally:
        # 5. LIMPEZA
        if os.path.exists(file_path):
            os.remove(file_path)
            st.caption(f"Arquivo temporário removido do disco: {file_path.name}")

# ----------------------------------------------------------------------
# INTERFACE DO USUÁRIO
# ----------------------------------------------------------------------

uploaded_file = st.file_uploader("Escolha um arquivo (.csv ou .zip)", type=["csv", "zip"])
unique_filename = None

if uploaded_file is not None:
    # 1. Salva o arquivo temporariamente no disco
    file_ext = uploaded_file.name.split('.')[-1].lower()
    unique_filename = f"{uuid.uuid4()}.{file_ext}"
    file_path = DATA_DIR / unique_filename
    
    suggested_table_name = re.sub(r'[^a-zA-Z0-9_]', '_', uploaded_file.name.split('.')[0]).lower()
    if not suggested_table_name: suggested_table_name = "dados_csv"

    try:
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"Arquivo salvo temporariamente para processamento: **{unique_filename}**")

    except Exception as e:
        st.error(f"Falha ao salvar o arquivo no disco: {e}")
        unique_filename = None

if unique_filename:
    st.markdown("---")
    
    table_name = st.text_input(
        "Nome da Tabela de Destino (SQLite)", 
        value=suggested_table_name,
        key="table_name_input"
    )
    
    # Botão processar
    if st.button("Criar Tabela, Inserir Dados e Verificar"):
        if not table_name:
            st.warning("O nome da tabela não pode ser vazio.")
        else:
            # INÍCIO DO PROCESSO PRINCIPAL
            # O st.spinner é crucial para indicar ao usuário que a aplicação está ocupada
            with st.spinner("⚠️ **Processando...** O aplicativo ficará bloqueado durante a análise e inserção (não feche a aba)"):
                ddl, total_rows, verification_rows = process_full_workflow(file_path, table_name)
            
            # EXIBIÇÃO DOS RESULTADOS
            if total_rows > 0:
                st.balloons()
                st.header("1. DDL SQL (CREATE TABLE)")
                st.code(ddl, language='sql')
                
                st.header("2. Verificação (Primeiras 50 Linhas)")
                df_verification = pd.DataFrame(verification_rows)
                st.dataframe(df_verification, use_container_width=True)
            elif ddl is not None:
                st.warning("A tabela foi criada, mas 0 linhas foram inseridas. Verifique o arquivo CSV.")
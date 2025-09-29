import os
import uuid
import zipfile
import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any

# Pasta de destino
DATA_DIR = Path("./dados")
DATA_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------
# FUNÇÃO DE ANÁLISE (O código que era do FastAPI, adaptado)
# ---------------------------------------------------
def analyze_csv_local(filename: str, description: str) -> Dict[str, Any] | None:
    file_path = (DATA_DIR / filename).resolve()
    summary = {}
    chunksize = 50000 
    
    # ... (O restante da lógica de processamento de chunks e estatísticas) ...
    
    # 2. Função Otimizada para Processar Cada Chunk (mesma lógica)
    def process_chunk(df_chunk, summary):
        # ... (Mantido o código interno da função process_chunk, sem alterações) ...
        df_chunk.columns = [str(col).strip().replace(' ', '_').replace('.', '_') for col in df_chunk.columns]

        for col in df_chunk.columns:
            data = df_chunk[col]
            col = col.lower()

            if col not in summary:
                summary[col] = {'type': str(data.dtype), 'min': None, 'max': None, 'min_len': None, 'max_len': 0}

            is_numeric = pd.api.types.is_numeric_dtype(data)

            if is_numeric:
                current_min = data.min()
                current_max = data.max()

                if not pd.isna(current_min):
                    if summary[col]['min'] is None: summary[col]['min'] = current_min
                    else: summary[col]['min'] = min(summary[col]['min'], current_min)

                if not pd.isna(current_max):
                    if summary[col]['max'] is None: summary[col]['max'] = current_max
                    else: summary[col]['max'] = max(summary[col]['max'], current_max)
                    
            if not is_numeric or data.dtype == np.dtype('object'):
                non_null_strings = data.dropna().astype(str)
                
                if not non_null_strings.empty:
                    data_str_len = non_null_strings.str.len()
                    
                    current_min_len = data_str_len.min()
                    current_max_len = data_str_len.max()

                    if summary[col]['min_len'] is None: summary[col]['min_len'] = current_min_len
                    else: summary[col]['min_len'] = min(summary[col]['min_len'], current_min_len)

                    summary[col]['max_len'] = max(summary[col]['max_len'], current_max_len)
                    
                    if summary[col]['type'] in ('object', 'str'): summary[col]['type'] = 'object_string'

        return summary
    
    # 3. Leitura Segura de CSV ou ZIP com Streaming (mesma lógica)
    chunk_count = 0
    
    try:
        if file_path.suffix == ".zip":
            with zipfile.ZipFile(file_path, "r") as z:
                csv_files = [f for f in z.namelist() if f.endswith(".csv")]
                if not csv_files: return {"error": "ZIP sem arquivos CSV."}
                
                csv_in_zip = csv_files[0]
                with z.open(csv_in_zip) as f:
                    for chunk in pd.read_csv(f, chunksize=chunksize, encoding='utf-8', engine='python'):
                        chunk_count += 1
                        summary = process_chunk(chunk, summary)
        
        elif file_path.suffix == ".csv":
            for chunk in pd.read_csv(file_path, chunksize=chunksize, encoding='utf-8', engine='python'):
                chunk_count += 1
                summary = process_chunk(chunk, summary)
                
        else:
            return {"error": "Formato inválido. Apenas .csv ou .zip."}
    except Exception as e:
        return {"error": f"Erro durante a leitura do arquivo: {str(e)}"}

    # 4. Monta CREATE TABLE (DDL SQL) para **SQLite** (mesma lógica)
    table_name = Path(filename).stem.replace('.', '_').replace('-', '_')
    create_table = f"-- DDL gerado para o arquivo: {filename}\nCREATE TABLE \"{table_name}\" (\n"
    
    for col, info in summary.items():
        col_name_safe = col.replace('-', '_')
        if info['min'] is not None or info['max'] is not None:
            create_table += f"    \"{col_name_safe}\" REAL,\n" 
        else:
            create_table += f"    \"{col_name_safe}\" TEXT,\n"
    
    create_table = create_table.rstrip(",\n") + "\n);"

    # 5. Monta análise detalhada (mesma lógica)
    analysis = []
    for col, info in summary.items():
        info_copy = info.copy()
        info_copy['type'] = str(info_copy['type'])
        
        for key in ['min', 'max', 'min_len', 'max_len']:
            value = info_copy.get(key)
            if value is not None and isinstance(value, (np.integer, np.floating)):
                info_copy[key] = value.item()
        
        analysis.append({"column": col, **info_copy})

    return {"description": description, "analysis": analysis, "create_table": create_table}

# ---------------------------------------------------
# APLICATIVO STREAMLIT
# ---------------------------------------------------
st.set_page_config(layout="wide")
st.title("Upload de Arquivo CSV/ZIP (Modo Local)")

uploaded_file = st.file_uploader("Escolha um arquivo (.csv ou .zip)", type=["csv", "zip"])

if uploaded_file is not None:
    # 1. Salva o arquivo original
    file_ext = uploaded_file.name.split('.')[-1].lower()
    unique_filename = f"{uuid.uuid4()}.{file_ext}"
    file_path = DATA_DIR / unique_filename
    
    try:
        # Salva o arquivo no disco (necessário para a função de análise)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.success(f"Arquivo salvo localmente para análise: **{unique_filename}**")

        # Verifica ZIP
        if file_ext == "zip":
            # ... (Lógica de verificação ZIP) ...
            pass # Simplificado para o exemplo, a lógica de verificação está no analyze_csv_local

    except Exception as e:
        st.error(f"Falha ao salvar o arquivo no disco: {e}")
        unique_filename = None


    if unique_filename:
        st.markdown("---")
        description = st.text_input("Descrição do arquivo para a análise", key="desc")
        
        # Botão processar
        if st.button("Processar Análise (Gerar DDL SQLite)"):
            if not description:
                st.warning("Por favor, forneça uma descrição.")
            else:
                with st.spinner("Analisando o arquivo localmente... (O aplicativo ficará bloqueado durante a análise)"):
                    # CHAMA A FUNÇÃO LOCAL DIRETAMENTE
                    result = analyze_csv_local(unique_filename, description)

                if "error" in result:
                    st.error(f"Erro na análise: {result['error']}")
                else:
                    st.success("Análise concluída com sucesso!")
                    
                    st.header("1. DDL SQL Gerado (SQLite)")
                    st.code(result['create_table'], language='sql')
                    
                    st.header("2. Análise Detalhada das Colunas")
                    analysis_df = pd.DataFrame(result['analysis'])
                    analysis_df = analysis_df[['column', 'type', 'min', 'max', 'min_len', 'max_len']]
                    
                    st.dataframe(analysis_df.fillna('-').style.format({
                        'min': lambda x: f'{x:.4f}' if isinstance(x, (float)) else x,
                        'max': lambda x: f'{x:.4f}' if isinstance(x, (float)) else x
                    }), use_container_width=True)
                    
                    st.caption(f"Descrição da análise: {result['description']}")
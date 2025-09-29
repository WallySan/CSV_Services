import os
import uuid
import zipfile
import requests
import streamlit as st

# Pasta de destino
DATA_DIR = "./dados"
os.makedirs(DATA_DIR, exist_ok=True)

st.title("Upload de Arquivo CSV/ZIP")

# Upload de arquivo
uploaded_file = st.file_uploader("Escolha um arquivo (.csv ou .zip)", type=["csv", "zip"])

if uploaded_file is not None:
    # Gera UUID para o arquivo
    file_ext = uploaded_file.name.split('.')[-1].lower()
    unique_filename = f"{uuid.uuid4()}.{file_ext}"
    file_path = os.path.join(DATA_DIR, unique_filename)
    
    # Salva o arquivo
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    # Se for zip, verifica se contém apenas CSV
    if file_ext == "zip":
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            csv_files = [f for f in zip_ref.namelist() if f.endswith('.csv')]
            if not csv_files:
                st.error("O arquivo ZIP não contém arquivos CSV.")
            else:
                # Extrai os CSVs para a mesma pasta com UUID
                for csv_file in csv_files:
                    extracted_path = os.path.join(DATA_DIR, f"{uuid.uuid4()}_{os.path.basename(csv_file)}")
                    with open(extracted_path, "wb") as f_out:
                        f_out.write(zip_ref.read(csv_file))
                st.success(f"ZIP processado com sucesso! {len(csv_files)} arquivo(s) CSV extraído(s).")
    
    st.success(f"Arquivo enviado com sucesso: {unique_filename}")
    
    # Campo de descrição
    description = st.text_input("Descrição do arquivo")
    
    # Botão processar
    if st.button("Processar") and description:
        endpoint_url = "http://SEU_ENDPOINT_AQUI"  # substituir pelo endpoint real
        files = {'file': open(file_path, 'rb')}
        data = {'description': description, 'filename': unique_filename}
        try:
            response = requests.post(endpoint_url, files=files, data=data)
            if response.status_code == 200:
                st.success("Arquivo enviado para processamento com sucesso!")
            else:
                st.error(f"Erro no envio: {response.status_code} {response.text}")
        except Exception as e:
            st.error(f"Falha ao enviar: {e}")

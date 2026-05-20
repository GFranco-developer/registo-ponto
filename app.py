#G.Franco-developer

"""
╔══════════════════════════════════════════════════════════════╗
║         REGISTO DE PONTO — RESTAURAÇÃO                       ║
║         Opção A: Streamlit + Google Sheets                   ║
║         Valor hora: 7€                                       ║
╚══════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import gspread
from datetime import datetime

# ──────────────────────────────────────────────
# CONFIGURAÇÃO
# ──────────────────────────────────────────────
VALOR_HORA = 7.0  # € por hora
SHEET_NAME = "Registo de Ponto"  # Nome da folha no Google Sheets (exato!)


# ──────────────────────────────────────────────
# LIGAÇÃO AO GOOGLE SHEETS
# ──────────────────────────────────────────────
def conectar_sheets():
    """
    Liga ao Google Sheets usando as credenciais guardadas.
    No Streamlit Cloud, as credenciais vêm de st.secrets.
    Usa a API moderna do gspread (v6+): ServiceAccountCredentials.
    """
    try:
        # Streamlit Cloud: lê de st.secrets
        creds_dict = dict(st.secrets["gcp_service_account"])
        # Garante que private_key tem newlines reais (o TOML pode escapar \n)
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        client = gspread.service_account_from_dict(creds_dict)
    except KeyError:
        # Fallback: ficheiro local credenciais.json
        client = gspread.service_account(filename="credenciais.json")
    return client


def obter_folha(client):
    """Abre a folha de cálculo e devolve o primeiro separador."""
    try:
        spreadsheet = client.open(SHEET_NAME)
    except gspread.exceptions.SpreadsheetNotFound:
        raise Exception(
            f"Folha '{SHEET_NAME}' não encontrada. "
            "Verifica: 1) o nome é exatamente 'Registo de Ponto' "
            "2) partilhaste com o email do service account."
        )
    worksheet = spreadsheet.sheet1
    return worksheet


def garantir_cabecalhos(worksheet):
    """Cria os cabeçalhos se a folha estiver vazia."""
    primeira_linha = worksheet.row_values(1)
    if not primeira_linha:
        cabecalhos = ["Data", "Hora Entrada", "Hora Saída", "Total Horas", "Ganho (€)"]
        worksheet.append_row(cabecalhos)


# ──────────────────────────────────────────────
# LÓGICA DE REGISTO
# ──────────────────────────────────────────────
def registar_entrada(worksheet):
    """
    Regista a hora de entrada:
    - Guarda Data + Hora Entrada numa nova linha
    - Deixa Saída/Horas/Ganho em branco (preenchidos na saída)
    """
    agora = datetime.now()
    data = agora.strftime("%d/%m/%Y")
    hora = agora.strftime("%H:%M:%S")

    worksheet.append_row([data, hora, "", "", ""])
    return data, hora


def registar_saida(worksheet):
    """
    Regista a hora de saída:
    - Encontra a última linha com entrada mas sem saída
    - Calcula horas trabalhadas e ganho do dia
    """
    todos_registos = worksheet.get_all_values()

    # Procura a última linha com entrada mas sem saída (ignora cabeçalho)
    linha_idx = None
    for i in range(len(todos_registos) - 1, 0, -1):  # de trás para a frente, salta cabeçalho
        linha = todos_registos[i]
        # Verifica: tem hora de entrada (col 2) mas não tem saída (col 3)
        if len(linha) >= 2 and linha[1] and (len(linha) < 3 or not linha[2]):
            linha_idx = i + 1  # +1 porque gspread começa em 1
            hora_entrada_str = linha[1]
            data_str = linha[0]
            break

    if linha_idx is None:
        return None, None, None, None  # Nenhuma entrada em aberto

    agora = datetime.now()
    hora_saida_str = agora.strftime("%H:%M:%S")

    # Calcula total de horas
    fmt = "%H:%M:%S"
    entrada = datetime.strptime(hora_entrada_str, fmt)
    saida = datetime.strptime(hora_saida_str, fmt)
    delta = saida - entrada
    total_horas = delta.total_seconds() / 3600  # converte para horas decimais
    total_horas_fmt = f"{total_horas:.2f}"

    # Calcula ganho
    ganho = total_horas * VALOR_HORA
    ganho_fmt = f"{ganho:.2f}"

    # Atualiza a linha no Google Sheets (colunas 3, 4 e 5)
    worksheet.update_cell(linha_idx, 3, hora_saida_str)   # Hora Saída
    worksheet.update_cell(linha_idx, 4, total_horas_fmt)  # Total Horas
    worksheet.update_cell(linha_idx, 5, ganho_fmt)        # Ganho (€)

    return data_str, hora_saida_str, total_horas_fmt, ganho_fmt


def verificar_entrada_aberta(worksheet):
    """Verifica se há uma entrada sem saída registada."""
    todos_registos = worksheet.get_all_values()
    for linha in reversed(todos_registos[1:]):  # ignora cabeçalho
        if len(linha) >= 2 and linha[1] and (len(linha) < 3 or not linha[2]):
            return True, linha[0], linha[1]  # data e hora de entrada
    return False, None, None


def obter_ultimos_registos(worksheet, n=5):
    """Devolve os últimos N registos completos (com saída)."""
    todos = worksheet.get_all_values()
    if len(todos) <= 1:
        return []
    dados = todos[1:]  # ignora cabeçalho
    completos = [r for r in dados if len(r) >= 5 and r[4]]  # só com ganho preenchido
    return completos[-n:][::-1]  # últimos N, mais recente primeiro


# ──────────────────────────────────────────────
# INTERFACE STREAMLIT
# ──────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="Registo de Ponto",
        page_icon="🍽️",
        layout="centered",
    )

    # ── CSS personalizado para iPhone ──
    st.markdown("""
    <style>
        /* Fundo escuro elegante */
        .stApp { background-color: #1a1a2e; }

        /* Título principal */
        h1 { color: #e8c97a !important; font-size: 1.6rem !important; text-align: center; }

        /* Subtítulo */
        h3 { color: #a8b2c8 !important; text-align: center; }

        /* Botões grandes para toque no iPhone */
        .stButton > button {
            width: 100%;
            height: 80px;
            font-size: 1.2rem !important;
            font-weight: bold;
            border-radius: 16px;
            border: none;
            margin: 8px 0;
            cursor: pointer;
            transition: transform 0.1s;
        }
        .stButton > button:active { transform: scale(0.97); }

        /* Caixa de status */
        .status-box {
            background: #16213e;
            border-radius: 12px;
            padding: 16px;
            margin: 12px 0;
            border-left: 4px solid #e8c97a;
            color: #e0e0e0;
        }

        /* Tabela de registos */
        .registo-item {
            background: #0f3460;
            border-radius: 10px;
            padding: 12px;
            margin: 6px 0;
            color: #e0e0e0;
            font-size: 0.9rem;
        }

        /* Ocultar elementos do Streamlit que não precisamos */
        #MainMenu, footer, header { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)

    # ── Cabeçalho ──
    st.markdown("# 🍽️ Registo de Ponto")
    st.markdown("### Restauração · 7€/hora")
    st.divider()

    # ── Inicializa ligação (com cache para não reconectar sempre) ──
    @st.cache_resource
    def get_worksheet():
        client = conectar_sheets()
        ws = obter_folha(client)
        garantir_cabecalhos(ws)
        return ws

    try:
        worksheet = get_worksheet()
    except Exception as e:
        st.error(f"❌ Erro ao ligar ao Google Sheets: {e}")
        st.info("Verifica as tuas credenciais e o nome da folha.")
        return

    # ── Verifica estado atual ──
    tem_entrada, data_entrada, hora_entrada = verificar_entrada_aberta(worksheet)

    # ── Mostra estado atual ──
    if tem_entrada:
        st.markdown(f"""
        <div class="status-box">
            🟢 <strong>EM SERVIÇO</strong><br>
            Entrada registada: {data_entrada} às {hora_entrada}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="status-box">
            ⚪ <strong>FORA DE SERVIÇO</strong><br>
            Ainda não registaste a entrada de hoje.
        </div>
        """, unsafe_allow_html=True)

    st.markdown("")  # espaço

    # ── Botão ENTRADA ──
    col1, col2 = st.columns(2)

    with col1:
        entrada_disabled = tem_entrada  # desativa se já há entrada aberta
        if st.button("🟢 ENTRADA", disabled=entrada_disabled, use_container_width=True):
            with st.spinner("A registar entrada..."):
                data, hora = registar_entrada(worksheet)
                # Limpa o cache para atualizar o estado
                get_worksheet.clear()
            st.success(f"✅ Entrada registada!\n{data} às {hora}")
            st.rerun()

    # ── Botão SAÍDA ──
    with col2:
        saida_disabled = not tem_entrada  # desativa se não há entrada aberta
        if st.button("🔴 SAÍDA", disabled=saida_disabled, use_container_width=True):
            with st.spinner("A calcular horas..."):
                resultado = registar_saida(worksheet)
                data, hora_s, horas, ganho = resultado
                get_worksheet.clear()

            if data is None:
                st.error("❌ Nenhuma entrada em aberto encontrada.")
            else:
                st.success(
                    f"✅ Saída registada!\n"
                    f"⏱️ {horas} horas trabalhadas\n"
                    f"💶 Ganho: {ganho}€"
                )
                st.balloons()
            st.rerun()

    st.divider()

    # ── Últimos registos ──
    st.markdown("### 📋 Últimos Registos")
    registos = obter_ultimos_registos(worksheet, n=5)

    if not registos:
        st.info("Ainda não há registos completos.")
    else:
        for r in registos:
            data   = r[0] if len(r) > 0 else "-"
            h_ent  = r[1] if len(r) > 1 else "-"
            h_sai  = r[2] if len(r) > 2 else "-"
            horas  = r[3] if len(r) > 3 else "-"
            ganho  = r[4] if len(r) > 4 else "-"
            st.markdown(f"""
            <div class="registo-item">
                📅 <strong>{data}</strong> &nbsp;|&nbsp;
                ▶ {h_ent} &nbsp;→&nbsp; ◼ {h_sai}<br>
                ⏱️ {horas}h &nbsp;·&nbsp; 💶 {ganho}€
            </div>
            """, unsafe_allow_html=True)

    # ── Botão de atualização ──
    st.markdown("")
    if st.button("🔄 Atualizar Dados", use_container_width=True):
        get_worksheet.clear()
        st.rerun()


if __name__ == "__main__":
    main()

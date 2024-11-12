import streamlit as st
from st_click_detector import click_detector

from longcite import LongCiteModel


st.set_page_config(layout="wide", page_title="LongCite")


@st.cache_resource
def load_model():
    model_path = "models/LongCite-llama3.1-8B-Q4_K_M.gguf"
    tokenizer_path = "THUDM/LongCite-llama3.1-8b"
    model = LongCiteModel(model=model_path)
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_path, trust_remote_code=True)
    return tokenizer, model


# Styles
st.markdown("""
<style>
    .block-container {
                    padding-top: 1rem;
                    padding-bottom: 0rem;
                    padding-left: 5rem;
                    padding-right: 5rem;
    }
    .main-title {
        text-align: center;
        font-size: 3.5rem;
        color: #1a73e8;
        margin: 4rem 0;
        font-weight: bold;
    }
    .subtitle {
        text-align: center;
        color: #5f6368;
        margin-bottom: 2rem;
    }
    .search-box {
        width: 100%;
        max-width: 600px;
        margin: 0 auto;
    }
    .centered-text {
        text-align: center;
    }
    .stButton>button {
        background-color: #1a73e8;
        color: white;
        border-radius: 20px;
        padding: 0.5rem 2rem;
        border: none;
    }
</style>
""", unsafe_allow_html=True)

# Main title
st.markdown('<h1 class="main-title">LongCite</h1>', unsafe_allow_html=True)

# Search interface
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    query = st.text_input(
        "", placeholder="Ask your question...", key="search_box")
    col_a, col_b, col_c = st.columns([1, 2, 1])
    with col_b:
        submit = st.button("Search", use_container_width=True)


# Citation rendering functions
def process_text(text):
    special_char = {
        '&': '&amp;', '\'': '&apos;', '"': '&quot;',
        '<': '&lt;', '>': '&gt;', '\n': '<br>',
    }
    for x, y in special_char.items():
        text = text.replace(x, y)
    return text


html_styles = """<style>
    .reference { color: blue; text-decoration: underline; }
    .highlight { background-color: yellow; }
    .label { font-family: sans-serif; font-size: 16px; font-weight: bold; }
    .Bold { font-weight: bold; }
    .statement { background-color: lightgrey; }
</style>"""


def convert_to_html(statements, clicked=-1):
    html = html_styles + '<br><span class="label">Answer:</span><br>\n'
    all_cite_html = []
    clicked_cite_html = None
    idx = 0

    for i, js in enumerate(statements):
        statement, citations = process_text(js['statement']), js['citation']
        html += f"""<span class="{'statement' if clicked == i else ''}">{statement}</span>"""

        if citations:
            cite_html = []
            idxs = []
            for c in citations:
                idx += 1
                idxs.append(str(idx))
                cite = '[Sentence: {}-{}\t|\tChar: {}-{}]<br>\n<span {}>{}</span>'.format(
                    c['start_sentence_idx'], c['end_sentence_idx'],
                    c['start_char_idx'], c['end_char_idx'],
                    'class="highlight"' if clicked == i else "",
                    process_text(c['cite'].strip())
                )
                cite_html.append(
                    f"""<span><span class="Bold">Snippet [{idx}]:</span><br>{cite}</span>""")

            all_cite_html.extend(cite_html)
            html += """ <a href='#' class="reference" id={}>[{}]</a>""".format(
                i, ','.join(idxs))
        html += '\n'

        if clicked == i:
            clicked_cite_html = html_styles + """<br><span class="label">Citations of current statement:</span><br>
                <div style="overflow-y: auto; padding: 20px; border: 0px dashed black; border-radius: 6px; 
                background-color: #EFF2F6;">{}</div>""".format("<br><br>\n".join(cite_html))

    all_cite_html = html_styles + """<br><span class="label">All citations:</span><br>
        <div style="overflow-y: auto; padding: 20px; border: 0px dashed black; border-radius: 6px; 
        background-color: #EFF2F6;">{}</div>""".format("<br><br>\n".join(all_cite_html)
                                                       .replace('<span class="highlight">', '<span>'))

    return html, all_cite_html, clicked_cite_html


@st.fragment
def render_answer(statements):
    answer_html, all_cite_html, clicked_cite_html = convert_to_html(
        statements,
        clicked=st.session_state.get("last_clicked", -1)
    )

    col1, col2 = st.columns([4, 4])
    with col1:
        clicked = click_detector(answer_html)
    with col2:
        if clicked_cite_html:
            st.html(clicked_cite_html)
        st.html(all_cite_html)

    if clicked != "":
        clicked = int(clicked)
        if "last_clicked" not in st.session_state or clicked != st.session_state["last_clicked"]:
            st.session_state["last_clicked"] = clicked
            st.rerun(scope='fragment')

statements = """Resumo: FaceLita é um jogo inovador destinado a oferecer suporte a crianças com alexitimia, uma condição que se caracteriza
pela dificuldade em identificar e expressar emoções de maneira apropriada, sendo especialmente prevalente em crianças
diagnosticadas com Transtorno do Espectro Autista (TEA). Concebido como uma ferramenta auxiliar em intervenções clínicas,
nosso principal objetivo é transformar o aprendizado das expressões faciais e emoções em uma jornada educativa e envolvente."""

render_answer(statements)
# Load model
tokenizer, model = load_model()

# Handle search
if submit and query:
    with st.spinner('Searching through documents...'):

        result = model.query_longcite(
            query,
            tokenizer=tokenizer,
            max_input_length=128000,
            max_new_tokens=1024
        )

        if result:
            statements = result['all_statements']
            render_answer(statements)

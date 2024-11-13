import streamlit as st
from longcite import LongCiteModel
from longcite import TextRetriever


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


st.markdown("""
<style>
  .block-container {
          padding-top: 1rem;
          padding-bottom: 0rem;
          padding-left: 5rem;
          padding-right: 5rem;
  }
  
  .answer-container {
          padding-top: 1rem;
          padding-bottom: 0rem;
          padding-left: 5rem;
          padding-right: 5rem;
          margin-bottom: 10rem;
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
  
  /* Citation tooltip styles */
  .citation-ref {
    color: blue;
    position: relative;
    cursor: pointer;
    text-decoration: none;
  }
  
  .citation-numbers {
    text-decoration:
    }
    
    .citation-brackets {
        text-decoration: none;
        color: blue;
    }
    
    .citation-tooltip {
        visibility: hidden;
        position: absolute;
        z-index: 1;
        bottom: 100%;
        left: 50%;
        transform: translateX(-50%);
        background-color: #EFF2F6;
        color: black;
        padding: 15px;
        border-radius: 6px;
        width: 300px;
        max-height: 300px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        opacity: 1;
        transition: opacity 0.3s;
        overflow: scroll;
    }
    
    .citation-ref:hover .citation-tooltip {
        visibility: visible;
        opacity: 1;
    }
    

    .citation-content {
        margin: 5px 0;
        font-size: 14px;
    }
    
    .citation-metadata {
        font-size: 12px;
        color: #666;
        margin-top: 5px;
    }
</style>


    
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-title">LongCite</h1>', unsafe_allow_html=True)

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    query = st.text_input(
        "", placeholder="Ask your question...", key="search_box")
    col_a, col_b, col_c = st.columns([1, 2, 1])
    with col_b:
        submit = st.button("Search", use_container_width=True)


def process_text(text):
    special_char = {
        '&': '&amp;', '\'': '&apos;', '"': '&quot;',
        '<': '&lt;', '>': '&gt;', '\n': '<br>',
    }
    for x, y in special_char.items():
        text = text.replace(x, y)
    return text


def convert_to_html(statements):
    html = '<div class="answer-container">\n<span class="label"></span><br>\n'

    for i, js in enumerate(statements):
        if not js['statement']:
            continue

        statement, citations = process_text(js['statement']), js['citation']
        html += f"<span>{statement}</span>"

        if citations:
            citation_tooltips = []
            citation_refs = []

            for idx, c in enumerate(citations, 1):
                cite_content = process_text(c['cite'].strip())
                metadata = f"[Sentence: {c['start_sentence_idx']}-{c['end_sentence_idx']} | Char: {c['start_char_idx']}-{c['end_char_idx']} | url : {c['url']}]"

                citation_tooltips.append(f"""
                    <div class="citation-content">{cite_content}</div>
                    <div class="citation-metadata">{metadata}</div>
                """)

            tooltip_content = "<br>".join(citation_tooltips)
            citation_numbers = ','.join(str(x)
                                        for x in range(1, len(citations) + 1))
            html += f""" <span class="citation-ref" onclick=" this.classList.toggle('ativa');">
                        <span class="citation-brackets">[</span><span class="citation-numbers">{citation_numbers}</span><span class="citation-brackets">]</span>
                        <span class="citation-tooltip" >{tooltip_content}</span>
                    </span>"""

        html += "\n"

    html += '</div>'

    return html


@st.fragment
def render_answer(statements):
    answer_html = convert_to_html(statements)
    st.markdown(answer_html, unsafe_allow_html=True)


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

import streamlit as st

from longcite import TextRetriever
import fitz
st.set_page_config(layout="wide", page_title="LongCite - Upload")


def convert_to_txt(file):
    """Convert the uploaded file to text based on its type."""
    doc_type = file.name.split(".")[-1].strip()
    try:
        if doc_type in ["txt", "md", "py"]:
            data = [file.read().decode('utf-8')]
        elif doc_type == "pdf":
            with  fitz.open(stream=file.read(), filetype="pdf") as pdf:
              data = []
              for page_num in range(len(pdf)):
                  page = pdf.load_page(page_num)
                  data.append(page.get_text()) 
        else:
            st.error(f"ERROR: Unsupported document type: {doc_type}")
            return None
        return "\n\n".join(data)
    except Exception as e:
        st.error(f"Failed to process the file: {e}")
        return None


st.title("📚 Document Upload")

st.markdown("""
<style>
    .upload-section {
        background-color: #f8f9fa;
        padding: 2rem;
        border-radius: 10px;
        margin: 2rem 0;
    }
    .stButton>button {
        background-color: #1a73e8;
        color: white;
    }
    .file-content {
        background-color: #f1f3f4;
        padding: 1rem;
        border-radius: 5px;
        white-space: pre-wrap;
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

if 'uploaded_docs' not in st.session_state:
    st.session_state['uploaded_docs'] = {}

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    uploaded_file = st.file_uploader("Upload a document (supported types: pdf, txt, md, py)")

if uploaded_file:

    content = convert_to_txt(uploaded_file)
    
    if content:
        
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("Upload", use_container_width=True):
              
                for filename, content in st.session_state['uploaded_docs'].items():
                    TextRetriever.add_document({
                        "name": filename,
                        "content": content,
                        "url": f"file:///{filename}"
                    })
                st.success("✅ file successfully uploaded!")
                st.session_state['uploaded_docs'].clear()
        
        st.session_state['uploaded_docs'][uploaded_file.name] = content

        show_preview = st.checkbox("Show Preview", value=True)
        if show_preview:
            st.text_area("Document Content", content, height=270)

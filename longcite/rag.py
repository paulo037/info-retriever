import re
from nltk.tokenize.punkt import PunktSentenceTokenizer
from chromadb import PersistentClient, Collection
import sqlite3
import uuid
from rank_bm25 import BM25Okapi
from nltk.tokenize import word_tokenize
import nltk
from typing import TypedDict
nltk.download('punkt')
nltk.download('punkt_tab')


class Document(TypedDict):
    id: str
    name: str
    content: str
    url: str


class TextRetriever:
    client: PersistentClient = PersistentClient(path='db/chroma_db')
    conn: sqlite3.Connection = sqlite3.connect(
        'db/rag_db.sqlite3', check_same_thread=False)
    cur: sqlite3.Cursor = conn.cursor()
    bm25: BM25Okapi
    documents: dict
    collection: Collection
    inialized = False

    @staticmethod
    def init_bm25():
        with TextRetriever.conn:
            TextRetriever.cur.execute("SELECT id, content, name FROM document")
            docs = TextRetriever.cur.fetchall()
            TextRetriever.documents = [
                {"id": d[0], "name":d[2]} for d in docs]

        contents = [d[1] for d in docs]
        tokenized_corpus = [word_tokenize(doc) for doc in contents]
        if tokenized_corpus:
            TextRetriever.bm25 = BM25Okapi(tokenized_corpus)

    @staticmethod
    def init():
        if TextRetriever.inialized:
            return
        TextRetriever.inialized = True
        TextRetriever.cur.execute(
            '''CREATE TABLE IF NOT EXISTS sentence (id INTEGER PRIMARY KEY AUTOINCREMENT, document_id TEXT, chunk_id TEXT, content TEXT, start INTEGER, end INTEGER, url TEXT, name)''')
        TextRetriever.cur.execute(
            '''CREATE TABLE IF NOT EXISTS document (id TEXT PRIMARY KEY, name TEXT, content TEXT, url TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        TextRetriever.conn.commit()
        TextRetriever.collection = TextRetriever.client.get_or_create_collection(
            "chunks")
        TextRetriever.init_bm25()

    @staticmethod
    def get_relevant_docs(query, min_doc_score):
        print(query)
        scores = TextRetriever.bm25.get_scores(word_tokenize(query))
        sorted_docs = sorted(zip(TextRetriever.documents, scores), key=lambda x: x[1], reverse=True)
        relevant_docs = [d['id'] for d, s in sorted_docs[:10] if s > min_doc_score]
        
        print("\n".join([d['name'] for d,_ in sorted_docs[:10]]))
        return relevant_docs

    @staticmethod
    def add_document(document: Document, sentence_per_block: int = 50, update_bm25 : bool = True) -> None:
        def text_split_by_punctuation(original_text, return_dict=False):
            text = original_text
            custom_sent_tokenizer = PunktSentenceTokenizer(text)
            punctuations = r"([。；！？])"  # For Chinese support

            separated = custom_sent_tokenizer.tokenize(text)
            separated = sum([re.split(punctuations, s) for s in separated], [])
            # Put the punctuations back to the sentence
            for i in range(1, len(separated)):
                if re.match(punctuations, separated[i]):
                    separated[i-1] += separated[i]
                    separated[i] = ''

            separated = [s for s in separated if s != ""]
            if len(separated) == 1:
                separated = original_text.split('\n\n')
            separated = [s.strip() for s in separated if s.strip() != ""]
            if not return_dict:
                return separated
            else:
                pos = 0
                res = []
                for i, sent in enumerate(separated):
                    st = original_text.find(sent, pos)
                    assert st != -1, sent
                    ed = st + len(sent)
                    res.append(
                        {
                            'c_idx': i,
                            'content': sent,
                            'start': st,
                            'end': ed,
                        }
                    )
                    pos = ed
                return res

        doc_id = str(uuid.uuid4())
        TextRetriever.cur.execute("INSERT INTO document (id, name, content, url) VALUES (?, ?, ?, ?)", (
            doc_id, document['name'], document['content'], document['url']))
        TextRetriever.conn.commit()
        
        if(update_bm25):
          TextRetriever.init_bm25()

        context = document['content']
        sentences = text_split_by_punctuation(context, return_dict=True)
        chunks = []
        for i in range(0, len(sentences), sentence_per_block-1):
            block = sentences[i:i+sentence_per_block]
            if not block:
                break

            chunk_id = str(uuid.uuid4())

            with TextRetriever.conn:
                for s in block:
                    TextRetriever.cur.execute("INSERT INTO sentence (document_id, chunk_id, content, start, end, name, url) VALUES (?, ?, ?, ?, ?, ?, ?)", (
                        doc_id, chunk_id, s['content'], s['start'], s['end'], document['name'], document['url']))

            chunks.append({
                'content': context[block[0]['start']:block[-1]['end']],
                'chunk_id': chunk_id,
                'document_id': doc_id,
            })

        for i, block in enumerate(chunks):
            TextRetriever.collection.add(
                documents=[block['content']],
                ids=[block['chunk_id']],
                metadatas=[{'document_id': block['document_id'],
                            'chunk_id': block['chunk_id']}],
            )

    @staticmethod
    def search(query, min_doc_score=7, top_k_chunks=5):

        relevant_docs = TextRetriever.get_relevant_docs(query, min_doc_score)
        if not relevant_docs:
            return []

        results = TextRetriever.collection.query(
            query_texts=[query],
            n_results=top_k_chunks,
            where={"document_id": {"$in": relevant_docs}}
        )

        with TextRetriever.conn:

            ids = results['ids'][0]
            placeholders = ', '.join(['?'] * len(ids))
            TextRetriever.cur.execute(
                f"SELECT content, start, end, name, url FROM sentence WHERE chunk_id IN ({placeholders})", ids)
            sentences = {str(s[1]): {'content': s[0], 'start': s[1], 'end': s[2], 'name': s[3], 'url': s[4]}
                         for s in TextRetriever.cur.fetchall()}

        return [sentences[id] for id in sorted(sentences.keys())]
    
    @staticmethod
    def get_all_urls():
        with TextRetriever.conn:
            TextRetriever.cur.execute("SELECT url FROM document")
            docs = TextRetriever.cur.fetchall()
            return [d[0] for d in docs]
      


TextRetriever.init()

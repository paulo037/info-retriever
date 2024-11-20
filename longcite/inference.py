from llama_cpp import Llama, LlamaTokenizer
from .rag import TextRetriever
import re


class LongCiteModel():
    def __init__(self, model):
        self.model = Llama(model, n_ctx=8192 * 4, n_gpu_layers=-1)
        self.generation_args = {
            "temperature": 0.3,
            "top_p": 0.7,
            "max_tokens": 2048,
            "stop": ["<|user|>", "<|observation|>"],
        }

    def chat(self, tokenizer, query: str, history=None, role="user",
             max_new_tokens=None, top_p=0.7, temperature=0.95):
        if history is None:
            history = []
        
        print(query)
        history.append({"role": role, "content": query})
        response = self.model.create_chat_completion(
            history, **self.generation_args)['choices'][0]['message']['content']
        
        return response, history

    def query_longcite(self,  query, tokenizer, max_input_length=4096, max_new_tokens=1024, temperature=0.95):

        def get_prompt(question):
            
            sentences = TextRetriever.search(question)
            question = f"[responda em português-br] {question}"
            splited_context =  "".join([f"<C{i}>"+s['content'] for i, s in enumerate(sentences)])


            # Construir o prompt final com o contexto recuperado
            prompt = '''Por favor, responda à pergunta do usuário com base no documento a seguir. ''' + \
                    '''Quando uma frase S em sua resposta utilizar informações de alguns trechos do documento (ou seja, <C{s1}>-<C_{e1}>, <C{s2}>-<C{e2}>, ...), ''' + \
                    '''por favor, adicione esses números de trechos à S no formato "<statement>{S}<cite>[{s1}-{e1}][{s2}-{e2}]...</cite></statement>". ''' + \
                    '''Você deve responder em português-br.\n\n[Início do Documento]\n%s\n[Fim do Documento]\n\n%s''' % (splited_context, question)

            return prompt, sentences, splited_context

        def get_citations(statement, sents):
            c_texts = re.findall(r'<cite>(.*?)</cite>', statement, re.DOTALL)
            spans = sum([re.findall(r"\[([0-9]+\-[0-9]+)\]",
                        c_text, re.DOTALL) for c_text in c_texts], [])
            statement = re.sub(r'<cite>(.*?)</cite>', '',
                               statement, flags=re.DOTALL)
            merged_citations = []
            for i, s in enumerate(spans):
                try:
                    st, ed = [int(x) for x in s.split('-')]
                    if st > len(sents) - 1 or ed < st:
                        continue
                    st, ed = max(0, st), min(ed, len(sents)-1)
                    assert st <= ed, str(c_texts) + '\t' + str(len(sents))
                    if len(merged_citations) > 0 and st == merged_citations[-1]['end_sentence_idx'] + 1:
                        merged_citations[-1].update({
                            "end_sentence_idx": ed,
                            'end_char_idx': sents[ed]['end'],
                            'name': sents[ed]['name'],
                            'url': sents[ed]['url'],
                            'cite': ''.join([x['content'] for x in sents[merged_citations[-1]['start_sentence_idx']:ed+1]]),
                        })
                    else:
                        merged_citations.append({
                            "start_sentence_idx": st,
                            "end_sentence_idx": ed,
                            "start_char_idx":  sents[st]['start'],
                            'end_char_idx': sents[ed]['end'],
                            'name': sents[ed]['name'],
                            'url': sents[ed]['url'],
                            'cite': ''.join([x['content'] for x in sents[st:ed+1]]),
                        })
                except:
                    print(c_texts, len(sents), statement)
                    raise
            return statement, merged_citations[:3]

        def postprocess(answer, sents, splited_context):
            res = []
            pos = 0
            new_answer = ""
            while True:
                st = answer.find("<statement>", pos)
                if st == -1:
                    st = len(answer)
                ed = answer.find("</statement>", st)
                statement = answer[pos:st]
                if len(statement.strip()) > 5:
                    res.append({
                        "statement": statement,
                        "citation": []
                    })
                    new_answer += f"<statement>{statement}<cite></cite></statement>"
                else:
                    res.append({
                        "statement": statement,
                        "citation": None,
                    })
                    new_answer += statement

                if ed == -1:
                    break

                statement = answer[st+len("<statement>"):ed]
                if len(statement.strip()) > 0:
                    statement, citations = get_citations(statement, sents)
                    res.append({
                        "statement": statement,
                        "citation": citations
                    })
                    c_str = ''.join(
                        ['[{}-{}]'.format(c['start_sentence_idx'], c['end_sentence_idx']) for c in citations])
                    new_answer += f"<statement>{statement}<cite>{c_str}</cite></statement>"
                else:
                    res.append({
                        "statement": statement,
                        "citation": None,
                    })
                    new_answer += statement
                pos = ed + len("</statement>")
            return {
                "answer": new_answer.strip(),
                "statements_with_citations": [x for x in res if x['citation'] is not None],
                "splited_context": splited_context.strip(),
                "all_statements": res,
            }

        def truncate_from_middle(prompt, max_input_length=None, tokenizer=None):
            if max_input_length is None:
                return prompt
            else:
                assert tokenizer is not None
                tokenized_prompt = tokenizer.encode(
                    prompt, special=False)
                if len(tokenized_prompt) > max_input_length:
                    half = int(max_input_length/2)
                    prompt = tokenizer.decode(tokenized_prompt[:half])+tokenizer.decode(
                        tokenized_prompt[-half:])
                return prompt

        prompt, sents, splited_context = get_prompt(query)

        prompt = truncate_from_middle(prompt, None, tokenizer)

        output, _ = self.chat(tokenizer, prompt, history=[],
                              max_new_tokens=max_new_tokens, temperature=temperature)

        result = postprocess(output, sents, splited_context)
        
        return result

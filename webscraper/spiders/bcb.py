from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from scrapy.http import HtmlResponse
from scrapy.http import Request
import time
import scrapy
import fitz
from longcite import TextRetriever
from urllib.parse import urlparse, parse_qs, urlencode
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from scrapy.http import HtmlResponse
import requests

def create_url(base_url, params):
    query_string = urlencode(params)
    return f"{base_url}?{query_string}"


def get_params(url):
    parsed_url = urlparse(url)
    params = parse_qs(parsed_url.query)
    params = {k: (int(v[0]) if v[0].isdigit() else v[0]) if len(v) == 1 else v for k, v in params.items()}
    return params

number_of_documents = 0

class BCBCrawlerSpider(scrapy.Spider):
    name = 'bcb_crawler'
    allowed_domains = ['bcb.gov.br']
    base_url = "https://www.bcb.gov.br/estabilidadefinanceira/buscanormas"

    comum_params = {
        "dataInicioBusca": "01/01/1950",
        "dataFimBusca": "18/11/2024",
        "startRow": 0,
        "refinadorRevogado": 0,
    }

    instrucao_normativa = create_url(base_url, {**comum_params, "tipoDocumento": "Instrução Normativa BCB"})
    resolucao_bcb       = create_url(base_url, {**comum_params, "tipoDocumento": "Resolução BCB"})
    carta_circular      = create_url(base_url, {**comum_params, "tipoDocumento": "Carta Circular"})
    
    visited_urls = set(TextRetriever.get_all_urls())

    #start_urls = [carta_circular, instrucao_normativa, resolucao_bcb]
    start_urls = [instrucao_normativa]


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        
        chrome_options = Options()
        
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(
            service=Service(), options=chrome_options)

    def parse(self, response):
        if (response.url in self.visited_urls):
            return
        
        global number_of_documents
        number_of_documents += 1


        self.driver.get(response.url)
        time.sleep(10)


        rendered_html = self.driver.page_source
        
        response = HtmlResponse(  url=response.url, body=rendered_html, encoding='utf-8')

        
        # If the URL is a search page, extract the links to the documents
        if ("buscanormas" in response.url):
            self.logger.info(f"Processing search page: {response.url}")
            have_row = False
            for next_page in response.xpath("//a/@href").getall():
                next_page = response.urljoin(next_page)
                if ("exibenormativo" in next_page):
                    yield Request(next_page, callback=self.parse)
                    have_row = True
                    
            if(have_row):
                params = get_params(str(response.url))              
                params["startRow"] += 15
                
                url_with_new_rows = create_url(self.base_url, params)
                
                yield Request(url_with_new_rows, callback=self.parse, dont_filter=True)
            
        # If the URL is a document page, extract the content
        else:
          self.logger.info(f"Processing content from URL: {response.url}")
          
          params = get_params(response.url)
          name = params["tipo"] if "tipo" in params else "unknown"
          name += f"_{params['numero']}" if "numero" in params else "_unknown"
          url = response.url
          
          pdf_link = None
          
          
          for next_page in response.xpath("//a/@href").getall():
            if("normativos.bcb.gov.br/Lists/Normativos/Attachments" in next_page):
                pdf_link = next_page
                break
          
          if pdf_link != None:
            
              url = pdf_link
              url_parts = url.split("/")
              name = url_parts[-1].split(".")[0] if url_parts[-1] else url_parts[-2].split(".")[0]
              
              try:
                  response = requests.get(pdf_link, timeout=15)
                  if response.status_code == 200 and response.headers['Content-Type'] == 'application/pdf':

                      with fitz.open(stream=response.content, filetype="pdf") as pdf:
                          data = []
                          for page_num in range(len(pdf)):
                              page = pdf[page_num]
                              data.append(page.get_text())
                          final_text = "\n\n".join(data)                          
                  else:
                      self.logger.info(f"Invalid content type or status code: {response.status_code}")
              
              except Exception as e:
                  self.logger.info(f"Error processing PDF from URL {url}: {e}")
                  
          else:
              text = response.xpath('//div[@class="corpoNormativo"]//text()').getall()
              cleaned_text = [line.strip() for line in text if line.strip()]
              final_text = "\n".join(cleaned_text)

            
              
          TextRetriever.add_document({
              "name": name,
              "url": url,
              "content": final_text
          },  update_bm25=False)
                    
    def closed(self, reason):
        self.driver.quit()

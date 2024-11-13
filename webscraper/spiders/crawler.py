import scrapy
from scrapy.http import Request
import fitz
import sys
import os
from longcite import TextRetriever

number_of_documents = 0
class UfvCrawlerSpider(scrapy.Spider):
    name = 'ufv_crawler'
    allowed_domains = ['sre.caf.ufv.br']
    start_urls = ['https://sre.caf.ufv.br']
    visited_urls = set(TextRetriever.get_all_urls())

    def parse(self, response):
        if(response.url in self.visited_urls):
            return
          
        self.visited_urls.add(response.url)
        
        global number_of_documents
        number_of_documents += 1
        self.logger.info(f"Number of documents: {number_of_documents}, URL: {response.url}")
        if response.headers.get('Content-Type').decode().startswith('text/html'):

            response = response.replace(
                body=self.remove_scripts_styles(response.body.decode()))

            text = response.xpath("//body//text()").getall()

            cleaned_text = [line.strip() for line in text if line.strip()]
            final_text = "\n".join(cleaned_text)
            
            url_parts = response.url.split("/")
            name = url_parts[-1].split(".")[0] if url_parts[-1] else url_parts[-2].split(".")[0]

            
            url = response.url

            TextRetriever.add_document({
                "name": name,
                "url": url,
                "content": final_text
            },  update_bm25=False)

            for next_page in response.xpath("//a/@href").getall():
                next_page = response.urljoin(next_page)
                yield Request(next_page, callback=self.parse)

        else:

            self.extract_and_process_file_content(response)

    def remove_scripts_styles(self, html):
        """Remove <script> and <style> tags from the HTML."""
        from lxml import etree
        parser = etree.HTMLParser()
        tree = etree.HTML(html, parser)

        etree.strip_elements(tree, 'script', 'style', with_tail=False)

        return etree.tostring(tree, encoding='unicode', method='html')

    def extract_and_process_file_content(self, response):
        """Extract and process the content of non-HTML files directly from the response."""
        file_type = response.url.split('.')[-1].strip().lower()

        if file_type == "pdf":

            with fitz.open(stream=response.body, filetype="pdf") as pdf:
                data = []
                for page_num in range(len(pdf)):
                    page = pdf.load_page(page_num)
                    data.append(page.get_text())
            text_content = "\n\n".join(data)

        elif file_type in ["txt", "md", "py"]:
            text_content = response.body.decode('utf-8')

        else:
            self.logger.warning(f"Unsupported file type: {file_type}")
            text_content = None

        if text_content:
            url_parts = response.url.split("/")
            name = url_parts[-1] if url_parts[-1] else url_parts[-2]
            url = response.url

            TextRetriever.add_document({
                "name": name,
                "url": url,
                "content": text_content
            }, update_bm25=False)

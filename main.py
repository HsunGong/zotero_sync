
from collections import OrderedDict
import logging
import os
from pathlib import Path
import re
import sys
import time
from typing import Tuple, Union

logging.basicConfig(level=logging.INFO, format=("\033[1m\033[94m%(levelname)s\033[0m | \033[92m%(filename)s:%(lineno)d - %(funcName)s\033[0m \033[90m(%(asctime)s)\033[0m\n" "%(message)s"))

import pytz
from pyzotero import zotero
import requests

with open("LOCAL_DB", "r") as f:
    LOCAL_DB = set(f.read().strip("\n"))

# region localpdf
def download_pdf(pdf_url: str, p: Path):
    print(pdf_url, "save to", p)
    response = requests.get(pdf_url)

    # 确保请求是成功的
    if response.status_code == 200:
        with open(p, 'wb') as f:
            f.write(response.content)
        return p
    else:
        print("Error:", response.status_code)
        return ""
# endregion

# region parse-pdf
def extract_metadata_from_pdf(pdf_path, article_dict: dict):
    # article_dict = {}
    article_dict["__error"] = True
    if not pdf_path:
        return article_dict
    if os.path.exists(pdf_path):
        try:
            import PyPDF2
            PyPDF2.PdfReader(pdf_path.as_posix())
        except Exception as e:
            logging.warning("Error opening " + pdf_path.as_posix() + ":" + str(e))
            return article_dict
    
    import scipdf  # pip install scipdf_parser

    # from .gpt_academic.crazy_functions.pdf_fns.parse_pdf import parse_pdf
    # from .gpt_academic.crazy_functions.pdf_fns.report_gen_html import construct_html

    for _grobid_url in os.environ["GROBID_URLS"].split(","):
        if _grobid_url.endswith('/'): _grobid_url = _grobid_url.rstrip('/')
        res = requests.get(_grobid_url+'/api/isalive')
        if res.text != 'true':
            continue
    
        # https://grobid.readthedocs.io/en/latest/training/header/
        try:
            article = scipdf.parse_pdf(pdf_path.as_posix(), grobid_url=_grobid_url, fulltext=True, soup=True, return_coordinates=True)
            if "[GENERAL]" in article.text and "exception" in article.text:
                logging.debug(article_dict["title"] + ":" + article.text)
            else:
                break
        except Exception as e:
            logging.debug(article_dict["title"] + ":" + str(e))
    else:
        logging.warning("GROBID服务不可用，请修改config中的GROBID_URL，可修改成本地GROBID服务。")
        return article_dict

    try:    
        title = article.find("title", attrs={"type": "main"})
        title = title.text.strip() if title is not None else ""
        if article_dict.get("title") and article_dict["title"].lower() != title.lower():
            logging.debug("Title not match: %s vs %s", article_dict["title"], title)
        else:
            article_dict["title"] = title.title()

        if article_dict.get("date") and article_dict["date"] != scipdf.parse_date(article):
            logging.debug("Date not match: %s vs %s", article_dict["date"], scipdf.parse_date(article))
        else:
            article_dict["date"] = scipdf.parse_date(article)

        if not article_dict.get("abstractNote"):
            article_dict["abstractNote"] = scipdf.parse_abstract(article)

        doi = article.find("idno", attrs={"type": "DOI"})
        doi = doi.text if doi is not None else ""
        if article_dict.get("DOI") and article_dict["DOI"] != doi:
            logging.debug("DOI not match: %s vs %s", article_dict["DOI"], doi)
        else:
            article_dict["DOI"] = doi

        try:
            article_dict["tags"] = [{"tag": term_tag.text.lower()} for term_tag in article.find("keywords").find_all("term")]
        except:
            article_dict["tags"] = []
        article_dict["tags"].append({"tag": "arXiv"})
    except Exception as e:
        logging.warning(article_dict["title"] + ":" + str(e))
    
    # ignored by zotero upload
    article_dict.update({
        "__refs": [],
        "__authors": [],
        "__sections": [],
        "__figures": [],
        "__formulas": [],
    })
    try:
        article_dict["__refs"] = scipdf.parse_references(article)
    
        authors = []
        # Find all author tags with an affiliation child
        for author in article.find_all('author'):
            affs = author.find_all("affiliation")
            if affs is None or len(affs) == 0:
                continue
            try:
                forename = author.find('forename').get_text()
                surname = author.find('surname').get_text()
                affiliations_list = []
                for aff in affs:
                    orgnames = ' '.join(org.get_text(strip=True) for org in aff.find_all("orgname"))
                    country = aff.find("country").get_text(strip=True) if aff.find("country") else ''
                    combined = orgnames + ', ' + country
                    if combined not in affiliations_list:
                        affiliations_list.append(combined)
                authors.append((forename + ' ' + surname, affiliations_list))
            except:
                continue
        article_dict["__authors"] = authors

        article_dict["__sections"] = scipdf.parse_sections(article, as_list=False)
        article_dict["__figures"] = scipdf.parse_figure_caption(article)
        article_dict["__formulas"] = scipdf.parse_formulas(article)
        # scipdf.parse_figures('example_data', output_folder='figures') # folder should contain only PDF files
    except Exception as e:
        logging.warning(article_dict["title"] + ":" + str(e))
    del article_dict["__error"]
    return article_dict

def generate_html(title, url, authors, keywords, abstract, subsections):
    html_data = '<div data-schema-version="8">\n<h2>Information</h2>\n'
    # Add h2 title

    title_html = f'<h3>{title}</h3>\n'
    url_html = f'<div id="url">\n<a href="{url}">PDF Link: {url}</a>\n</div>\n\n'
    html_data += title_html + url_html

    # 3. Embed keywords in a table
    keywords_html = '<div id="keywords">Keywords: ' + " , ".join(keywords) + '</div>\n\n'
    html_data += keywords_html

    # Generate Authors table
    if len(authors) > 0:
        authors_html = '<div id="authors">\n<table>\n'
        for author, affiliations in authors:
            authors_html += f'<tr>\n<td>{author}</td>\n'
            for affiliation in affiliations:
                authors_html += f'<td>{affiliation}</td>\n'
            authors_html += '</tr>\n'
        authors_html += '</table>\n</div>\n\n'
        html_data += authors_html
    
    html_data += "<br>\n"

    # 2. Embed the abstract
    abstract_html = f'<div id="abstract"><strong>Abstract</strong><p>{abstract}</p>\n</div>\n'
    html_data += abstract_html + "<br>\n"
    
    # 1. Generate TOC
    toc_html = '<div id="toc">'
    for subsection in subsections:
        toc_html += f'<h4>{subsection.title()}</h4>\n'
    toc_html += '</div>\n'
    html_data += toc_html

    # Combine all parts and return
    html_data += '</div>'
    return html_data
# endregion


# region zotero
def fetch_items_from_collection(zot, collection_key):
    all_items = []
    
    # 获取直接属于这个 collection 的 items
    items = zot.everything(zot.items(collectionKey=collection_key))
    all_items.extend(items)
    
    # 查找子 collections
    # sub_collections = zot.collections_sub(collection_key)
    # for sub_col in sub_collections:
    #     all_items.extend(fetch_items_from_collection(zot, sub_col['data']['key']))
    
    return all_items

def query_title(title, zot):
    items = zot.items(q=title.lower())
    titles = set(item["data"]["title"].lower() for item in items if "title" in item["data"])
    return titles, items

def update_by_arxiv(search, save_root, collection, zot, update_db_callback=None):
    save_root.mkdir(exist_ok=True, parents=True)

    metadatas = []
    for result in search.results():
        if result.title.lower() in LOCAL_DB:
            logging.debug("Title: " + result.title + " exists.")
            continue
        titles, _ = query_title(result.title.lower(), zot)
        if result.title.lower() in titles:
            LOCAL_DB.add(result.title.lower())
            logging.info("Title: " + result.title + " exists. However not added to LOCAL_DB.")
            continue

        result.entry_id = result.entry_id.split("/")[-1]
        result.pdf_url = "https://arxiv.org/pdf/" + result.entry_id + ".pdf"
        save_name = \
            result.updated.astimezone(pytz.timezone("Asia/Shanghai")).strftime("%Y%m%d") + \
            "-20" + result.entry_id + \
            "_" + re.sub("[^A-Za-z0-9 -]+", "", result.title.lower()).replace(" ", "-") + \
            ".pdf"
        pdf_path = download_pdf(result.pdf_url, (save_root / save_name))

        # 根据元数据创建一个 Zotero item
        template = zot.item_template('Preprint')
        template['title'] = result.title.title()
        template['abstractNote'] = result.summary
        template['url'] = result.pdf_url
        template['date'] = result.updated.astimezone(pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d")
        template['DOI'] = result.doi
        template['creators'] = [{'creatorType': 'author', 'firstName': " ".join(au.name.split(" ")[:-1]), 'lastName': au.name.split(" ")[-1]} for au in result.authors]
        # template['volume'] = result.entry_id
        # template['publicationTitle'] = "arXiv"
        template['libraryCatalog'] = "arXiv"
        template['accessDate'] = time.strftime("%Y-%m-%d", time.localtime())
        template['archive'] = "arXiv"
        template['archiveID'] = "arXiv:" + result.entry_id
        template['archiveLocation'] = result.entry_id
        template['extra'] = result.entry_id
        # zot.addto_collection(collection, template)
        template["collections"] = [collection]
        # shortTitle

        metadata = extract_metadata_from_pdf(pdf_path, template)
        template = {k:v for k,v in metadata.items() if not k.startswith("__")}
        response = zot.create_items([template])
        logging.info(str(response))
        key = response["successful"]["0"]["key"]

        # add attachment
        # attachment = zot.item_template("attachment", linkmode="imported_url") # need upload
        # attachment = zot.item_template("attachment", linkmode="linked_url")
        # attachment["title"] = result.entry_id + ".pdf"        

        # add note
        metadatas.append(metadata)
        if "__error" in metadata:
            continue
        
        note = zot.item_template("note")
        note["parentItem"] = key
        note["note"] = generate_html(
            metadata["title"],
            metadata["url"],
            metadata["__authors"],
            [tag["tag"] for tag in metadata["tags"]],
            metadata["abstractNote"],
            [i["heading"] for i in metadata["__sections"]],
        )
        response = zot.create_items([note])
        logging.info(str(response))
        assert len(response["successful"]) == 1

        # add subitems
        refs = []
        for art in metadata["__refs"]:
            if not art.get("title"):
                continue
            titles, items = query_title(result.title.lower(), zot)
            if art["title"].lower() not in titles:
                item = update_db_callback(art)
            else:
                item = filter(lambda x: x["data"]["title"].lower() == art["title"].lower(), items)[0]

            logging.debug("Link: " + metadata["title"] + " to " + art["title"])
            url = "http://zotero.org/groups/{}/items/{}" % (item["library"]["id"], item["data"]["key"])
            refs.append(url)
        template["relations"] = {'dc:relation': refs}
        response = zot.create_items([template])
        assert len(response["successful"]) == 1

        LOCAL_DB.add(result.title.lower())
    return metadatas

# endregion

def create_db_from_public(article, retrieve_info_func, save_root, collection, zot):
    # COLLECTION = "MKR87F5B"
    save_root.mkdir(exist_ok=True, parents=True)

    template = retrieve_info_func(article, zot)
    template["collections"] = [collection]

    metadata = extract_metadata_from_pdf(template["url"], template)

    if metadata.get("__authors"):
        metadata['creators'] = []
        for author, aff in metadata["__authors"]:
            metadata['creators'].append({'creatorType': 'author', 'firstName': author.split(" ")[0] , 'lastName': author.split(" ")[1]})

    template = {k:v for k,v in metadata.items() if not k.startswith("__")}
    response = zot.create_items([template])
    logging.info(str(response))
    assert len(response["successful"]) == 1

    LOCAL_DB.add(template["title"].lower())
    return response["successful"]["0"]

if __name__ == '__main__':
    save_root = Path(os.environ["SAVE_ROOT"])

    key = os.environ["ZOTERO_KEY"]
    if os.environ["USER_ID"]:
        zot = zotero.Zotero(os.environ["USER_ID"], "user", key)
    else:
        zot = zotero.Zotero(os.environ["GROUP_ID"], "group", key)

    for name, collection, search_query in [
        ("ARXIV_ASR", "IDRMFRCT", '("ASR" OR "speech recognition") AND (cat:eess.SP OR cat:cs.SD OR cat:eess.AS)'),
        # https://www.zotero.org/groups/{id}/sjtu_paper_reading/collections/{id}
        ("ARXIV_TSE", "G5IZAPHN", '("TSE" OR "target speaker extraction") AND (cat:eess.SP OR cat:cs.SD OR cat:eess.AS)'),
    ]:
        import arxiv

        search = arxiv.Search(
            query=search_query,
            max_results=100,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )
        # https://export.arxiv.org/api/query?search_query=(cat:eess.SP+OR+cat:cs.SD+OR+cat:eess.AS+OR+cat:cs.AI)+AND+(ASR+OR+speech+recognition)&sortBy=submittedDate&sortOrder=descending&start=0&max_results=1000

        # from dblp import retrieve_info
        # from gscholar import retrieve_info
        from sscholar import retrieve_info
        update_db = lambda article: create_db_from_public(article, retrieve_info, save_root / "DATABASE", "MKR87F5B", zot)
    
        metadatas = update_by_arxiv(search = search, save_root = save_root / name, collection = collection, zot = zot, update_db_callback=update_db)

    with open("LOCAL_DB", "w") as f:
        f.write("\n".join(LOCAL_DB))
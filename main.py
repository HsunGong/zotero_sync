
from collections import OrderedDict
import functools
import logging
import os
from pathlib import Path
import re
import sys
import time
from typing import Tuple, Union

logging.basicConfig(level=logging.INFO, format=("\033[1m\033[94m%(levelname)s\033[0m | \033[92m%(filename)s:%(lineno)d - %(funcName)s\033[0m \033[90m(%(asctime)s)\033[0m\n" "%(message)s"))

import pytz
from pyzotero import zotero, zotero_errors
import requests

LOCAL_DB = dict()
with open("LOCAL_DB", "r") as f:
    for l in f.readlines():
        name, key = l.strip().split("\t")
        LOCAL_DB[name] = key

def quick_add(title_key, id_key):
    LOCAL_DB[title_key] = id_key
    with open("LOCAL_DB", "a") as f:
        # for title_key, id_key in LOCAL_DB.items():
        f.write(f"{title_key}\t{id_key}\n")
    logging.info(f"Add paper to LOCAL_DB, {title_key} : {LOCAL_DB[title_key]}")


# region localpdf
def download_pdf(pdf_url: str, p: Path):
    print(pdf_url, "save to", p)
    headers = {
    #"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    #"Accept-Encoding": "gzip, deflate, br",
    #"Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    #"Cache-Control": "max-age=0",
    ##"Cookie": "browser=202.120.38.125.1680155333113680; _ga=GA1.1.1866255749.1688641261; _ga_B1RR0QKWGQ=GS1.1.1699856236.4.1.1699856269.0.0.0; arxiv_bibex={%22active%22:true%2C%22ds_cs%22:%22S2%22%2C%22ds_eess%22:%22S2%22%2C%22ds_stat%22:%22S2%22%2C%22ds_cond-mat%22:%22S2%22%2C%22ds_q-bio%22:%22S2%22%2C%22ds_math%22:%22S2%22}; arxiv_labs={%22sameSite%22:%22strict%22%2C%22expires%22:365%2C%22bibex-toggle%22:%22enabled%22%2C%22litmaps-toggle%22:%22enabled%22%2C%22last_tab%22:%22tabone%22}",
    #"Dnt": "1",
    ##"If-Modified-Since": "Tue, 23 Jan 2024 03:01:48 GMT",
    ##"If-None-Match": "\"16dde442-4a553-60f942ad02b85\"",
    #"Sec-Ch-Ua": "\"Microsoft Edge\";v=\"119\", \"Chromium\";v=\"119\", \"Not?A_Brand\";v=\"24\"",
    #"Sec-Ch-Ua-Mobile": "?0",
    #"Sec-Ch-Ua-Platform": "\"macOS\"",
    #"Sec-Fetch-Dest": "document",
    #"Sec-Fetch-Mode": "navigate",
    #"Sec-Fetch-Site": "none",
    #"Sec-Fetch-User": "?1",
    #"Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0"
    }
    response = requests.get(pdf_url, headers=headers)

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
    if type(pdf_path) != str:
        try:
            pdf_path = pdf_path.as_posix()
            import PyPDF2
            PyPDF2.PdfReader(pdf_path)
        except Exception as e:
            logging.warning("Error opening " + str(pdf_path) + ":" + str(e))
            return article_dict
    elif not pdf_path.endswith(".pdf"):
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
            article = scipdf.parse_pdf(pdf_path, grobid_url=_grobid_url, fulltext=True, soup=True, return_coordinates=True)
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
    url_link = url[:-4].replace("pdf", "abs")
    url_html = f'<div id="url">\n<a href="{url}">URL Link: {url_link}</a>\n</div>\n' + f'<div id="url">\n<a href="{url}">PDF Link: {url}</a>\n</div>\n\n'
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
    titles = {item["data"]["title"].lower():item for item in items if "title" in item["data"]}
    return titles

def update_by_arxiv(results, save_root, collection, zot, update_db_callback=None, _predef_tags = []):
    save_root.mkdir(exist_ok=True, parents=True)

    metadatas = []
    for result in results:
        title_key = result.title.lower()
        if title_key in LOCAL_DB:
            logging.debug("Title: " + result.title + " exists.")
            continue
        titles = query_title(title_key, zot)
        if title_key in titles:
            logging.info(f"{result.title} exists but not in LOCAL_DB.")
            quick_add(title_key, titles[title_key]["key"])
            continue

        result.entry_id = result.entry_id.split("/")[-1]
        result.pdf_url = "https://arxiv.org/pdf/" + result.entry_id + ".pdf"
        save_name = \
            result.updated.astimezone(pytz.timezone("Asia/Shanghai")).strftime("%Y%m%d") + \
            "-20" + result.entry_id + \
            "_" + re.sub("[^A-Za-z0-9 -]+", "", title_key).replace(" ", "-") + \
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
        template["tags"].extend([{"tag": t } for t in _predef_tags])
        template["tags"] = list(i for i in template["tags"] if type(i) == str and i != "" and len(i) < 40)
        response0 = zot.create_items([template])
        logging.info(str(response0))
        assert len(response0["successful"]) == 1, response0
        key = response0["successful"]["0"]["key"]

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
        response1 = zot.create_items([note])
        logging.info(str(response1))
        assert len(response1["successful"]) == 1
        quick_add(title_key, response1["successful"]["0"]["key"])

        # add subitems
        from tqdm import tqdm
        pbar = tqdm(total=len(metadata["__refs"]))
        update = lambda *args: pbar.update()
        import multiprocessing as MP
        pool = MP.Pool(64)
        refs = []
        for art in metadata["__refs"]:
            if not art.get("title"):
                update()
                continue
            titles = query_title(art["title"].lower(), zot)
            if art["title"].lower() not in titles:
                refs.append(pool.apply_async(update_db_callback, (art,), callback=update))
            else:
                update()
                refs.append(titles[art["title"].lower()])

        for idx in range(len(refs)):
            item = refs[idx]
            if type(item) == MP.pool.AsyncResult:
                try:
                    item = item.get()
                except Exception as e:
                    logging.warning("Subdata get: " + str(e))
                    refs[idx] = None
                    continue

            if item["data"]["title"].lower() not in LOCAL_DB:
                quick_add(item["data"]["title"].lower(), item["data"]["key"])
            url = "http://zotero.org/groups/{}/items/{}".format(item["library"]["id"], item["data"]["key"])
            logging.debug("Link: " + metadata["title"] + " to " + art["title"])
            refs[idx] = url
        response0["successful"]["0"]["data"]["relations"] = {'dc:relation': [r for r in refs if r is not None]}
        try:
            response2 = zot.update_item(response0["successful"]["0"])
            assert response2
        except zotero_errors.PreConditionFailed as e:
            # Response: Item has been modified since specified version (expected 6719, found 6721)
            logging.warning(f"{e}")
            response00 = zot.items(q=response0["successful"]["0"]["data"]["title"])[0]
            response00["data"]["relations"] = {'dc:relation': [r for r in refs if r is not None]}
            response2 = zot.update_item(response00)
            assert response2
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
    return response["successful"]["0"]

if __name__ == '__main__':
    save_root = Path(os.environ["SAVE_ROOT"])

    for _grobid_url in os.environ["GROBID_URLS"].split(","):
        if _grobid_url.endswith('/'): _grobid_url = _grobid_url.rstrip('/')
        res = requests.get(_grobid_url+'/api/isalive')
        if res.text != 'true':
            logging.warning("Error:" + _grobid_url + "----" + res.text)

    key = os.environ["ZOTERO_KEY"]
    if os.environ["USER_ID"]:
        zot = zotero.Zotero(os.environ["USER_ID"], "user", key)
    else:
        zot = zotero.Zotero(os.environ["GROUP_ID"], "group", key)

    import arxiv
    from search import SEARCH_QUERYS
    client = arxiv.Client()
    for name, collection, search_query, max_res, tags in SEARCH_QUERYS:
        results = client.results(arxiv.Search(
            max_results=max_res,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
            **search_query
        ))
        # https://export.arxiv.org/api/query?search_query=(cat:eess.SP+OR+cat:cs.SD+OR+cat:eess.AS+OR+cat:cs.AI)+AND+(ASR+OR+speech+recognition)&sortBy=submittedDate&sortOrder=descending&start=0&max_results=1000

        # from dblp import retrieve_info
        # from gscholar import retrieve_info
        from sscholar import retrieve_info
        update_db = functools.partial(create_db_from_public, retrieve_info_func=retrieve_info, save_root=save_root / "DATABASE", collection="MKR87F5B", zot=zot)
    
        metadatas = update_by_arxiv(results = results, save_root = save_root / name, collection = collection, zot = zot, update_db_callback=update_db, _predef_tags=tags)

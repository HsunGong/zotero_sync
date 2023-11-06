import logging

import bibtex_dblp.config
import bibtex_dblp.database
import bibtex_dblp.dblp_api
from bibtex_dblp.dblp_api import BibFormat
import bibtex_dblp.io


# https://github.com/volkm/bibtex-dblp/blob/master/bin/update_from_dblp.py
def search_dblp(search_string, include_arxiv=False, max_search_results=bibtex_dblp.config.MAX_SEARCH_RESULTS):
    """
    Search an entry for the given search string.
    :param search_string: Search string.
    :param include_arxiv: Whether to include entries from arXiv.
    :param max_search_results: Maximal number of search results to return.
    :return: List of possible entries corresponding to search string, number of total matches
    :raises: HTTPError.
    """
    logging.info("Search: {}".format(search_string))
    search_results = bibtex_dblp.dblp_api.search_publication(search_string, max_search_results=max_search_results)
    if include_arxiv:
        return search_results.results, search_results.total_matches
    else:
        valid_results = []
        total_matches = search_results.total_matches
        for res in search_results.results:
            if "CoRR" in str(res.publication):
                total_matches -= 1
            else:
                valid_results.append(res)
        return valid_results, total_matches


def retrieve_info(article, zot):
    valid_results, _ = search_dblp(article["title"])
    import pdb;pdb.set_trace()

    article = list(filter(lambda x: "arxiv" not in x["pub_url"], search_query))
    if len(article) == 0:
        article = search_query[0]
    
    template = zot.item_template('Conference Paper')
    template['title'] = article["bib"]["title"]
    template['abstractNote'] = article["bib"]["abstract"]
    template['url'] = article["bib"]["eprint_url"]
    template['date'] = article["bib"]["pub_year"]
    template['DOI'] = doi
    
    template['creators'] = []
    for auid in article["author_id"]:
        au = scholarly.search_author_id(auid)
        # {'creatorType': 'author', 'firstName': " ".join(au.name.split(" ")[:-1]), 'lastName': au.name.split(" ")[-1]} for au in authors]
        
    # template['volume'] = result.entry_id
    # template['publicationTitle'] = "arXiv"
    template['libraryCatalog'] = "arXiv"
    template['accessDate'] = time.strftime("%Y-%m-%d", time.localtime())
    template['archiveLocation'] = article["pub_url"]
    template['extra'] = "" + \
        "pub_url: " + article["pub_url"] + "\n" + \
        "cited by: scholar.google.com" + article["citedby_url"] + "\n" + \
        "citations: " + str(article["num_citations"]) + " till " + time.strftime("%Y-%m-%d", time.localtime()) + "\n"
    return True
from typing import OrderedDict

from semanticscholar import SemanticScholar

sch = SemanticScholar()

def retrieve_info(article, zot):
    # template = zot.item_template('journalArticle')
    template = zot.item_template('conferencePaper')
    template['title'] = article["title"]
    template["__bad_authors"] = True
    authors = OrderedDict((au.strip(),None) for au in article["authors"].split(";"))
    template['creators'] = [{'creatorType': 'author', 'firstName': au.split(" ")[0] , 'lastName': au.split(" ")[1]} for au in authors.keys()]
    template['date'] = article["year"]
    # template["publisher"] = article["journal"]
    template["conferenceName"] = article["journal"]
    template["proceedingsTitle"] = article["journal"]

    results = sch.search_paper(article["title"], limit=5)
    if len(results) == 0:
        return template
    best_res = results[0]
    for i in results:
        if i["externalIds"].get("DOI"): best_res = i
    
    template['abstractNote'] = best_res["abstract"]
    template["date"] = best_res["publicationDate"]
    template['proceedingsTitle'] = best_res["journal"].get("name", "") # or ["venue"]
    template['conferenceName'] = best_res["venue"]
    template['volume'] = best_res["journal"].get("volume", "")
    template['pages'] = best_res["journal"].get("pages", "")
    template['DOI'] = best_res["externalIds"].get("DOI", "")
    template['archive'] = best_res["externalIds"].get("ArXiv", "")
    template['archiveLocation'] = "https://arxiv.org/pdf/" + best_res["externalIds"].get("ArXiv", "") + ".pdf"
    template['url'] = "https://arxiv.org/pdf/" + best_res["externalIds"].get("ArXiv", "") + ".pdf"
    if not template['archive']:
        template['url'] = best_res["publicationVenue"].get("url", "")

    # best_res[publicationTypes] = ['JournalArticle', 'Conference']
    template['libraryCatalog'] = ", ".join(best_res["fieldsOfStudy"])
    template['creators'] = [{'creatorType': 'author', 'firstName': au["name"].split(" ")[0] , 'lastName': au["name"].split(" ")[1]} for au in best_res["authors"]]

    template['extra'] = "" + \
        "pub_urls:\n" + \
        " - public:" + best_res["publicationVenue"].get("url") + "\n" + \
        " - semantic-sch: " + best_res["url"] + "\n" + \
        "DBLP-ID: " + best_res["externalIds"].get("DBLP") + "\n" + \
        "citations: " + best_res["citationCount"] + " till " + time.strftime("%Y-%m-%d", time.localtime()) + "\n"
    return template
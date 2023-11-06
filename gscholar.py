from typing import OrderedDict

from scholarly import scholarly


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

    search_query = list(scholarly.search_pubs(article["title"]))
    if len(search_query) == 0:
        return template
    
    article = list(filter(lambda x: "arxiv" not in x["pub_url"], search_query))
    if len(article) == 0:
        article = search_query[0]

    template['abstractNote'] = article["bib"]["abstract"]
    template['url'] = article["bib"]["eprint_url"]
    template['archiveLocation'] = article["pub_url"]
    template['extra'] = "" + \
        "pub_url: " + article["pub_url"] + "\n" + \
        "cited by: scholar.google.com" + article["citedby_url"] + "\n" + \
        "citations: " + str(article["num_citations"]) + " till " + time.strftime("%Y-%m-%d", time.localtime()) + "\n"
    return template
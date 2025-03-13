SEARCH_QUERYS = [
    ("ARXIV_ASR", "IDRMFRCT", {'query':'("ASR" OR "speech recognition") AND (cat:eess.SP OR cat:cs.SD OR cat:eess.AS)'}, 50, []),
    # https://www.zotero.org/groups/{id}/sjtu_paper_reading/collections/{id}
    ("ARXIV_TSE_SE_SS", "G5IZAPHN", {"query":'("TSE" OR "target speaker extraction" OR "SE" OR "speech enhance" OR "SS" OR "speech separation") AND (cat:eess.SP OR cat:cs.SD OR cat:eess.AS)'}, 50, []),
    # ("ARXIV_ASR", "IDRMFRCT", {'id_list':["2310.17558v1", "2309.09838v1",]}, 100, ["xun.gong"]),
    ("ARXIV_SD_AS", "3F7GENNZ", {"query":'(cat:cs.SD OR cat:eess.AS)'}, 50, []),
]

import feedparser

id_list = []
for category in ["cs.SD", "eess.AS"]:
    feed_url = f'http://export.arxiv.org/rss/{category}'
    feed = feedparser.parse(feed_url)
    print("Extend", [i.id for i in feed.entries], "Total: ", len(feed.entries))
    # dict_keys(['id', 'title', 'title_detail', 'links', 'link', 'summary', 'summary_detail', 'authors', 'author', 'author_detail'])
    id_list.extend(entry.id.split('/')[-1] for entry in feed.entries)

SEARCH_QUERYS.append(
    ("ARXIV_SD_AS", "3F7GENNZ",{'id_list': id_list}, len(id_list), []),
)

"""Read-only audiovisual references and scholarly abstracts from public APIs.

NASA archive references are *not* automatically copyright-cleared. Europe PMC
abstract excerpts are *not* independently appraised findings or full-text reuse
permissions. Both serve the open-ended creative research process, never source
custody or automatic footage import.
"""
from __future__ import annotations

import re

from .creative_research import (
    _check, _plain, _request_params, CreativeResearchError,
)


def nasa_video_references(fetch_json, query, limit):
    query=_check(query,limit)
    url=_request_params("https://images-api.nasa.gov/search",{
        "q":query,"media_type":"video","page_size":limit})
    response=fetch_json(url)
    collection=response.get("collection") if isinstance(response,dict) else None
    records=collection.get("items") if isinstance(collection,dict) else None
    if not isinstance(records,list):
        raise CreativeResearchError("NASA archive search schema unavailable")
    found=[]
    for item in records[:limit]:
        if not isinstance(item,dict) or not isinstance(item.get("data"),list):
            continue
        if len(item["data"])<1 or not isinstance(item["data"][0],dict):
            continue
        info=item["data"][0]
        identity=info.get("nasa_id")
        if (not isinstance(identity,str) or
                not re.fullmatch(r"[A-Za-z0-9_-]{1,120}",identity) or
                info.get("media_type")!="video"):
            continue
        found.append({
            "title":_plain(info.get("title"),180) or identity,
            "source_page":"https://images.nasa.gov/details/"+identity,
            "reference_type":"archival_video",
            "rights_status":"unreviewed_government_or_third_party",
            "source_reuse_not_authorized":True,
            "model_has_not_watched_video":True,
        })
    return found


def europe_pmc_abstracts(fetch_json,query,limit):
    query=_check(query,limit)
    url=_request_params(
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search",{
            "query":query,"pageSize":limit,"resultType":"core",
            "format":"json"})
    response=fetch_json(url)
    records=(response.get("resultList") if isinstance(response,dict) else None)
    records=records.get("result") if isinstance(records,dict) else None
    if not isinstance(records,list):
        raise CreativeResearchError("Europe PMC scholarly API malformed")
    found=[]
    for entry in records[:limit]:
        if not isinstance(entry,dict):
            continue
        ident, origin=entry.get("id"),entry.get("source")
        if (not isinstance(ident,str) or
                not re.fullmatch(r"[A-Za-z0-9._-]{1,90}",ident) or
                origin not in ("MED","PMC","PPR","AGR","PAT")):
            continue
        title=_plain(entry.get("title"),180)
        if not title:
            continue
        published=entry.get("pubYear")
        year=int(published) if (isinstance(published,str) and
            re.fullmatch(r"(?:1[5-9]\d\d|20\d\d|2[1-9]\d\d)",published)) else None
        abstract=_plain(entry.get("abstractText"),320)
        found.append({
            "title":title,
            "source_page":"https://europepmc.org/article/"+origin+"/"+ident,
            "year":year,
            "abstract_excerpt":abstract,
            "abstract_is_unreviewed_source_text":True,
            "study_results_verified":False,
            "peer_review_independently_verified":False,
            "research_not_a_media_reuse_license":True,
        })
    return found

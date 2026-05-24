# New Derwent API Documentation

Base URL

```
https://api.clarivate.com/
```

Authentication

All endpoints require a X-APiKey.

```
X-ApiKey: <your_key_genreated for IPDATA API subscription>
```

---

# 1. Patent Search

Returns details of a specific caselaw.

## Endpoint

```
POST /patents/derwent/search-by-query
```

## Example Request

```bash
curl -X POST "https://api.clarivate.com/patents/derwent/search-by-query" \
  -H "X-ApiKey: YOUR_KEY" \
  -H "Content-Type" application/json"
  -d '{
  "params": [
    {
      "query":"ti=Neuropilin",
      "collections": "arapps,brapps,caapps,coapps,crapps,cuapps,mxapps,uyapps,usapps,auapps,cnapps,hkapps,idapps,jpapps,krapps,phapps,sgapps,twapps,vnapps,atapps,beapps,bgapps,hrapps,czapps,dkapps,epapps,eeapps,fiapps,frapps,ddapps,deapps,gbapps,grapps,inapps,ieapps,luapps,maapps,nlapps,noapps,ptapps,roapps,ruapps,rsapps,skapps,zaapps,esapps,seapps,chapps,tnapps,trapps,woapps,brgrants,cagrants,cugrants,mxgrants,usgrants,augrants,cngrants,hkgrants,jpgrants,krgrants,mygrants,mngrants,nzgrants,phgrants,sggrants,sugrants,twgrants,thgrants,vngrants,apgrants,amgrants,atgrants,bygrants,begrants,bggrants,hrgrants,czgrants,csgrants,dkgrants,epgrants,eegrants,eagrants,figrants,frgrants,gegrants,ddgrants,degrants,gbgrants,grgrants,gcgrants,hugrants,isgrants,ingrants,iegrants,ilgrants,itgrants,lvgrants,ltgrants,lugrants,mdgrants,mcgrants,magrants,nlgrants,nogrants,oagrants,plgrants,ptgrants,rogrants,rugrants,rsgrants,skgrants,sigrants,esgrants,segrants,chgrants,uagrants,auinnov,inpadoc,arutils,brutils,crutils,cnutils,hkutils,jputils,krutils,mnutils,twutils,atutils,byutils,bgutils,hrutils,czutils,dkutils,eeutils,deutils,ieutils,mdutils,plutils,ptutils,routils,ruutils,rsutils,skutils,siutils,esutils,trutils,uautils",
      "offset": "0",
      "size": "10",
      "search-on-datatype": "fld_dwpi",
      "return-listref": "true",
      "return-body": "true",
      "search-limit": "1000000",
      "display-limit": "1000000",
      "return-fields": "pn,pd,ti"
    }
  ]
}'
```

## Request Body

```json
{
  "params": [
    {
      "query":"ti=Neuropilin",
      "collections": "arapps,brapps,caapps,coapps,crapps,cuapps,mxapps,uyapps,usapps,auapps,cnapps,hkapps,idapps,jpapps,krapps,phapps,sgapps,twapps,vnapps,atapps,beapps,bgapps,hrapps,czapps,dkapps,epapps,eeapps,fiapps,frapps,ddapps,deapps,gbapps,grapps,inapps,ieapps,luapps,maapps,nlapps,noapps,ptapps,roapps,ruapps,rsapps,skapps,zaapps,esapps,seapps,chapps,tnapps,trapps,woapps,brgrants,cagrants,cugrants,mxgrants,usgrants,augrants,cngrants,hkgrants,jpgrants,krgrants,mygrants,mngrants,nzgrants,phgrants,sggrants,sugrants,twgrants,thgrants,vngrants,apgrants,amgrants,atgrants,bygrants,begrants,bggrants,hrgrants,czgrants,csgrants,dkgrants,epgrants,eegrants,eagrants,figrants,frgrants,gegrants,ddgrants,degrants,gbgrants,grgrants,gcgrants,hugrants,isgrants,ingrants,iegrants,ilgrants,itgrants,lvgrants,ltgrants,lugrants,mdgrants,mcgrants,magrants,nlgrants,nogrants,oagrants,plgrants,ptgrants,rogrants,rugrants,rsgrants,skgrants,sigrants,esgrants,segrants,chgrants,uagrants,auinnov,inpadoc,arutils,brutils,crutils,cnutils,hkutils,jputils,krutils,mnutils,twutils,atutils,byutils,bgutils,hrutils,czutils,dkutils,eeutils,deutils,ieutils,mdutils,plutils,ptutils,routils,ruutils,rsutils,skutils,siutils,esutils,trutils,uautils",
      "offset": "0",
      "size": "10",
      "search-on-datatype": "fld_dwpi",
      "return-listref": "true",
      "return-body": "true",
      "search-limit": "1000000",
      "display-limit": "1000000",
      "return-fields": "pn,pd,ti"
    }
  ]
}
```

### Fields

| Field | Type | Required | Description |
|------|------|----------|-------------|
| query | string | Yes | Defines the boolean query . |
| collections | string | Yes | List of authority that should be considered for search. |
| size | integer | No | Maximum number of records to return. Used for pagination -Max 500. |
| offset | integer | No | Number of records to skip before returning results. Used for pagination. |
| search-on-datatype | string | No  | search on specific patent source fld|fld_dwpi|dwpi, default:fld_dwpi_. |
| search-limit | integer | No | Max recordes returned for the particular search from search engine -Max 1Million. |
| display-limit | integer | No | Max records that can be stored in listref for pagination -Max 1Million also <=Search-limit |
| return-listref | boolean | No | Number of records to skip before returning results. Used for pagination. |
| return-body | boolean | No | Number of records to skip before returning results. Used for pagination. |
| return-fields | string | Yes | Number of records to skip before returning results. Used for pagination. |

### QUERY String

| Field |  Required | Description |
|------|------|----------|-------------|
| FIELD |  Yes | Entitled search field -Single or combination of fields to search |
| OP |  Yes | Operator used for comparison (e.g., `=`, `AND`, `ADJ`, `NEAR` ,`SAME`, `OR`). |
| VALUE | Yes | keywords for search. |

- ## Example Response

```json
{
    "header": {
        "duration": "261",
        "searched": 180988951,
        "found": "992",
        "size": 992
    },
    "body": [
        {
            "id": "US12540187B220260203",
            "rank": "1.0",
            "field": [
                {
                    "name": "pn",
                    "form": "orig",
                    "value": "US12540187B2"
                },
                {
                    "name": "pd",
                    "form": "orig",
                    "value": "2026-02-03"
                },
                {
                    "name": "ti",
                    "form": "orig",
                    "lang": "en",
                    "value": "Method of treating vascular eye and retinal diseases by administration of anti-Neuropilin 1A antibodies"
                }
            ]
        }
    ]
}
```
---
# AI Search
Search Field: AISQ
size : 200 -max

Example:

```bash
curl -X POST "https://api.clarivate.com/patents/derwent/search-by-query" \
  -H "X-ApiKey: YOUR_KEY" \
  -H "Content-Type" application/json"
  -d '{
  "params": [
    {
      "query":"aisq=Neuropilin",
      "collections": "arapps,brapps,caapps,coapps,crapps,cuapps,mxapps,uyapps,usapps,auapps,cnapps,hkapps,idapps,jpapps,krapps,phapps,sgapps,twapps,vnapps,atapps,beapps,bgapps,hrapps,czapps,dkapps,epapps,eeapps,fiapps,frapps,ddapps,deapps,gbapps,grapps,inapps,ieapps,luapps,maapps,nlapps,noapps,ptapps,roapps,ruapps,rsapps,skapps,zaapps,esapps,seapps,chapps,tnapps,trapps,woapps,brgrants,cagrants,cugrants,mxgrants,usgrants,augrants,cngrants,hkgrants,jpgrants,krgrants,mygrants,mngrants,nzgrants,phgrants,sggrants,sugrants,twgrants,thgrants,vngrants,apgrants,amgrants,atgrants,bygrants,begrants,bggrants,hrgrants,czgrants,csgrants,dkgrants,epgrants,eegrants,eagrants,figrants,frgrants,gegrants,ddgrants,degrants,gbgrants,grgrants,gcgrants,hugrants,isgrants,ingrants,iegrants,ilgrants,itgrants,lvgrants,ltgrants,lugrants,mdgrants,mcgrants,magrants,nlgrants,nogrants,oagrants,plgrants,ptgrants,rogrants,rugrants,rsgrants,skgrants,sigrants,esgrants,segrants,chgrants,uagrants,auinnov,inpadoc,arutils,brutils,crutils,cnutils,hkutils,jputils,krutils,mnutils,twutils,atutils,byutils,bgutils,hrutils,czutils,dkutils,eeutils,deutils,ieutils,mdutils,plutils,ptutils,routils,ruutils,rsutils,skutils,siutils,esutils,trutils,uautils",
      "offset": "0",
      "size": "200",
      "search-on-datatype": "fld_dwpi",
      "return-listref": "true",
      "return-body": "true",
      "search-limit": "1000000",
      "display-limit": "1000000",
      "return-fields": "pn,pd,ti"
    }
  ]
}'
```
----

# 2. DOCUEMENT RETERIVE

Reterives documents of the given guid/T3ID/Listref

Documents-by-id
## POST  Endpoint

```bash
curl -X POST "https://api.clarivate.com/patents/derwent/documents-by-id" \
  -H "X-ApiKey: YOUR_KEY" \
  -H "Content-Type" application/json"
  -d '{"params": [{"ids": ["US12448415B220251021"], "collections": "usapps,usgrants,cnapps", "offset": "0", "size": "1",  "return-fields": "pn,ti,tid,cl1,nov,use,ab,ki,tid,use,nov,adv,pad"}]}'
```

## Example Request


```bash
'{
    "params": [
        {
            "ids": [
                "US12448415B220251021"
            ],
            "collections": "usapps,usgrants,cnapps",
            "return-fields": "pn"
        }
    ]
}'
```

## Request Body

| Field | Type | Required | Description |
|------|------|----------|-------------|
| ids | String | yes | lsit of T3ID |
| collections | string | yes | Country of the parties|
| return-fields | String | yes | lsit of fields to be retrieved |

## Example Response

```json
{
    "body": [
        {
            "field": [
                {
                    "form": "docdb",
                    "name": "pn",
                    "value": "US12448415B2"
                },
                {
                    "form": "dwpi",
                    "name": "pn",
                    "value": "US12448415B2"
                },
                {
                    "form": "orig",
                    "name": "pn",
                    "value": "US12448415B2"
                }
            ],
            "id": "US12448415B220251021"
        }
    ],
    "header": {
        "download_details": {
            "downloaded_this_day": 1,
            "downloaded_this_month": 22610,
            "downloaded_this_year": 23441
        },
        "duration": "1",
        "found": "1",
        "response_id": "US12448415B220251021",
        "size": 1
    }
}
```

---

# Error Responses

| Code | Meaning |
|-----|--------|
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden|
| 500 | Internal Server Error |

Example error:

```json
{
    "code": 2200,
    "error": "Invalid derwent search return field(s) requested - ['ptn']"
}
```

Documents-by-listref
# End point
patents/derwent/documents-by-listref

listref: listef from search request

```bash
curl -X POST "https://api.clarivate.com/patents/derwent/documents-by-listref" \
  -H "X-ApiKey: YOUR_KEY" \
  -H "Content-Type" application/json"
  -d '{"params": [{"listref": "1784349127061-9t4hcqlj90N", "collections": "usapps,usgrants,cnapps", "offset": "0", "size": "1",  "return-fields": "pn,ti,tid,cl1,nov,use,ab,ki,tid,use,nov,adv,pad"}]}'
```

Example Request:


```
{
    "params": [
        {
            "listref": "1784349127061-9t4hcqlj90N",
            "collections":"usapps,usgrants,jpapps,idapps",
            "return-fields": "pn",
            "size": "1",
            "offset":"0"
               }
    ]
}
```
🚀 Goals for the Next Iteration

Remove predefined weights
→ The Python processor should no longer apply static coefficients (0.3/0.4/0.3).
→ Instead, it prepares contextual data for the LLM to reason about severity.

Fetch rich contextual signals from Wikidata
→ Use quantitative and qualitative properties that convey importance, impact, scale, or influence.
→ Examples:

Number of sitelinks (global relevance)

Number of statements or references (data completeness / centrality)

Inbound link count (structural centrality)

Descriptions, aliases, categories, or occupations

Pageviews (from Wikipedia API)

Combine Wikidata enrichment with AI task context
→ Merge all collected data (impact area, topics, personality, and contentSummary) into one coherent prompt.
→ Pass that to OpenAI to reason and return one of your existing SeverityEnum values.

🧠 New Flow (Revised Architecture)
NestJS ──> Python Processor ──> Wikidata + OpenAI ──> SeverityEnum

1️⃣ NestJS

Same as today: only extracts Wikidata IDs and summary.

Sends the task to the Python AI processor.

2️⃣ Python Processor
Steps:

Fetch full Wikidata objects:

impactAreaWikidataId

topicsWikidataIds[]

personalityWikidataId (optional)

Extract valuable features per entity:

{
  "id": "Q42",
  "label": "Climate change",
  "description": "...",
  "sitelinks": 120,
  "inbound_links": 2100,
  "pageviews": 350000,
  "instance_of": ["global issue", "environmental phenomenon"]
}


Build a structured context for the AI:

{
  "impact_area": {...},
  "topics": [...],
  "personality": {... or None},
  "content_summary": "...",
}


Prompt OpenAI:

You are a reasoning model for classifying severity levels.
Given the following impact area, topics, personality, and context summary, 
analyze how severe or important this issue is according to these enums:

- critical
- high_3
- high_2
- high_1
- medium_3
- medium_2
- medium_1
- low_3
- low_2
- low_1

Context:
<json with impact area, topics, and content summary>

Respond ONLY with one of the enums.


Parse response → Enum → Return to NestJS

🧩 Wikidata Fields to Extract
Type	Field	How to Get	Why it Matters
Relevance	sitelinks count	entity["sitelinks"]	Measures global recognition
Connectivity	Count of inbound references	SPARQL query	Centrality in Wikidata graph
Engagement	Pageviews (Wikipedia API)	https://wikimedia.org/api/rest_v1/metrics/pageviews/...	Public interest
Qualitative context	labels, descriptions, instance of (P31)	wbgetentities	Gives textual context for reasoning
Scope signals	For people/orgs: follower count, number of awards, etc.	Properties like P8687 (social followers), P166 (awards)	Influence indicators

You don’t need to normalize them manually — just include them in the prompt and let the model infer their relevance.

⚙️ Implementation Changes Summary
Component	Current	Updated
Weight system	Static numeric weights	Removed entirely
Wikidata data	Limited use for scoring	Extended enrichment (quantitative + qualitative)
AI logic	Local math + mapping	Context reasoning via OpenAI
OpenAI prompt	Not used	Central to severity decision
Severity mapping	Manual numeric range	Direct LLM classification to enum
Python processor complexity	~500 lines	Simpler logic, heavier prompt generation
📦 Suggested Code Structure (Python)
# wikidata_client.py
class WikidataClient:
    def fetch_entity(self, wikidata_id: str) -> dict:
        # get labels, descriptions, sitelinks, properties
        ...

    def get_inbound_links(self, wikidata_id: str) -> int:
        # SPARQL count query
        ...

    def get_pageviews(self, wikidata_id: str) -> int:
        # Wikipedia REST API call
        ...

# defining_severity_processor.py
class DefiningSeverityProcessor:
    def process(self, task):
        data = self._enrich_data(task)
        ai_prompt = self._build_prompt(data)
        severity = self._call_openai(ai_prompt)
        return {"severity": severity}

    def _enrich_data(self, task):
        # use WikidataClient to fetch full context
        ...

    def _build_prompt(self, data):
        # merge wikidata context + content summary
        ...

    def _call_openai(self, prompt):
        # call OpenAI API and return enum
        ...

🧩 Next Steps

Remove weight constants and hardcoded impact area priorities.

Add Wikidata enrichment functions (sitelinks, pageviews, etc.).

Design a JSON-based prompt builder to merge Wikidata + summary.

Integrate with OpenAI API (text completion / reasoning model).

Test:

With and without personality

With minimal Wikidata data (fallbacks)

Validate correct enum mapping
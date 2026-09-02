"""City guide generation via Tavily + LLM + attraction image search."""

import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from .. import config
from . import llm


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"\[([^\]]+)\]\(.*?\)", r"\1", text)
    text = re.sub(r"[*_#>`~]+", " ", text)
    text = re.sub(r"[•●▪■◆▶►◦∗]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _tavily_search(section_name: str, query: str, tavily_client) -> tuple:
    try:
        response = tavily_client.search(
            query=query,
            search_depth="advanced",
            max_results=5,
            include_answer=True,
        )
        chunks = []
        if response.get("answer"):
            chunks.append(f"SUMMARY:\n{clean_text(response['answer'])}")
        for r in response.get("results", []):
            content = clean_text(r.get("content", ""))
            if content:
                chunks.append(f"TITLE: {r.get('title', '')}\nCONTENT:\n{content}")
        return section_name, "\n\n".join(chunks)
    except Exception as e:
        return section_name, f"Search failed: {str(e)}"


def _search_attraction_images(attraction_name: str, city_name: str) -> dict:
    """Search for high-quality images using Tavily, fallback to Google Images."""
    from tavily import TavilyClient
    import urllib.parse
    
    try:
        tavily_client = TavilyClient(api_key=config.TAVILY_API_KEY)
        
        # Search for the attraction with focus on direct image results
        query = f'"{attraction_name}" {city_name} photo high quality'
        response = tavily_client.search(
            query=query,
            search_depth="basic",
            max_results=10,
            include_answer=False,
        )
        
        images = []
        photo_domains = {
            "unsplash.com": "Unsplash",
            "pexels.com": "Pexels", 
            "pixabay.com": "Pixabay",
            "flickr.com": "Flickr",
            "freeimages.com": "FreeImages",
            "stocksnap.io": "StockSnap",
            "unsplash.com/napi": "Unsplash API",
            "images.pexels.com": "Pexels Images",
            "pixabay.com/api": "Pixabay API",
        }
        
        # Look for URLs from good photo sites
        for result in response.get("results", []):
            url = result.get("url", "")
            title = result.get("title", attraction_name)
            
            # Check if URL is from a known photo/image site
            for domain in photo_domains.keys():
                if domain in url.lower():
                    images.append({
                        "url": url,
                        "title": title,
                    })
                    break
        
        # If we found some images, return them (even if they're gallery pages)
        if len(images) >= 2:
            return {
                "attraction": attraction_name,
                "images": images[:2],
            }
        
        # Fallback: Create a Google Images search link + Bing Images link for better results
        search_query = f"{attraction_name} {city_name}"
        search_encoded = urllib.parse.quote(search_query)
        
        images = [
            {
                "url": f"https://www.google.com/search?q={search_encoded}&tbm=isch",
                "title": f"Google Images: {attraction_name}",
            },
            {
                "url": f"https://www.bing.com/images/search?q={search_encoded}",
                "title": f"Bing Images: {attraction_name}",
            },
        ]
        
        return {
            "attraction": attraction_name,
            "images": images,
        }
    except Exception as e:
        print(f"Image search failed for {attraction_name}: {e}")
        return {"attraction": attraction_name, "images": []}


def get_attraction_images(city_name: str, country_name: str, guide_markdown: str) -> dict:
    """Extract attractions from guide and fetch their images via Wikipedia."""
    
    # Parse attractions from "Top Attractions & Things to Do" section
    pattern = r"## Top Attractions.*?\n\n(.*?)(?=##|$)"
    match = re.search(pattern, guide_markdown, re.DOTALL | re.IGNORECASE)
    
    if not match:
        return {}
    
    attractions_text = match.group(1)
    # Extract bullet points as attractions
    attractions = re.findall(r"^-\s*\*\*([^*]+)\*\*", attractions_text, re.MULTILINE)
    attractions = [a.strip() for a in attractions if a.strip()][:5]  # Top 5
    
    if not attractions:
        return {}
    
    # Fetch images in parallel
    attraction_images = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(_search_attraction_images, attr, city_name): attr
            for attr in attractions
        }
        for future in as_completed(futures):
            result = future.result()
            if result.get("images"):
                attraction_images[result["attraction"]] = result["images"]
    
    return attraction_images


def generate_city_guide(city_name: str, country_name: str) -> str:
    """Parallel Tavily search → LLM → city guide markdown."""
    from tavily import TavilyClient

    tavily_client = TavilyClient(api_key=config.TAVILY_API_KEY)

    queries = {
        "tourism": f"{city_name} {country_name} top attractions relaxed weekend hidden gems neighborhoods",
        "history": f"{city_name} {country_name} history major historical events heritage",
        "economy": f"{city_name} {country_name} economy industries business profile",
        "culture": f"{city_name} {country_name} culture arts museums events lifestyle",
        "shopping": f"{city_name} {country_name} shopping centers streets markets boutiques local products",
        "sports": f"{city_name} {country_name} famous sports teams athletes sporting events",
        "drinks": f"{city_name} {country_name} local wines beers breweries wineries regional drinks",
    }

    raw_context = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(_tavily_search, key, q, tavily_client): key
            for key, q in queries.items()
        }
        for f in as_completed(futures):
            key, ctx = f.result()
            raw_context[key] = ctx

    structured = "\n\n".join(
        f"## {s.upper()}\n{content}" for s, content in raw_context.items()
    )

    prompt = f"""You are an expert European travel writer specialized in relaxed weekend trips.

Create a detailed but concise weekend guide for:

CITY: {city_name}
COUNTRY: {country_name}

Use ONLY the verified search context below.

SEARCH CONTEXT:
{structured}

IMPORTANT RULES:
- Do NOT mention missing information.
- Do NOT hallucinate fake restaurants or attractions.
- Keep tone elegant, informative, relaxed, and practical.
- Focus on slow travel and enjoyable city experiences.
- Avoid adventure sports or physically intensive activities.
- Mention famous sports teams ONLY if internationally famous.
- Mention regional wines and beers when relevant.
- Use clean markdown formatting.

OUTPUT FORMAT:

# Discover {city_name}: Your Weekend Guide

---
[Introduction paragraph]

---

## What is {city_name} famous for?

- item
- item
- item
- item

## Top Attractions & Things to Do

- attraction
- attraction
- attraction
- hidden gems and neighborhoods

## Shopping & Local Finds

[Shopping centers, shopping areas, shopping streets, boutiques, local markets, local products]

## Culture & Leisure

[Concise section]

## Wining & Dining

[Describe local food and drink culture: regional cuisine, local wines, beers, spirits, and culinary traditions. No specific restaurant names or listings. Focus on what to try, local specialties, market culture, street food character, and dining atmosphere.]

## Economic Landscape

[Concise section describing industries and sectors]

## A Glimpse into History

[A brief historic overview]

---
"""

    return llm.generate(prompt, system_prompt="You are a high-end travel editor producing accurate, readable, structured travel guides.")
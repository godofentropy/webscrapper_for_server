import asyncio
import re
from playwright.async_api import async_playwright
from urllib.parse import urljoin, urlparse

# ===============================
# 1. Default Generative AI Keywords
# ===============================
DEFAULT_GEN_AI_KEYWORDS = [
    "Generative AI",
    "GPT",
    "Large Language Model",
    "LLM",
    "Transformer",
    "Deep Learning",
    "Neural Network",
    "AI-generated",
    "Text-to-image",
    "Stable Diffusion",
    "DALL·E",
    "MidJourney",
    "OpenAI",
    "Google Gemini",
    "Claude AI",
    "Anthropic",
    "Fine-tuning",
    "Prompt Engineering"
]

# ===============================
# 1.5 Classification Helper
# ===============================
def classify_page(title, text_content, og_type=None):
    """
    Classify the page as 'news', 'event', 'article', or 'unknown'
    based on basic heuristics (title keywords, date patterns, etc.).
    Feel free to refine or expand this logic.
    """

   # og:type beats heuristics if present and recognized
    if og_type:
        og_lower = og_type.lower()
        if og_lower in {"article", "news"}:
            return og_lower

    # 1) Check if title suggests "news"
    if title and "news" in title.lower():
        return "news"

    # 2) Check for date patterns or "event" in text (e.g. '2025-03-21' or 'event')
    date_pattern_iso = re.search(r"\d{4}-\d{2}-\d{2}", text_content)
    date_pattern_us = re.search(r"\d{1,2}/\d{1,2}/\d{4}", text_content)
    if date_pattern_iso or date_pattern_us or "event" in text_content:
        return "event"

    # 3) Check if the text might indicate an article
    # For example, looking for 'article' or 'posted on'
    # (Alternatively, if you parse <meta property="og:type"> or <article> tags, etc.)
    if "article" in text_content or "posted on" in text_content:
        return "article"

    # If none match, default to unknown
    return "unknown"

# ===============================
# 2. extract_links Function
# ===============================
async def extract_links(page, base_url):
    """
    Extracts all <a> hrefs from the page, converts them to absolute URLs,
    and returns only those within the same domain as base_url.
    """
    links = await page.eval_on_selector_all("a", "elements => elements.map(el => el.href)")
    valid_links = set()
    for link in links:
        absolute_link = urljoin(base_url, link)
        # Keep only URLs in the same domain
        if urlparse(absolute_link).netloc == urlparse(base_url).netloc:
            valid_links.add(absolute_link)
    return valid_links

# ===============================
# 3. scrape_page Function (Modified to Return Data + Classification)
# ===============================
async def scrape_page(page, url, keywords):
    """
    Scrapes the page for title, AI keywords, and classification.
    Returns a dictionary if keywords are found, else None.
    """
    print(f"Scraping: {url}")
    try:
        # 1) Get the page title
        title = await page.title()

        # 2) Attempt to retrieve og:type metadata
        og_type = None
        try:
            og_meta = await page.query_selector('meta[property="og:type"]')
            if og_meta:
                og_type = await og_meta.get_attribute('content')
        except Exception as e:
            print(f"Could not retrieve og:type: {e}")

        # 3) Get the main text content
        text_content = await page.inner_text("body")
        text_lower = text_content.lower()

        # 4) AI keyword detection
        found_keywords = []
        tokens = set(re.findall(r'\b\w+\b', text_lower))
        for kw in keywords:
            kw_lower = kw.lower()
            if " " in kw_lower:
                pattern = r"(?<![A-Za-z0-9])" + re.escape(kw_lower) + r"(?![A-Za-z0-9])"
                if re.search(pattern, text_lower):
                    found_keywords.append(kw)
            else:
                if kw_lower in tokens:
                    found_keywords.append(kw)

        # 5) If no keywords found, return None
        if not found_keywords:
            print(f"No AI keywords found on {url}.\n")
            return None

        # 6) (Optional) classify the page
        page_class = classify_page(title, og_type, text_lower)  # if you have classify_page

        print(f"🔍 Found keywords on {url}: {found_keywords}")
        print(f"Classification: {page_class}\n" if page_class else "")

        return {
            "url": url,
            "title": title,
            "found_keywords": found_keywords,
            "classification": page_class if page_class else "unknown"
        }

    except Exception as e:
        print(f"⚠️ Error scraping {url}: {e}")
        # If you also want to skip error pages, return None. Otherwise, return an error dict.
        return None


# ===============================
# 4. crawl_website Function (Modified to Collect Results)
# ===============================
async def crawl_website(browser, start_url, keywords, max_pages=10):
    """
    Crawls pages starting from start_url (within the same domain),
    scraping each for AI keywords and following internal links.
    Returns a list of result dictionaries.
    """
    results = []
    visited_urls = set()
    context = await browser.new_context()  # separate context per domain
    page = await context.new_page()

    to_visit = [start_url]
    while to_visit and len(visited_urls) < max_pages:
        url = to_visit.pop(0)
        if url in visited_urls:
            continue

        try:
            await page.goto(url, timeout=10000)
            visited_urls.add(url)
            # Scrape the current page and collect its result
            result = await scrape_page(page, url, keywords)
            results.append(result)
            
            # Gather new links and add those not yet visited
            new_links = await extract_links(page, start_url)
            to_visit.extend(new_links - visited_urls)
        except Exception as e:
            results.append({"url": url, "error": str(e)})

    await context.close()
    return results

# ===============================
# 5. run_all_crawls Function (Modified to Return All Results)
# ===============================
async def run_all_crawls(urls, keywords, max_pages):
    """
    Launches the browser once, then creates a separate context & page
    for each domain, running them concurrently with asyncio.gather().
    Returns a flattened list of all scraping results.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        tasks = [
            asyncio.create_task(crawl_website(browser, url, keywords, max_pages))
            for url in urls
        ]
        nested_results = await asyncio.gather(*tasks)
        # Flatten the list of results (one list per URL)
        results = [item for sublist in nested_results for item in sublist]
        await browser.close()
        return results

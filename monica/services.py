import requests
import logging
import os
from django.utils.text import slugify
from django.conf import settings
from groq import Groq

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")


def generate_ai_content(prompt):
    from .models import BlogPost
    url = "https://api.groq.com/v1/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": "mistral",
        "prompt": prompt,
        "max_tokens": 200,
    }
    
    response = requests.post(url, json=data, headers=headers)
    
    if response.status_code == 200:
        return response.json().get("choices")[0].get("text", "").strip()
    
    return "Error generating content"

def fetch_image_from_pexels(keyword):
    url = "https://api.pexels.com/v1/search"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": keyword, "per_page": 1}  # Fetch only one image

    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        if data["photos"]:
            return data["photos"][0]["src"]["large"]  # Return image URL
    return None  # No image found

def fetch_image_from_pexels(query):
    url = f"https://api.pexels.com/v1/search?query={query}&per_page=1"
    headers = {"Authorization": PEXELS_API_KEY}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()["photos"][0]["src"]["large"]
    return None

def generate_blog_content():
    from .models import BlogPost, AIContentPrompt
    # Get the blog prompt from the database, fallback to default if none exists
    prompt_obj = AIContentPrompt.objects.filter(prompt_type='blog').first()
    prompt = prompt_obj.prompt if prompt_obj else "Generate an engaging fintech blog post on cross-border payments and how BorderCash plays a role"
    
    client = Groq(api_key=GROQ_API_KEY)
    try:
        # Call Mixtral API using Groq SDK
        completion = client.chat.completions.create(
            model="mistral-saba-24b",
            messages=[{"role": "user", "content": prompt}],
            temperature=1,
            max_tokens=1024,
            top_p=1,
            stream=False,  # Disable streaming for direct response
        )
        # Log response for debugging
        logger.info("Mixtral API Response: %s", completion)
        if not completion.choices:
            raise ValueError(f"Unexpected API response: {completion}")
        blog_content = completion.choices[0].message.content
        title = blog_content.split("\n")[0]  # First line as title
        slug = slugify(title)
        # Generate Keywords
        keywords = extract_keywords(blog_content)  # Extract keywords properly
        # Fetch Image from Pexels
        image_url = fetch_image_from_pexels(title)
        return title, blog_content, image_url, slug, keywords  # Ensure five values are returned
    except Exception as e:
        logger.error(f"Error generating blog content: {e}")
        return None, None, None, None, None  # Ensure five values are always returned

def extract_keywords(content):
    """
    Function to extract relevant keywords from content.
    Modify as needed for better keyword extraction.
    """
    words = content.split()[:10]  # Extract first 10 words as a simple keyword approach
    return ", ".join(words)

def generate_relevant_hashtags(content):
    """
    Generate more relevant hashtags based on content.
    This implementation focuses on fintech-related terms.
    """
    import re
    
    # List of common fintech/payment keywords to check for
    fintech_keywords = [
        "payment", "digital", "wallet", "finance", "fintech", "banking", 
        "cross-border", "transaction", "money", "transfer", "swifwallet",
        "mobile", "online", "cashless", "crypto", "blockchain", "secure"
    ]
    
    # Extract words from content
    words = re.findall(r'\b[a-zA-Z]+\b', content.lower())
    
    # Find matching keywords
    matches = set([kw for kw in fintech_keywords if kw in words])
    
    # Add "fintech" and "swifwallet" as defaults if we don't have enough matches
    if "swifwallet" not in matches:
        matches.add("swifwallet")
    if "fintech" not in matches and len(matches) < 3:
        matches.add("fintech")
    if "payments" not in matches and len(matches) < 3:
        matches.add("payments")
    
    # Format as hashtags (capitalize each word for readability)
    hashtags = ' '.join([f"#{word.capitalize()}" for word in matches])
    
    return hashtags


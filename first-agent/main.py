from playwright.sync_api import sync_playwright, Playwright
from bs4 import BeautifulSoup
import time
import re

def fetch_content(url: str, playwright_instance: Playwright) -> str:
    """
    Fetches the full HTML content of a URL using Playwright. 
    
    This version navigates to the Google Careers page, inputs a search term, 
    simulates pressing ENTER, and waits for the results to load before returning the HTML.

    Args:
        url (str): The full URL of the website to start from (Google Careers).
        playwright_instance (Playwright): The synchronous Playwright object.
    
    Returns:
        str: The full HTML content of the job results page or an error message.
    """
    print(f"-> Attempting to navigate and search on Google Careers (Live Simulation: ON): {url}")
    
    try:
        # Launch a visible Chromium browser (headless=False) for live simulation
        browser = playwright_instance.chromium.launch(headless=False)
        
        # 1. Create a new context with a standard user-agent
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        
        page = context.new_page()
        
        # 2. Navigate to the Google Careers search page
        page.goto(url, wait_until="load", timeout=20000)
        
        # 3. Find and fill the search box (using a likely selector for job search input)
        search_input_selector = 'input[placeholder="Search jobs"]'
        
        # Wait for the search box to appear
        page.wait_for_selector(search_input_selector, timeout=10000)
        
        # Type the search query "Software"
        search_term = "Software"
        print(f"-> Typing '{search_term}' into the search bar...")
        page.fill(search_input_selector, search_term)
        
        # *** FIX IMPLEMENTED HERE: Explicitly press 'Enter' to submit the form ***
        print("-> Submitting search by pressing 'Enter'...")
        page.press(search_input_selector, "Enter")

        # 4. Wait for the search results to load.
        # A common selector for the list of job results is used here:
        job_results_selector = 'ul[role="list"] a'
        
        # Wait for at least one job link to be visible (up to 15 seconds)
        print("-> Waiting for job results to load...")
        # Since we pressed enter, we should wait until the new content appears
        page.wait_for_selector(job_results_selector, timeout=15000)

        # Get the fully rendered HTML content of the results page
        raw_html_content = page.content()
        
        # Keep the browser open briefly for the user to see the results before closing
        time.sleep(2) 
        browser.close()
        return raw_html_content

    except Exception as e:
        # Catch Playwright errors (e.g., Timeout, NavigationError)
        return f"An unexpected error occurred during Playwright fetching or waiting: {e}"


def analyze_content_with_ai(raw_html_content: str) -> str:
    """
    Simulates an AI agent processing the raw web content to extract structured data.
    
    The task is to find all job links within the search results.

    Args:
        raw_html_content (str): The raw HTML content of the job results page.

    Returns:
        str: A simulated analysis result containing the extracted job links.
    """
    
    # 1. Define the new system instruction for the complex task
    # Note: The system instruction is actually extracted below, but for simulation consistency, 
    # we keep this header here.
    system_instruction = "Your task is to extract the links of relevant 'Software' roles from the Google Careers search results."

    # 2. Use BeautifulSoup to parse and extract the structured data
    soup = BeautifulSoup(raw_html_content, 'html.parser')
    
    job_links = []
    
    # Find all anchor tags that are likely job links.
    # We look for links pointing to job detail pages. The selector 'a[href*="/jobs/results/"]' 
    # targets links whose href attribute contains that specific subdirectory.
    for link_tag in soup.find_all('a', href=True):
        href = link_tag['href']
        text = link_tag.get_text(strip=True)
        
        # Check if the link looks like a job result link (starts with /jobs/results/) and has meaningful text
        # Google Careers job links look like /jobs/results/XXXX
        if (href.startswith('/jobs/results/') and text and len(text) > 10):
             # Ensure the link is absolute
            full_url = "https://careers.google.com" + href
            
            # Use a tuple (title, url) to keep them paired
            job_links.append((text, full_url))
        
    # Remove duplicates and limit the results for a clean summary
    # We use a set conversion on the tuple list to eliminate duplicates
    unique_links = list(set(job_links))
    
    # 3. Format the simulated AI output
    system_instruction = "Your task is to extract the links of relevant 'Software' roles from the Google Careers search results."
    
    if not unique_links:
        analysis = "AI Agent: No relevant job links were found in the extracted content. This is likely due to complex, custom rendering of the job titles and links."
    else:
        # Format the links nicely for the final output, showing only the first 10 for brevity
        first_ten_links = unique_links[:10]
        link_list = "\n".join([f"  - {title}: {url}" for title, url in first_ten_links])
        
        analysis = (
            f"AI Agent: Successfully identified {len(unique_links)} potential 'Software' roles. "
            f"Here are the title and URL for the first {len(first_ten_links)} extracted job listings:\n"
            f"{link_list}"
        )
        
    return f"--- AI Agent System Instruction ---\n{system_instruction}\n\n--- AI Analysis Result ---\n{analysis}"


if __name__ == "__main__":
    # --- Installation Note ---
    # To run this, you need to install Playwright and its browser dependencies:
    # 1. pip install playwright beautifulsoup4
    # 2. playwright install 
    
    # Target URL is the Google Careers base search results page
    target_url = "https://careers.google.com/jobs/results/" 
    
    # Use sync_playwright context manager to ensure the browser resources are released
    with sync_playwright() as p:
        
        time.sleep(0.5)
        
        # --- STEP 1: Fetch Content using Playwright ---
        web_content = fetch_content(target_url, p)
        
        print("\n" + "="*40)
        print(f"Target URL: {target_url}")
        
        if web_content.startswith("Error:"):
            print(f"Extraction Failed: {web_content}")
        else:
            # --- STEP 2: Analyze Content with AI Agent ---
            ai_result = analyze_content_with_ai(web_content)
            
            # Extract title for display (should now be the Google Careers page title)
            soup = BeautifulSoup(web_content, 'html.parser')
            title = soup.find('title').text.strip() if soup.find('title') else "No Title Found"
            
            print(f"Extracted Title: {title}")
            print("="*40)
            print(ai_result)
            
        print("\n" + "="*40)
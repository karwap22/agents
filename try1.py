from playwright.sync_api import sync_playwright
import json

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()

    page = context.new_page()
    page.goto("https://www.linkedin.com/login")

    print("Login manually. After login press ENTER in terminal.")
    input()

    # save cookies
    cookies = context.cookies()
    with open("cookies.json", "w") as f:
        json.dump(cookies, f)

    print("Cookies saved!")
    browser.close()

from flask import Flask, request, render_template_string
import asyncio
from Python_Backend import run_all_crawls, DEFAULT_GEN_AI_KEYWORDS
import os, sys

if getattr(sys, 'frozen', False):
    try:
        base_path = sys._MEIPASS  # Works for onefile builds
    except AttributeError:
        base_path = os.path.dirname(sys.executable)  # For onedir builds
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

browser_path = os.path.join(base_path, "ms-playwright")
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browser_path

print("PLAYWRIGHT_BROWSERS_PATH set to:", browser_path)

app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    logo_url = "https://brand.illinois.edu/wp-content/uploads/2024/02/Block-I-orange-blue-background.png"

    html_form = f"""
    <!DOCTYPE html>
    <html>
      <head>
        <title>Web Scraper 2.0</title>
        <!-- Bootstrap CSS -->
        <link
          href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css"
          rel="stylesheet"
        >
        <style>
          /* Dark to vibrant purple gradient background */
          body {{
            margin: 0;
            padding: 0;
            background: linear-gradient(to bottom, #141414 0%, #8C23F2 100%) fixed;
            background-size: cover;
          }}
          /* 
            Container with 70% opacity (30% transparency).
            RGBA(108,117,125,0.7) is the color #6c757d at 70% opacity.
          */
          .scraper-container {{
            background-color: rgba(108, 117, 125, 0.7);
            color: #fff;
            border-radius: 0.5rem;
            max-width: 600px;
            margin: 5% auto;
            padding: 2rem;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3);
            text-align: center;
          }}
          #loading {{
            display: none;
            font-weight: bold;
            color: #fff;
            margin-bottom: 20px;
          }}
        </style>
        <script>
          function showLoading() {{
            document.getElementById('loading').style.display = 'block';
          }}
        </script>
      </head>
      <body>
        <div class="scraper-container">
          <img
            src="{logo_url}"
            alt="University of Illinois Logo"
            style="max-width: 120px;"
            class="mb-3"
          />
          <h1 class="mb-4">Web Scraper 2.0</h1>
          <div id="loading" class="alert alert-dark">Scraping in progress... Please standby.</div>
          <form action="/scrape" method="POST" onsubmit="showLoading();">
            <div class="mb-3 text-start">
              <label for="urls" class="form-label"><strong>URLs (space-separated):</strong></label>
              <input
                type="text"
                name="urls"
                id="urls"
                value="https://illinois.edu https://siebelschool.illinois.edu"
                class="form-control"
              />
            </div>

            <div class="mb-3 text-start">
              <label for="keywords" class="form-label"><strong>Keywords (comma-separated):</strong></label>
              <input
                type="text"
                name="keywords"
                id="keywords"
                placeholder="Fine-tune keywords (leave blank for defaults)"
                class="form-control"
              />
            </div>

            <div class="mb-3 text-start">
              <label for="max_pages" class="form-label"><strong>Max Pages:</strong></label>
              <input
                type="number"
                name="max_pages"
                id="max_pages"
                value="5"
                class="form-control"
              />
            </div>

            <button type="submit" class="btn btn-dark w-100">Scrape</button>
          </form>
        </div>

        <!-- Bootstrap JS -->
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js"></script>
      </body>
    </html>
    """
    return render_template_string(html_form)


@app.route("/scrape", methods=["POST"])
def scrape():
    urls_str = request.form.get("urls", "")
    keywords_str = request.form.get("keywords", "")
    max_pages_str = request.form.get("max_pages", "5")

    # Convert the URLs input into a list (split on whitespace)
    urls = urls_str.split() if urls_str.strip() else []
    # If the user typed keywords, use them; otherwise use the default list
    if keywords_str.strip():
        keywords = [kw.strip() for kw in keywords_str.split(",")]
    else:
        keywords = DEFAULT_GEN_AI_KEYWORDS

    try:
        max_pages = int(max_pages_str)
    except ValueError:
        max_pages = 5

    # Run the async scraper
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        scrape_results = loop.run_until_complete(run_all_crawls(urls, keywords, max_pages))
        loop.close()
    except Exception as e:
        return f"<h2>Error:</h2><pre>{e}</pre>"

    # Filter out pages that returned None (i.e. no keywords)
    positive_results = [res for res in scrape_results if res is not None]

    # Build the HTML for the results page with the same design as the index
    result_html = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>Scraping Results</title>
        <!-- Bootstrap CSS -->
        <link
          href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css"
          rel="stylesheet"
        >
        <style>
          /* Same background gradient */
          body {
            margin: 0;
            padding: 0;
            background: linear-gradient(to bottom, #141414 0%, #8C23F2 100%) fixed;
            background-size: cover;
          }
          /* Same semi-transparent container styling */
          .scraper-container {
            background-color: rgba(108, 117, 125, 0.7); /* 70% opaque grey */
            color: #fff;
            border-radius: 0.5rem;
            max-width: 600px;
            margin: 5% auto;
            padding: 2rem;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3);
            text-align: center;
          }
          a {
            color: #fff; /* Make links white by default */
          }
        </style>
      </head>
      <body>
        <div class="scraper-container">
          <h2>Scraping Complete!</h2>
    """

    # If we have results, display them; otherwise say "No positive results found."
    if positive_results:
        result_html += "<ul class='list-group text-start'>"
        for res in positive_results:
            result_html += f"""
              <li class="list-group-item bg-transparent text-white">
                <strong>URL:</strong> <a href="{res['url']}" target="_blank">{res['url']}</a><br/>
                <strong>Title:</strong> {res.get('title', 'N/A')}<br/>
                <strong>Keywords Found:</strong> {', '.join(res.get('found_keywords', []))}<br/>
                <strong>Classification:</strong> {res.get('classification', 'unknown')}
              </li>
            """
        result_html += "</ul>"
    else:
        result_html += "<p>No positive results found.</p>"

    # Add the "Go Back" link + close HTML
    result_html += """
          <br/><a href="/">Go Back</a>
        </div>
        <!-- Bootstrap JS -->
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js"></script>
      </body>
    </html>
    """
    return result_html


if __name__ == "__main__":
    app.run(debug=True)

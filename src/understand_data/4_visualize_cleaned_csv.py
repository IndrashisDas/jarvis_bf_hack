from flask import Flask, Response
import pandas as pd
import os

app = Flask(__name__)

@app.route('/')
def index():
    relative_path = os.path.join(os.path.dirname(__file__), '../../data/filtered_master_file.csv')

    # Load your cleaned CSV
    df = pd.read_csv(relative_path)

    # Limit number of rows to avoid freezing the browser
    limited_df = df.head(1000)

    # Convert DataFrame to HTML table with Bootstrap classes
    html_table = limited_df.to_html(classes='table table-striped table-bordered table-hover', index=False, border=0)

    # Create full HTML page as a string
    html_page = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Filtered PV Data</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
        <meta charset="utf-8">
    </head>
    <body class="p-4">
        <div class="container">
            <h1 class="mb-4">🔍 Filtered PV Forecast Data</h1>
            <p class="text-muted">Showing first {len(limited_df)} records out of {len(df)}</p>
            <div class="table-responsive">
                {html_table}
            </div>
        </div>
    </body>
    </html>
    """

    return Response(html_page, mimetype='text/html')

if __name__ == '__main__':
    app.run(debug=True)

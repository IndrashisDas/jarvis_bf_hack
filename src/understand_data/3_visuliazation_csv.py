import pandas as pd
from flask import Flask, render_template_string
import os

# Define the relative path to the CSV file
relative_path = os.path.join(os.path.dirname(__file__), '../../data/master_pv_forecast_input.csv')

# Load the file using the relative path
df = pd.read_csv(relative_path)

# Limit the data to the first 1000 records
df = df.head(1000)

# Convert the DataFrame to HTML
html_table = df.to_html(classes='table table-striped', index=False)

# Initialize Flask app
app = Flask(__name__)

non_nan_columns = df.columns[df.notna().any()]

# Print columns with non-NaN values
if len(non_nan_columns) > 0:
    print("Columns with non-NaN values:")
    print(non_nan_columns)
else:
    print("All columns are entirely NaN.")

@app.route('/')
def index():
    # Render the HTML with the table
    return render_template_string("""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Uncleaned Data Preview</title>
            <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
        </head>
        <body>
            <div class="container">
                <h1 class="my-4">Uncleaned Data Sample (First 1000 Records)</h1>
                {{ table|safe }}
            </div>
        </body>
        </html>
    """, table=html_table)

# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True)

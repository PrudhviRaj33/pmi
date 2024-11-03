from flask import Flask, request, jsonify, send_from_directory
import os
import time
from werkzeug.utils import secure_filename
import fitz  # PyMuPDF

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'
ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_unique_filename(base_name, extension):
    timestamp = time.strftime("%Y%m%d%H%M%S")
    return f"{base_name}_{timestamp}.{extension}"

def highlight_in_pdf(file_path, keywords, output_path):
    try:
        doc = fitz.open(file_path)
        for page in doc:
            for keyword in keywords:
                keyword = keyword.strip()  # Strip any leading/trailing whitespace
                areas = page.search_for(keyword)

                if areas:  # If any areas are found for the keyword
                    for area in areas:
                        highlight = page.add_highlight_annot(area)
                        highlight.update()
                    print(f"Highlighted '{keyword}' on page {page.number + 1}.")
                else:
                    print(f"No occurrences of '{keyword}' found on page {page.number + 1}.")

        doc.save(output_path)
        doc.close()  # Close the document after saving
        print(f"Saved highlighted PDF to '{output_path}'.")
    except Exception as e:
        print(f"Error highlighting PDF: {e}")

@app.route('/highlight', methods=['POST'])
def highlight():
    if 'file' not in request.files or 'keywords' not in request.form:
        return jsonify({"error": "File and keywords are required"}), 400

    file = request.files['file']
    keywords = request.form['keywords'].split(',')
    
    if not (file and allowed_file(file.filename)):
        return jsonify({"error": "Invalid file type"}), 400

    # Save uploaded file
    filename = secure_filename(file.filename)
    input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(input_path)

    # Highlight keywords and save output
    output_filename = generate_unique_filename(filename.rsplit('.', 1)[0], 'pdf')
    output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)

    if filename.endswith('.pdf'):
        highlight_in_pdf(input_path, keywords, output_path)

    # Check if the output file was created successfully
    if not os.path.exists(output_path):
        return jsonify({"error": "Error creating highlighted PDF"}), 500

    return jsonify({"highlighted_pdf_url": f"/outputs/{output_filename}"}), 200

@app.route('/outputs/<filename>')
def download_file(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
    
    # Bind to 0.0.0.0 and use the PORT environment variable
    port = int(os.environ.get("PORT", 5000))  # Default to 5000 if PORT not set
    app.run(host='0.0.0.0', port=port, debug=True)


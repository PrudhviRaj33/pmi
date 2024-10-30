from flask import Flask, request, jsonify, send_from_directory
import os
import time
from werkzeug.utils import secure_filename
from PyPDF2 import PdfWriter, PdfReader
import fitz  # PyMuPDF
from docx import Document  # For DOCX files

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'docx'}

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
                areas = page.search_for(keyword)
                for area in areas:
                    highlight = page.add_highlight_annot(area)
                    highlight.update()
        doc.save(output_path)
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

    return jsonify({"highlighted_pdf_url": f"/outputs/{output_filename}"}), 200

@app.route('/outputs/<filename>')
def download_file(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
    app.run(debug=True)

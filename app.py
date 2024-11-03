from flask import Flask, request, jsonify, send_from_directory
import os
import time
from werkzeug.utils import secure_filename
import fitz  # PyMuPDF
import firebase_admin
from firebase_admin import credentials, storage
from flask_cors import CORS

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}) 

# Use environment variable or set a default
app.secret_key = os.getenv('SECRET_KEY', 'your_secret_key')  
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'
ALLOWED_EXTENSIONS = {'pdf'}

# Initialize Firebase Admin SDK
cred = credentials.Certificate('serviceAccountKey.json')
firebase_admin.initialize_app(cred, {
    'storageBucket': 'cardio-1c22a.appspot.com'
})
bucket = storage.bucket()

def allowed_file(filename):
    """Check if the uploaded file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_unique_filename(base_name, extension):
    """Generate a unique filename based on the current timestamp."""
    timestamp = time.strftime("%Y%m%d%H%M%S")
    return f"{base_name}_{timestamp}.{extension}"

def highlight_in_pdf(file_path, keywords, output_path):
    """Highlight specified keywords in the PDF."""
    try:
        doc = fitz.open(file_path)
        for page in doc:
            for keyword in keywords:
                keyword = keyword.strip()  # Strip any leading/trailing whitespace
                areas = page.search_for(keyword)

                if areas:
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
    """API endpoint to highlight keywords in a PDF."""
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

    # Upload the highlighted PDF to Firebase Storage
    try:
        blob = bucket.blob(f'videos/{output_filename}')  # Store in the 'videos' folder
        blob.upload_from_filename(output_path)
        blob.make_public()  # Make the blob public
    except Exception as e:
        return jsonify({"error": f"Error uploading to storage: {e}"}), 500

    # Clean up temporary files
    os.remove(input_path)
    os.remove(output_path)

    return jsonify({"highlighted_pdf_url": blob.public_url}), 200

@app.route('/delete', methods=['DELETE'])
def delete_file():
    """API endpoint to delete a file from Firebase Storage."""
    filename = request.args.get('filename')
    if not filename:
        return jsonify({"error": "Filename is required"}), 400

    blob = bucket.blob(f'videos/{filename}')
    try:
        blob.delete()  # Delete the file
        return jsonify({"message": f"File '{filename}' deleted successfully."}), 200
    except Exception as e:
        return jsonify({"error": f"Error deleting file: {e}"}), 500

@app.route('/outputs/<filename>')
def download_file(filename):
    """Download a file from the outputs directory."""
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
    app.run(host='127.0.0.1', port=5001)

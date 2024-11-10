from flask import Flask, request, jsonify, send_from_directory
import os
import time
import json
import fitz  # PyMuPDF
import firebase_admin
from firebase_admin import credentials, storage
from werkzeug.utils import secure_filename
from flask_cors import CORS
import logging
from dotenv import load_dotenv
load_dotenv()  # This loads environment variables from a .env file


# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}) 

# Environment-based secret key and folder configs
app.secret_key = os.getenv('SECRET_KEY', 'default_secret_key')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'
ALLOWED_EXTENSIONS = {'pdf'}

# Load and initialize Firebase Admin SDK with credentials from environment variable
cred_json_str = os.getenv('FIREBASE_CREDENTIALS_JSON')
if not cred_json_str:
    logging.error("FIREBASE_CREDENTIALS_JSON environment variable not set.")
    raise ValueError("Missing FIREBASE_CREDENTIALS_JSON environment variable.")
try:
    cred_json = json.loads(cred_json_str)
    cred = credentials.Certificate(cred_json)
    firebase_admin.initialize_app(cred, {
        'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET', 'default_bucket_name')
    })
    bucket = storage.bucket()
except json.JSONDecodeError:
    logging.error("Invalid JSON format in FIREBASE_CREDENTIALS_JSON.")
    raise ValueError("Invalid JSON in FIREBASE_CREDENTIALS_JSON.")
except Exception as e:
    logging.error(f"Error initializing Firebase: {e}")
    raise ValueError(f"Firebase initialization failed: {e}")

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
                keyword = keyword.strip()
                areas = page.search_for(keyword)
                for area in areas:
                    highlight = page.add_highlight_annot(area)
                    highlight.update()
        doc.save(output_path)
        doc.close()
        logging.info(f"Saved highlighted PDF to '{output_path}'.")
    except Exception as e:
        logging.error(f"Error highlighting PDF: {e}")
        raise

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

    try:
        highlight_in_pdf(input_path, keywords, output_path)
    except Exception as e:
        return jsonify({"error": f"Error processing PDF: {e}"}), 500

    # Upload the highlighted PDF to Firebase Storage
    try:
        blob = bucket.blob(f'videos/{output_filename}')
        blob.upload_from_filename(output_path)
        blob.make_public()
    except Exception as e:
        logging.error(f"Error uploading to Firebase: {e}")
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
        blob.delete()
        logging.info(f"File '{filename}' deleted successfully.")
        return jsonify({"message": f"File '{filename}' deleted successfully."}), 200
    except Exception as e:
        logging.error(f"Error deleting file: {e}")
        return jsonify({"error": f"Error deleting file: {e}"}), 500

@app.route('/outputs/<filename>')
def download_file(filename):
    """Download a file from the outputs directory."""
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
    port = int(os.environ.get('PORT', 5000))  # Use the port provided by Render
    app.run(host='0.0.0.0', port=port, debug=True)

from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from pdf2image import convert_from_bytes
from PIL import Image
import os, io, tempfile, zipfile, re

app = Flask(__name__)


# --- Utility: Convert image to PDF page with original resolution centered on A4 ---
def image_to_pdf(image_stream):
    img = Image.open(image_stream)
    img_width, img_height = img.size
    page_width, page_height = A4

    # Calculate position to center the image
    x_offset = (page_width - img_width * 0.75) / 2  # 0.75 to convert pixels to points (approx.)
    y_offset = (page_height - img_height * 0.75) / 2

    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)
    image = ImageReader(img)
    can.drawImage(image, x_offset, y_offset, width=img_width * 0.75, height=img_height * 0.75, preserveAspectRatio=True)
    can.showPage()
    can.save()
    packet.seek(0)
    return PdfReader(packet)


# --- Reverse PDF ---
@app.route('/reverse', methods=['POST'])
def reverse_pdf():
    pdf_file = request.files['pdf_file']
    reader = PdfReader(pdf_file)
    writer = PdfWriter()
    for page in reversed(reader.pages):
        writer.add_page(page)
    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='reversed.pdf')

# --- Merge Multiple PDFs ---
@app.route('/merge', methods=['POST'])
def merge_pdfs():
    pdf_files = request.files.getlist('pdf_files')  # This keeps the order of selection
    writer = PdfWriter()

    for file in pdf_files:
        if file:
            reader = PdfReader(file)
            for page in reader.pages:
                writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='merged.pdf')



# --- Delete N Pages (start or end) ---
@app.route('/delete_n', methods=['POST'])
def delete_n_pages():
    pdf_file = request.files['pdf_file']
    n = int(request.form['n'])
    location = request.form['location']
    reader = PdfReader(pdf_file)
    writer = PdfWriter()
    total_pages = len(reader.pages)
    keep_range = range(n, total_pages) if location == 'start' else range(0, total_pages - n)
    for i in keep_range:
        writer.add_page(reader.pages[i])
    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='deleted_n_pages.pdf')

# --- Add N Images (start or end) ---
@app.route('/add_images', methods=['POST'])
def add_n_images():
    pdf_file = request.files['pdf_file']
    images = request.files.getlist('images')
    location = request.form['location']

    writer = PdfWriter()
    pdf_reader = PdfReader(pdf_file)

    if location == 'start':
        for img in images:
            img_reader = image_to_pdf(img.stream)
            writer.add_page(img_reader.pages[0])
        for page in pdf_reader.pages:
            writer.add_page(page)
    else:
        for page in pdf_reader.pages:
            writer.add_page(page)
        for img in images:
            img_reader = image_to_pdf(img.stream)
            writer.add_page(img_reader.pages[0])

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='added_images.pdf')

# --- Delete Specific or Range of Pages ---
@app.route('/delete_specific', methods=['POST'])
def delete_specific_pages():
    pdf_file = request.files['pdf_file']
    pages_str = request.form['pages']  # e.g. "2,4,6-8"
    try:
        delete_pages = set()
        for part in pages_str.split(','):
            part = part.strip()
            if '-' in part:
                start, end = map(int, part.split('-'))
                delete_pages.update(range(start - 1, end))
            elif part.isdigit():
                delete_pages.add(int(part) - 1)

        reader = PdfReader(pdf_file)
        writer = PdfWriter()
        for i in range(len(reader.pages)):
            if i not in delete_pages:
                writer.add_page(reader.pages[i])

        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        return send_file(output, as_attachment=True, download_name='deleted_selected_pages.pdf')
    except Exception as e:
        return str(e), 400

# --- Insert Images at Specific Positions ---
@app.route('/insert_images', methods=['POST'])
def insert_images():
    base_pdf = request.files['base_pdf']
    images = request.files.getlist('images')
    positions_str = request.form['positions']  # e.g. "2,4,6-8"

    try:
        positions = []
        for part in positions_str.split(','):
            part = part.strip()
            if '-' in part:
                start, end = map(int, part.split('-'))
                positions.extend(range(start - 1, end))
            elif part.isdigit():
                positions.append(int(part) - 1)

        base_reader = PdfReader(base_pdf)
        writer = PdfWriter()

        insert_queue = []
        for img in images:
            img_reader = image_to_pdf(img.stream)
            insert_queue.append(img_reader.pages[0])

        insert_map = {}
        for i, pos in enumerate(positions):
            if pos not in insert_map:
                insert_map[pos] = []
            if i < len(insert_queue):
                insert_map[pos].append(insert_queue[i])

        total = len(base_reader.pages)
        i = 0
        while i <= total:
            if i in insert_map:
                for p in insert_map[i]:
                    writer.add_page(p)
            if i < total:
                writer.add_page(base_reader.pages[i])
            i += 1

        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        return send_file(output, as_attachment=True, download_name='inserted_images.pdf')

    except Exception as e:
        return str(e), 400

@app.route('/split_pdf', methods=['POST'])
def split_pdf():
    pdf_file = request.files['pdf_file']
    split_str = request.form['split_points']  # e.g. "5,12"
    try:
        reader = PdfReader(pdf_file)
        split_points = sorted(set(int(x.strip()) for x in split_str.split(',') if x.strip().isdigit()))
        split_points = [p for p in split_points if 1 <= p < len(reader.pages)]

        # Add start and end boundaries
        split_indices = [0] + split_points + [len(reader.pages)]

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zipf:
            for i in range(len(split_indices) - 1):
                writer = PdfWriter()
                for j in range(split_indices[i], split_indices[i + 1]):
                    writer.add_page(reader.pages[j])
                temp_output = io.BytesIO()
                writer.write(temp_output)
                temp_output.seek(0)
                zipf.writestr(f'part_{i + 1}.pdf', temp_output.read())

        zip_buffer.seek(0)
        return send_file(zip_buffer, mimetype='application/zip', download_name='splitted_pdfs.zip', as_attachment=True)
    except Exception as e:
        return str(e), 400

@app.route('/pdf_to_images', methods=['POST'])
def pdf_to_images():
    pdf_file = request.files['pdf_file']
    try:
        images = convert_from_bytes(pdf_file.read(), poppler_path=r"C:\Users\11023109\Downloads\Release-24.08.0-0\poppler-24.08.0\Library\bin")
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zipf:
            for i, img in enumerate(images):
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='PNG')
                img_byte_arr.seek(0)
                zipf.writestr(f'page_{i+1}.png', img_byte_arr.read())
        zip_buffer.seek(0)
        return send_file(zip_buffer, mimetype='application/zip', download_name='pdf_pages.zip', as_attachment=True)
    except Exception as e:
        return str(e), 400

# --- Convert Images to PDF ---
@app.route('/images_to_pdf', methods=['POST'])
def images_to_pdf():
    try:
        images = request.files.getlist('images')
        writer = PdfWriter()
        for img in images:
            img_reader = image_to_pdf(img.stream)
            writer.add_page(img_reader.pages[0])

        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        return send_file(output, as_attachment=True, download_name='converted_from_images.pdf')
    except Exception as e:
        return str(e), 400

# --- Main Route (Frontend) ---
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

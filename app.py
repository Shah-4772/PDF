from flask import Flask, render_template, request, send_file
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def clean_folder(folder):
    for f in os.listdir(folder):
        os.remove(os.path.join(folder, f))

def image_to_pdf(image_path, output_path):
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    c.drawImage(image_path, 0, 0, width=width, height=height)
    c.showPage()
    c.save()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/reverse", methods=["POST"])
def reverse_pdf():
    clean_folder(UPLOAD_FOLDER)
    clean_folder(OUTPUT_FOLDER)
    file = request.files['pdf_file']
    path = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
    file.save(path)
    reader = PdfReader(path)
    writer = PdfWriter()
    for page in reversed(reader.pages):
        writer.add_page(page)
    out_path = os.path.join(OUTPUT_FOLDER, "reversed.pdf")
    with open(out_path, "wb") as f:
        writer.write(f)
    return send_file(out_path, as_attachment=True)

@app.route("/delete_last_2", methods=["POST"])
def delete_last_2():
    clean_folder(UPLOAD_FOLDER)
    clean_folder(OUTPUT_FOLDER)
    file = request.files['pdf_file']
    path = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
    file.save(path)
    reader = PdfReader(path)
    writer = PdfWriter()
    for i in range(len(reader.pages) - 2):
        writer.add_page(reader.pages[i])
    out_path = os.path.join(OUTPUT_FOLDER, "deleted_last2.pdf")
    with open(out_path, "wb") as f:
        writer.write(f)
    return send_file(out_path, as_attachment=True)

@app.route("/delete_n", methods=["POST"])
def delete_n():
    clean_folder(UPLOAD_FOLDER)
    clean_folder(OUTPUT_FOLDER)
    file = request.files['pdf_file']
    n = int(request.form['n'])
    location = request.form['location']
    path = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
    file.save(path)
    reader = PdfReader(path)
    writer = PdfWriter()
    total = len(reader.pages)
    if location == "start":
        pages = range(n, total)
    else:
        pages = range(0, total - n)
    for i in pages:
        writer.add_page(reader.pages[i])
    out_path = os.path.join(OUTPUT_FOLDER, "deleted_n.pdf")
    with open(out_path, "wb") as f:
        writer.write(f)
    return send_file(out_path, as_attachment=True)

@app.route("/delete_specific", methods=["POST"])
def delete_specific():
    clean_folder(UPLOAD_FOLDER)
    clean_folder(OUTPUT_FOLDER)
    file = request.files['pdf_file']
    pages_str = request.form['pages']
    pages_to_delete = set(int(x.strip()) - 1 for x in pages_str.split(',') if x.strip().isdigit())
    path = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
    file.save(path)
    reader = PdfReader(path)
    writer = PdfWriter()
    for i in range(len(reader.pages)):
        if i not in pages_to_delete:
            writer.add_page(reader.pages[i])
    out_path = os.path.join(OUTPUT_FOLDER, "deleted_specific.pdf")
    with open(out_path, "wb") as f:
        writer.write(f)
    return send_file(out_path, as_attachment=True)

@app.route("/add_images", methods=["POST"])
def add_images():
    clean_folder(UPLOAD_FOLDER)
    clean_folder(OUTPUT_FOLDER)
    pdf_file = request.files['pdf_file']
    image_files = request.files.getlist("images")
    location = request.form['location']
    pdf_path = os.path.join(UPLOAD_FOLDER, secure_filename(pdf_file.filename))
    pdf_file.save(pdf_path)

    image_pdfs = []
    for idx, img in enumerate(image_files):
        img_path = os.path.join(UPLOAD_FOLDER, f"img_{idx}.pdf")
        img.save(f"img_{idx}.jpg")
        image_to_pdf(f"img_{idx}.jpg", img_path)
        image_pdfs.append(img_path)

    writer = PdfWriter()

    if location == "start":
        for pdf in image_pdfs:
            reader = PdfReader(pdf)
            for page in reader.pages:
                writer.add_page(page)
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            writer.add_page(page)
    else:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            writer.add_page(page)
        for pdf in image_pdfs:
            reader = PdfReader(pdf)
            for page in reader.pages:
                writer.add_page(page)

    out_path = os.path.join(OUTPUT_FOLDER, "added_images.pdf")
    with open(out_path, "wb") as f:
        writer.write(f)

    for pdf in image_pdfs:
        os.remove(pdf)
    for img in os.listdir("."):
        if img.startswith("img_") and img.endswith(".jpg"):
            os.remove(img)

    return send_file(out_path, as_attachment=True)

@app.route("/merge", methods=["POST"])
def merge():
    clean_folder(UPLOAD_FOLDER)
    clean_folder(OUTPUT_FOLDER)
    files = request.files.getlist("pdf_files")
    writer = PdfWriter()
    for file in files:
        path = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
        file.save(path)
        reader = PdfReader(path)
        for page in reader.pages:
            writer.add_page(page)
    out_path = os.path.join(OUTPUT_FOLDER, "merged.pdf")
    with open(out_path, "wb") as f:
        writer.write(f)
    return send_file(out_path, as_attachment=True)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
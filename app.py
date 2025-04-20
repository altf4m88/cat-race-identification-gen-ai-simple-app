import os
import google.generativeai as genai
from flask import Flask, request, render_template, redirect, url_for, Markup
from dotenv import load_dotenv
from PIL import Image
import io
import base64
from flaskext.markdown import Markdown

# Muat environment variables dari .env file
load_dotenv()

app = Flask(__name__)
Markdown(app)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # Batas ukuran file upload 16MB

# Konfigurasi Gemini API Key
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY tidak ditemukan di environment variable.")
genai.configure(api_key=api_key)

# --- System Prompt Anda ---
# (Salin System Prompt yang sudah Anda buat sebelumnya ke sini)
SYSTEM_PROMPT = """Anda adalah AI spesialis analisis gambar yang berfokus pada identifikasi ras kucing. Tugas utama Anda adalah menganalisis gambar yang diunggah pengguna, menentukan ras kucing yang ada di dalamnya, dan memberikan informasi ringkas mengenai ras tersebut.

Instruksi:

1.  Terima Input Gambar: Anda akan menerima input berupa gambar.
2.  Analisis Gambar: Periksa gambar dengan cermat untuk mengidentifikasi keberadaan kucing dan ciri-ciri visualnya (seperti bentuk kepala, telinga, mata, pola bulu, panjang bulu, bentuk tubuh, ekor).
3.  Identifikasi Ras: Berdasarkan analisis visual, tentukan ras kucing yang paling mungkin terlihat dalam gambar. Gunakan pengetahuan Anda tentang berbagai ras kucing.
4.  Cari Informasi Tambahan: Setelah ras teridentifikasi, cari informasi ringkas mengenai sejarah atau asal-usul ras tersebut.
5.  Berikan Hasil: Sampaikan hasil identifikasi dan informasi tambahan Anda kepada pengguna dalam format berikut:
    * Ras Terdeteksi: [Nama Ras Kucing]
    * Tingkat Keyakinan: [Tinggi / Sedang / Rendah] - (Berikan estimasi seberapa yakin Anda dengan identifikasi visual ini).
    * Ciri Khas Pendukung: [Sebutkan 2-3 ciri visual utama dari gambar yang mendukung kesimpulan Anda, misal: "Bulu panjang dan lebat, hidung pesek", "Telinga melipat ke depan", "Pola bulu tutul khas"].
    * Ringkasan Sejarah Ras: [Berikan 1-2 kalimat ringkas tentang asal-usul atau sejarah singkat dari ras kucing yang teridentifikasi. Contoh: "Berasal dari wilayah X pada abad ke-Y...", "Merupakan hasil persilangan alami/selektif dari ras A dan B..."].
6.  Tangani Ketidakpastian/Kasus Khusus:
    * Jika gambar tidak jelas, berkualitas rendah, atau sudut pengambilan mempersulit identifikasi, sebutkan hal ini dan berikan tingkat keyakinan "Rendah". Jangan menyertakan sejarah jika ras tidak dapat diidentifikasi dengan cukup pasti.
    * Jika gambar tidak mengandung kucing, nyatakan dengan jelas bahwa tidak ada kucing yang terdeteksi dalam gambar.
    * Jika Anda mendeteksi kucing tetapi tidak yakin dengan ras spesifiknya (misalnya, kucing domestik campuran tanpa ciri ras dominan), sebutkan sebagai "Kucing Domestik Campuran" atau "Ras tidak dapat ditentukan secara spesifik" dengan tingkat keyakinan yang sesuai, dan tidak perlu menyertakan sejarah ras.
7.  Bahasa: Selalu berikan respons dalam Bahasa Indonesia.
8.  Fokus: Fokus pada identifikasi ras kucing berdasarkan visual gambar dan berikan informasi ringkas mengenai sejarah ras yang teridentifikasi tersebut. Jangan menambahkan informasi lain yang tidak relevan (seperti detail perawatan mendalam atau saran adopsi) kecuali diminta spesifik oleh pengguna.

Tujuan Utama: Memberikan identifikasi ras kucing yang paling mungkin berdasarkan bukti visual dalam gambar yang diunggah, beserta tingkat keyakinan, justifikasi visual singkat, dan ringkasan sejarah ras tersebut."""
# --- Akhir System Prompt ---

# Pilih model Gemini yang mendukung multimodal (gambar dan teks)
# Gemini 1.5 Flash adalah pilihan yang baik untuk keseimbangan kecepatan dan biaya
# Ganti jika Anda ingin menggunakan model lain seperti 'gemini-1.5-pro-latest'
MODEL_NAME = "gemini-2.0-flash"

# Inisialisasi model Gemini
model = genai.GenerativeModel(
    MODEL_NAME,
    system_instruction=SYSTEM_PROMPT
)

# Fungsi untuk memeriksa ekstensi file yang diizinkan
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET'])
def index():
    """Menampilkan halaman utama dengan form upload."""
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    """Menerima upload gambar, mengirim ke Gemini, dan menampilkan hasil."""
    if 'file' not in request.files:
        return render_template('index.html', error="Tidak ada file yang dipilih.")

    file = request.files['file']

    if file.filename == '':
        return render_template('index.html', error="Tidak ada file yang dipilih.")

    if file and allowed_file(file.filename):
        try:
            # Baca gambar menggunakan Pillow untuk validasi & konversi
            img_bytes = file.read()
            img = Image.open(io.BytesIO(img_bytes))
            # Pastikan formatnya didukung (misal konversi ke JPEG atau PNG jika perlu)
            # Kita akan mengirim bytes asli, tapi perlu mime type yang benar
            # Coba deteksi mime type dari nama file atau biarkan API mendeteksi
            # Untuk API google-generativeai, kita buat objek gambar
            image_part = {
                "mime_type": file.mimetype, # Ambil mimetype dari request Flask
                "data": img_bytes
            }

            # Buat prompt untuk Gemini API (gambar + teks instruksi sederhana)
            prompt_parts = [
                image_part,
                "\n\nIdentifikasi ras kucing pada gambar ini berdasarkan instruksi sistem." # Tambahkan prompt teks singkat
            ]

            # Panggil Gemini API
            print(f"Mengirim permintaan ke model: {MODEL_NAME}...")
            response = model.generate_content(prompt_parts, stream=False) # stream=False untuk jawaban lengkap
            print("Menerima respons dari Gemini.")

            # Encode gambar ke base64 untuk ditampilkan di HTML
            image_b64 = base64.b64encode(img_bytes).decode('utf-8')

            # Ambil teks hasil dari respons
            result_text = response.text

            # Format response as markdown
            formatted_text = result_text.replace('\n', '  \n')  # Ensure proper markdown line breaks
            result_markdown = Markup(formatted_text)

            return render_template('index.html', result=result_markdown, image_b64=image_b64, is_markdown=True)

        except genai.types.BlockedPromptException as e:
             print(f"Error: Permintaan diblokir - {e}")
             return render_template('index.html', error=f"Permintaan analisis diblokir oleh sistem keamanan. Coba gambar lain.")
        except Exception as e:
            print(f"Error saat memproses gambar atau memanggil API: {e}")
            # Tampilkan error yang lebih umum ke pengguna
            return render_template('index.html', error=f"Terjadi kesalahan saat memproses gambar: {e}")

    else:
        return render_template('index.html', error="Format file tidak didukung. Gunakan PNG, JPG, JPEG, GIF, atau WEBP.")

# Jalankan aplikasi Flask
if __name__ == '__main__':
    # Pastikan API Key sudah ada sebelum menjalankan
    if not api_key:
         print("Kesalahan: GEMINI_API_KEY environment variable belum diatur.")
    else:
         print("Menjalankan Flask App...")
         # host='0.0.0.0' agar bisa diakses dari jaringan lokal jika perlu
         # debug=True hanya untuk pengembangan, jangan gunakan di produksi
         app.run(host='0.0.0.0', port=5000, debug=True)
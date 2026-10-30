"""SEMUA selektor WhatsApp Web ada di file ini.

WhatsApp Web sering mengubah tampilannya. Kalau pengiriman tiba-tiba gagal,
mulai periksa dari sini. Setiap elemen punya beberapa alternatif (dicoba berurutan),
termasuk label berbahasa Inggris dan Indonesia.

Terakhir dicek: 26 Oktober 2026 (kirim, baca status "Read", baca balasan, nomor tidak
terdaftar – semua lulus uji manual).

Cara memeriksa bila rusak: buka chat di jendela Chrome app, klik kanan pesan > Inspect,
lalu cocokkan atribut data-testid / aria-label dengan daftar di bawah.
"""

WA_URL = "https://web.whatsapp.com/"

# Layar QR (belum login)
QR = (
    'canvas[aria-label*="Scan" i]',
    'canvas[aria-label*="Pindai" i]',
    "div[data-ref] canvas",
    '[data-testid="qrcode"]',
)

# Sudah login: daftar chat tampil
LOGGED_IN = (
    "#pane-side",
    '[data-testid="chat-list"]',
    'div[aria-label="Chat list"]',
    'div[aria-label="Daftar chat"]',
)

# Kotak tulis pesan di chat yang terbuka
COMPOSE = (
    'footer div[contenteditable="true"][role="textbox"]',
    'footer div[contenteditable="true"]',
    '[data-testid="conversation-compose-box-input"]',
)

# Tombol kirim
SEND_BUTTON = (
    'footer button[aria-label="Send"]',
    'footer button[aria-label="Kirim"]',
    '[data-testid="send"]',
    'footer span[data-icon="send"]',
    'footer span[data-icon="wds-ic-send-filled"]',
)

# Popup saat nomor tidak terdaftar di WhatsApp
POPUP = (
    '[data-animate-modal-popup="true"]',
    'div[role="dialog"]',
)
INVALID_NUMBER_TEXT = (
    "phone number shared via url is invalid",
    "nomor telepon yang dibagikan melalui url tidak valid",
    "isn't on whatsapp",
    "tidak terdaftar di whatsapp",
)

# Pesan di dalam chat (versi Okt 2026: kelas CSS acak, jadi pakai data-testid & aria-label)
MESSAGE_ROW = (
    '#main [data-testid^="conv-msg-"]',
    '#main div[role="row"] div[data-id]',
)
MESSAGE_TEXT = ('[data-testid="selectable-text"]', "span.selectable-text")
# Kotak kutipan di dalam pesan yang membalas pesan lain (nama atribut berubah-ubah antar versi WhatsApp Web)
QUOTE = ('[data-testid="quoted-message"], [aria-label="Quoted message"], [aria-label="Pesan yang dikutip"], '
         '[aria-label="Pesan dikutip"], .quoted-mention')
TAIL_OUT = '[data-testid="tail-out"]'
TAIL_IN = '[data-testid="tail-in"]'
# Label tersembunyi di awal tiap pesan: "You:" untuk pesan kita, "<nama>:" untuk pesan masuk
OUT_SENDER_LABELS = ("you:", "anda:")

# Status pesan keluar, dicocokkan ke aria-label ikon (mis. " Read ") dan judul svg (mis. "wds-ic-read").
# Urutan penting: dicek dari atas.
STATUS_KEYWORDS = (
    ("pending", ("pending", "menunggu", "msg-time", "ic-time", "clock")),
    ("read", ("read", "dibaca", "ic-read")),
    ("delivered", ("delivered", "diterima", "dblcheck", "double")),
    ("sent", ("sent", "terkirim", "msg-check", "ic-check")),
)

# localStorage berisi nomor akun yang login, mis. "6281234567890:12@c.us"
LOCALSTORAGE_WID_KEYS = ("last-wid-md", "last-wid")

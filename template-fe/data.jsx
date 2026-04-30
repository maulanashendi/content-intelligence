// Mock dataset for Content Intelligence prototype
const FEEDS = [
  { id: 1, name: "Antara Politik", category: "politik", status: "OK", lastFetch: "12m ago", count: 184, fail: 0 },
  { id: 2, name: "Antara Ekonomi", category: "ekonomi", status: "OK", lastFetch: "12m ago", count: 211, fail: 0 },
  { id: 3, name: "Detik Hukum", category: "hukum", status: "OK", lastFetch: "8m ago", count: 156, fail: 0 },
  { id: 4, name: "Kompas Lingkungan", category: "lingkungan", status: "FAILING", lastFetch: "1h 14m", count: 47, fail: 2 },
  { id: 5, name: "CNN Indonesia", category: "umum", status: "OK", lastFetch: "9m ago", count: 298, fail: 0 },
  { id: 6, name: "Tribun Investigasi", category: "investigasi", status: "OK", lastFetch: "14m ago", count: 38, fail: 0 },
  { id: 7, name: "Reuters ID Wire", category: "umum", status: "OK", lastFetch: "6m ago", count: 412, fail: 0 },
  { id: 8, name: "Liputan6 Politik", category: "politik", status: "OK", lastFetch: "11m ago", count: 167, fail: 0 },
  { id: 9, name: "Tirto Riset", category: "investigasi", status: "DEAD", lastFetch: "9h 22m", count: 0, fail: 3 },
  { id: 10, name: "Bisnis Indonesia", category: "ekonomi", status: "OK", lastFetch: "13m ago", count: 132, fail: 0 },
  { id: 11, name: "Mongabay ID", category: "lingkungan", status: "OK", lastFetch: "22m ago", count: 41, fail: 0 },
  { id: 12, name: "Republika Politik", category: "politik", status: "OK", lastFetch: "10m ago", count: 124, fail: 0 },
];

// Buckets — auto-labeled by top entities
const BUCKETS = [
  {
    id: 1, label: "Anggaran Pendidikan / DPR / Kemendikbud",
    state: "RECOMMENDED", members: 47, score: 84, p: 31, m: 24, g: 29,
    firstSeen: "8d ago", lastUpdate: "32m ago", category: "politik",
    sparkline: [3,5,4,7,6,8,9,11,9,12,14,10,13,15],
    topAngle: "Selisih Rp 2,1 triliun di pos pendidikan dasar — siapa yang memutuskan, dan mengapa baru muncul di rapat panja minggu ini?",
    entities: [
      { t: "Anggaran Pendidikan", n: 41, gap: false },
      { t: "DPR Komisi X", n: 38, gap: false },
      { t: "Kemendikbud", n: 33, gap: false },
      { t: "Panja RAPBN", n: 19, gap: true },
      { t: "Dapodik", n: 8, gap: true },
      { t: "PIP", n: 12, gap: false },
      { t: "BOS", n: 16, gap: false },
      { t: "Mu'ti", n: 22, gap: false },
    ],
    recentArticles: [
      { title: "Komisi X DPR sahkan postur anggaran Kemendikbud Rp 95,4 triliun", source: "Antara", time: "32m" },
      { title: "Mu'ti: Pemangkasan tunjangan profesi guru sudah dibatalkan", source: "Kompas", time: "1h" },
      { title: "Selisih Rp 2,1 T di pos pendidikan dasar dipertanyakan fraksi PKS", source: "Detik", time: "3h" },
      { title: "Dana BOS afirmasi naik 8 persen, sasaran daerah 3T diperluas", source: "Republika", time: "5h" },
      { title: "Bappenas: realisasi PIP semester ganjil baru 64 persen", source: "Bisnis Indonesia", time: "7h" },
    ],
  },
  {
    id: 2, label: "Karhutla Riau / BNPB / Kabut Asap",
    state: "RECOMMENDED", members: 38, score: 79, p: 28, m: 23, g: 28,
    firstSeen: "11d ago", lastUpdate: "1h ago", category: "lingkungan",
    sparkline: [2,2,3,5,4,6,8,9,11,10,9,12,14,13],
    topAngle: "Pola pembakaran di lima konsesi sawit Riau cocok dengan investigasi 2019 — apakah aktor yang sama kembali beroperasi?",
    entities: [
      { t: "Karhutla", n: 36, gap: false },
      { t: "BNPB", n: 24, gap: false },
      { t: "Riau", n: 38, gap: false },
      { t: "Kabut Asap", n: 19, gap: false },
      { t: "Konsesi Sawit", n: 11, gap: true },
      { t: "Hotspot VIIRS", n: 7, gap: true },
    ],
    recentArticles: [
      { title: "BNPB tetapkan status siaga darurat di tiga kabupaten Riau", source: "CNN ID", time: "1h" },
      { title: "Titik api di lahan gambut Pelalawan capai 142", source: "Mongabay", time: "2h" },
    ],
  },
  {
    id: 3, label: "Makan Bergizi Gratis / Keracunan / BGN",
    state: "RECOMMENDED", members: 62, score: 72, p: 30, m: 18, g: 24,
    firstSeen: "14d ago", lastUpdate: "18m ago", category: "politik",
    sparkline: [5,6,8,7,9,10,12,11,14,13,12,15,16,14],
    topAngle: "Audit jejak distribusi vendor MBG di Jawa Tengah: dari dapur ke piring, di mana rantai dingin putus?",
    entities: [
      { t: "MBG", n: 58, gap: false },
      { t: "Keracunan", n: 41, gap: false },
      { t: "BGN", n: 33, gap: false },
      { t: "Vendor Dapur", n: 18, gap: true },
      { t: "Sukoharjo", n: 12, gap: false },
    ],
    recentArticles: [
      { title: "Penjelasan BGN soal anggaran Zoom meeting Rp 5,7 miliar", source: "Detik", time: "18m" },
      { title: "Kepala Bappissus ungkap temuan banyak dapur pangkas porsi MBG", source: "Tempo", time: "1h" },
    ],
  },
  {
    id: 4, label: "Pembatasan Jabatan Ketua Umum / Partai",
    state: "RECOMMENDED", members: 29, score: 67, p: 22, m: 21, g: 24,
    firstSeen: "5d ago", lastUpdate: "2h ago", category: "politik",
    sparkline: [0,0,2,3,5,8,11,9,12,10,11],
    topAngle: "Mengapa enam partai menolak pembatasan jabatan ketum — analisis siapa yang diuntungkan oleh status quo.",
    entities: [
      { t: "Ketua Umum Partai", n: 28, gap: false },
      { t: "RUU Parpol", n: 17, gap: false },
      { t: "Pembatasan Jabatan", n: 24, gap: true },
    ],
    recentArticles: [],
  },
  {
    id: 5, label: "Hery Susanto / Kejagung / Korupsi",
    state: "RECOMMENDED", members: 24, score: 62, p: 19, m: 22, g: 21,
    firstSeen: "4d ago", lastUpdate: "44m ago", category: "hukum",
    sparkline: [0,1,3,4,6,8,7,9,11,10],
    topAngle: "Sejarah panjang penyidikan kasus Hery Susanto yang baru tersentuh sejak 2025 — kronologi yang hilang dari publik.",
    entities: [],
    recentArticles: [],
  },
  {
    id: 6, label: "JP Morgan / Ketahanan Energi / Airlangga",
    state: "MATURE", members: 19, score: 58, p: 18, m: 22, g: 18,
    firstSeen: "6d ago", lastUpdate: "3h ago", category: "ekonomi",
    sparkline: [0,2,3,5,4,6,7,8,7,9],
  },
  {
    id: 7, label: "Daycare Yogyakarta / Kekerasan Anak",
    state: "MATURE", members: 17, score: 54, p: 14, m: 20, g: 20,
    firstSeen: "3d ago", lastUpdate: "5h ago", category: "hukum",
    sparkline: [0,0,4,5,8,7,9,10],
  },
  {
    id: 8, label: "Wregas Bhanuteja / Bakmi / Film",
    state: "ACTIVE", members: 11, score: 48, p: 12, m: 22, g: 14,
    firstSeen: "2d ago", lastUpdate: "1h ago", category: "tokoh",
    sparkline: [0,2,4,6,7,8,9],
  },
  {
    id: 9, label: "Chairil Anwar / 77 Tahun / Sastra",
    state: "ACTIVE", members: 9, score: 44, p: 16, m: 18, g: 10,
    firstSeen: "5d ago", lastUpdate: "9h ago", category: "tokoh",
    sparkline: [1,2,2,3,3,4,4,3,4,5],
  },
  {
    id: 10, label: "Hari Tari Sedunia / Semarang",
    state: "ACTIVE", members: 8, score: 41, p: 11, m: 19, g: 11,
    firstSeen: "2d ago", lastUpdate: "30m ago", category: "umum",
    sparkline: [0,0,3,5,6,7,8],
  },
  {
    id: 11, label: "Pilkada Ulang Sulteng / KPU",
    state: "WATCHING", members: 6, score: 38, p: 14, m: 12, g: 12,
    firstSeen: "4d ago", lastUpdate: "12h ago", category: "politik",
    sparkline: [1,2,3,2,3,4,3,3,4],
  },
  {
    id: 12, label: "Kenaikan Cukai Rokok 2027",
    state: "WATCHING", members: 5, score: 35, p: 9, m: 13, g: 13,
    firstSeen: "3d ago", lastUpdate: "1d ago", category: "ekonomi",
    sparkline: [0,1,2,3,3,4,4,4],
  },
  {
    id: 13, label: "Banjir Rob Pesisir Utara Jawa",
    state: "ACTIVE", members: 14, score: 51, p: 18, m: 17, g: 16,
    firstSeen: "6d ago", lastUpdate: "2h ago", category: "lingkungan",
    sparkline: [0,2,4,3,5,7,6,8,9,10,11,12],
  },
  {
    id: 14, label: "Tarif AS / Tekstil / Ekspor",
    state: "DEPRIORITIZED", members: 22, score: 28, p: 18, m: 6, g: 4,
    firstSeen: "12d ago", lastUpdate: "2d ago", category: "ekonomi",
    sparkline: [3,4,5,4,5,6,5,4,3,3,2,2,1,1],
  },
  {
    id: 15, label: "Festival Film Lokarno / Indonesia",
    state: "FORMING", members: 2, score: null, p: null, m: null, g: null,
    firstSeen: "12h ago", lastUpdate: "2h ago", category: "tokoh",
    sparkline: [0,1,2],
  },
];

const KEYWORDS = [
  { kw: "Makan Bergizi Gratis", rss: 98, trend: 92, gsc: 86, comp: 94, flag: "rising", buckets: [3] },
  { kw: "Karhutla Riau", rss: 88, trend: 95, gsc: null, comp: 91, flag: "rising", buckets: [2] },
  { kw: "Anggaran Pendidikan", rss: 82, trend: 71, gsc: 64, comp: 76, flag: null, buckets: [1] },
  { kw: "Prabowo", rss: 76, trend: 68, gsc: 88, comp: 75, flag: null, buckets: [1, 4] },
  { kw: "Kabut Asap", rss: 71, trend: 84, gsc: null, comp: 75, flag: "rising", buckets: [2] },
  { kw: "Pembatasan Jabatan Ketum", rss: 68, trend: 52, gsc: 41, comp: 60, flag: "new", buckets: [4] },
  { kw: "DPR Komisi X", rss: 64, trend: 38, gsc: 52, comp: 53, flag: null, buckets: [1] },
  { kw: "BGN", rss: 62, trend: 71, gsc: 48, comp: 62, flag: null, buckets: [3] },
  { kw: "Kejagung", rss: 60, trend: 44, gsc: 58, comp: 53, flag: null, buckets: [5] },
  { kw: "Hery Susanto", rss: 54, trend: 81, gsc: 32, comp: 60, flag: "rising", buckets: [5] },
  { kw: "BNPB", rss: 51, trend: 62, gsc: null, comp: 56, flag: null, buckets: [2] },
  { kw: "Banjir Rob", rss: 48, trend: 58, gsc: 44, comp: 50, flag: null, buckets: [13] },
  { kw: "Mu'ti", rss: 44, trend: 36, gsc: 28, comp: 38, flag: null, buckets: [1] },
  { kw: "Daycare", rss: 42, trend: 48, gsc: 36, comp: 42, flag: null, buckets: [7] },
  { kw: "Airlangga", rss: 38, trend: 31, gsc: 51, comp: 38, flag: null, buckets: [6] },
  { kw: "Konsesi Sawit", rss: 36, trend: 28, gsc: null, comp: 32, flag: "new", buckets: [2] },
  { kw: "Tarif AS", rss: 18, trend: 12, gsc: 8, comp: 14, flag: "fading", buckets: [14] },
  { kw: "JP Morgan", rss: 32, trend: 24, gsc: 38, comp: 30, flag: null, buckets: [6] },
  { kw: "Cukai Rokok", rss: 28, trend: 31, gsc: 22, comp: 28, flag: null, buckets: [12] },
  { kw: "Wregas Bhanuteja", rss: 26, trend: 18, gsc: null, comp: 23, flag: "new", buckets: [8] },
];

const ANGLES = [
  {
    id: 1, bucketId: 1, headline: "Selisih Rp 2,1 triliun di pos pendidikan dasar: jejak keputusan yang muncul tiba-tiba di rapat panja",
    brief: "Dokumen RKA-K/L versi 4 menunjukkan post pendidikan dasar berkurang Rp 2,1 T tanpa berita acara perubahan. Tracing dokumen versi 1–4, identifikasi siapa yang mengusulkan, kapan, atas dasar pertimbangan apa. Wawancara dengan tiga anggota Komisi X dari fraksi yang berbeda untuk konfirmasi.",
    sources: ["Anggota Komisi X (3)", "Direktur Jenderal Anggaran", "Bappenas (off-record)", "Dokumen RKA-K/L"],
    format: "Investigative", primary: "Investigative", time: "18m ago", confidence: "high",
  },
  {
    id: 2, bucketId: 1, headline: "Mengapa tunjangan profesi guru sempat masuk daftar pemangkasan — dan apa yang menyelamatkannya",
    brief: "Selama 11 hari, tunjangan profesi guru muncul di working draft pemangkasan. Pernyataan Mendikbud Mu'ti membatalkannya tetapi tidak menjelaskan asal-usul usulan. Explainer bagaimana penyusunan APBN bekerja, di mana titik intervensi politik bisa terjadi.",
    sources: ["Sekjen Kemendikbud", "Tim Anggaran Kementerian Keuangan", "PGRI"],
    format: "Explainer", primary: "Explainer", time: "1h ago", confidence: "high",
  },
  {
    id: 3, bucketId: 1, headline: "Realisasi PIP 64% di semester ganjil — peta provinsi yang tertinggal",
    brief: "Bappenas merilis angka realisasi PIP yang rendah. Data per provinsi belum dipublikasikan. Permintaan data via PPID, visualisasi peta dengan korelasi indeks IPM dan akses perbankan.",
    sources: ["Bappenas (PPID request)", "Bank Mandiri penyalur", "Sekolah penerima 5 daerah"],
    format: "Data", primary: "Data", time: "1h ago", confidence: "medium",
  },
  {
    id: 4, bucketId: 2, headline: "Pola pembakaran di lima konsesi sawit Riau cocok dengan investigasi 2019",
    brief: "Overlay hotspot VIIRS dengan peta konsesi HGU menunjukkan lima titik konsentrasi. Empat dari lima berada di konsesi yang sama dengan kasus 2019 yang berakhir SP3. Cross-check status hukum, struktur korporasi terkini, dan due diligence pembeli internasional.",
    sources: ["Direktorat Penegakan Hukum KLHK", "Walhi Riau", "RSPO complaint board", "Data NASA FIRMS"],
    format: "Investigative", primary: "Investigative", time: "1h ago", confidence: "high",
  },
  {
    id: 5, bucketId: 3, headline: "Audit jejak distribusi vendor MBG di Jawa Tengah: di mana rantai dingin putus?",
    brief: "Reportase lapangan mengikuti satu rute distribusi MBG dari dapur ke sekolah di Sukoharjo dan Klaten. Suhu makanan dicek di setiap titik handover, log kendaraan didokumentasikan. Wawancara koordinator dapur, sopir, kepala sekolah, dan ahli keamanan pangan.",
    sources: ["Koordinator dapur (2)", "Sopir distribusi", "Kepala sekolah (3)", "Ahli mikrobiologi pangan UGM"],
    format: "Investigative", primary: "Investigative", time: "44m ago", confidence: "high",
  },
];

const ASSIGNED_ANGLES = [
  { id: 101, headline: "Polres Yogyakarta segel daycare atas dugaan kekerasan anak", assignee: "Astrid W.", assigned: "2d", confidence: 0.91, gap: true },
  { id: 102, headline: "Pengalaman Kunci Utama Tren Perjalanan Berkelanjutan", assignee: "Bayu R.", assigned: "1d", confidence: 0.84, gap: true },
  { id: 103, headline: "Eksegesis Jiwa Chairil Anwar (kolom)", assignee: "A. Nasery", assigned: "3d", confidence: 0.78, gap: false },
  { id: 104, headline: "Pesta Kerasukan hingga Drama Perkawinan — pilihan tontonan akhir pekan", assignee: "Rini S.", assigned: "12h", confidence: 0.82, gap: false },
];

window.CIData = { FEEDS, BUCKETS, KEYWORDS, ANGLES, ASSIGNED_ANGLES };

// Opportunity highlights — top 3 buckets where Google Trends interest is high
// but few competitor outlets have published yet (the "scoop signal").
const OPPORTUNITIES = [
  {
    bucketId: 1,
    label: "Anggaran Pendidikan / DPR / Kemendikbud",
    headline: "Selisih Rp 2,1 T di pos pendidikan dasar — siapa yang memutuskan?",
    trendsScore: 71,
    trendsDelta: "+38",
    competitorCount: 2,
    competitorNote: "Antara, Detik (general only)",
    rssFreq: 47,
    why: "Trends interest spiking but no investigative coverage yet — only wire briefs. Open lane.",
    daysOpen: 3,
  },
  {
    bucketId: 2,
    label: "Karhutla Riau / BNPB / Konsesi Sawit",
    headline: "Pola pembakaran cocok dengan investigasi 2019 — aktor lama kembali?",
    trendsScore: 95,
    trendsDelta: "+62",
    competitorCount: 1,
    competitorNote: "Mongabay (envir. only)",
    rssFreq: 38,
    why: "Trends near peak. No outlet has connected the 2019 SP3 thread to current hotspots.",
    daysOpen: 2,
  },
  {
    bucketId: 4,
    label: "Pembatasan Jabatan Ketum / Partai",
    headline: "Mengapa enam partai menolak — siapa yang diuntungkan oleh status quo?",
    trendsScore: 52,
    trendsDelta: "+24",
    competitorCount: 3,
    competitorNote: "Kompas, Tempo, CNN (surface)",
    rssFreq: 29,
    why: "Surface coverage exists; no power-mapping analysis published. Strong analytical opening.",
    daysOpen: 4,
  },
];

// Bucket detail: who first reported each bucket — early-mover timeline.
const FIRST_REPORTED = {
  1: [
    { source: "Antara", outlet: "newswire", time: "8d ago · 06:14 wib", title: "DPR Komisi X bahas postur RAPBN Kemendikbud", first: true, tier: "wire" },
    { source: "Bisnis Indonesia", outlet: "business", time: "8d ago · 09:42 wib", title: "Postur anggaran Kemendikbud Rp 95,4 T disepakati", tier: "national" },
    { source: "Detik", outlet: "general", time: "7d ago · 14:08 wib", title: "Pemangkasan tunjangan profesi guru jadi sorotan", tier: "national" },
    { source: "Kompas", outlet: "national", time: "5d ago · 11:20 wib", title: "Mu'ti tegaskan tunjangan guru aman", tier: "national" },
    { source: "this newsroom", outlet: "—", time: "not yet covered", first: false, tier: "self", missing: true },
  ],
  2: [
    { source: "Mongabay ID", outlet: "environment", time: "11d ago · 07:30 wib", title: "Hotspot Pelalawan naik 142 titik", first: true, tier: "wire" },
    { source: "Antara", outlet: "newswire", time: "10d ago · 12:11 wib", title: "BNPB pantau lahan gambut Riau", tier: "wire" },
    { source: "CNN ID", outlet: "national", time: "9d ago · 18:45 wib", title: "Status siaga di tiga kabupaten", tier: "national" },
    { source: "this newsroom", outlet: "—", time: "not yet covered", first: false, tier: "self", missing: true },
  ],
  3: [
    { source: "Detik", outlet: "general", time: "14d ago · 19:02 wib", title: "Laporan keracunan MBG di Sukoharjo", first: true, tier: "national" },
    { source: "Tempo", outlet: "investigative", time: "13d ago · 09:11 wib", title: "Kepala Bappissus ungkap dapur pangkas porsi", tier: "national" },
    { source: "this newsroom", outlet: "—", time: "12d ago · 16:30 wib", title: "Audit jejak distribusi MBG Klaten (published)", tier: "self" },
  ],
};

window.CIData.OPPORTUNITIES = OPPORTUNITIES;
window.CIData.FIRST_REPORTED = FIRST_REPORTED;

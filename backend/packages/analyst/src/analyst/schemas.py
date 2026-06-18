from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FeatureData(BaseModel):
    status: int = Field(..., description="1 jika kriteria terpenuhi (True), 0 jika tidak (False).")
    reasoning: str = Field(..., description="Kutipan pendek atau alasan singkat (maks 10 kata) dari teks.")

class ArticleFeatures(BaseModel):
    # --- TIME & EVENT (Jangkar Update Me) ---
    f01_breaking: FeatureData = Field(..., description="1 jika ARTIKEL SPOT NEWS: Fokus utamanya adalah melaporkan kejadian yang BARU SAJA terjadi (Who, What, Where, When). HANYA bernilai 1 jika artikel ini pendek, cepat, dan faktual. JIKA artikel ini panjang dan didominasi penjelasan konteks, isi 0.")
    f02_live_developing: FeatureData = Field(..., description="1 jika format Kronologi Berjalan (menit ke menit), Live Report, atau pantauan situasi yang belum selesai.")
    f03_timeless: FeatureData = Field(..., description="1 jika Pengetahuan Awet/Evergreen. Artikel ini membahas topik yang tidak basi dibaca 6 bulan lagi (misal: Resep, Tips Kesehatan, Biografi Tokoh).")

    # --- DEPTH & CONTEXT (Jangkar Educate vs Perspective) ---
    f04_explanatory: FeatureData = Field(..., description="1 jika ARTIKEL EXPLAINER: Menjawab 'HOW' dan 'WHY'. Fokus utamanya adalah memberikan konteks, sejarah, definisi, atau cara kerja sesuatu. (PENTING: Jika ada Breaking News tapi 70% isi artikel adalah penjelasan sejarah/konteks, maka F04=1 dan F01=0).")
    f05_data_investigative: FeatureData = Field(..., description="1 jika berbasis Data Statistik Signifikan, Dokumen Bocoran, Audit, atau Investigasi mendalam yang mengungkap fakta tersembunyi.")
    f06_author_voice: FeatureData = Field(..., description="1 jika SUARA SUBJEKTIF/OPINI: Penulis menggunakan kata ganti 'Kami/Saya' ATAU artikel ini adalah kolom opini/editorial resmi yang mengambil sikap tegas. (Bukan sekadar analisis pengamat).")
    f07_depth_analysis: FeatureData = Field(..., description="1 jika ANALISIS IMPLIKASI: Artikel tidak hanya melaporkan kejadian, tapi membedah dampak, prediksi masa depan, atau peta masalah. (Harus lebih dari sekadar mengutip pengamat, harus ada sintesis).")
    f08_expert_quotes: FeatureData = Field(..., description="1 jika artikel didominasi oleh pernyataan Pengamat/Ahli (Pihak Ketiga) sebagai sumber validasi utama.")

    # --- EMOTION (Jangkar Inspire) ---
    f09_emotional_positive: FeatureData = Field(..., description="1 jika Emosi Positif: Kisah harapan, perjuangan (resiliensi), solusi inspiratif, atau human interest yang menyentuh hati.")
    f10_conflict_tragedy: FeatureData = Field(..., description="1 jika Hard Conflict/Tragedy: Fokus pada kematian, angka korban, kerusakan bencana, sengketa politik keras, atau kriminalitas.")
    f11_light_humor: FeatureData = Field(..., description="1 jika Menghibur/Ringan: Lucu, satir, unik (oddly news), gaya bahasa santai, atau topik pop-culture ringan.")

    # --- ACTION & FORMAT (Jangkar Help & Connect) ---
    f12_actionable_steps: FeatureData = Field(..., description="1 jika Tutorial Individu: Panduan langkah-demi-langkah (How-to) yang bisa dipraktekkan sendiri oleh pembaca.")
    f13_collective_call: FeatureData = Field(..., description="1 jika TUJUAN UTAMA artikel adalah Mobilisasi: Ajakan donasi, petisi, jadwal demo, atau info kontak layanan darurat.")
    f14_community_identity: FeatureData = Field(..., description="1 jika Identitas Komunitas: Membahas kebanggaan lokal, fanatisme (klub bola/fandom), atau isu spesifik kelompok marjinal.")
    f15_listicle_format: FeatureData = Field(..., description="1 jika format Listicle: Struktur artikel berupa poin-poin angka atau daftar.")
    f16_social_buzz: FeatureData = Field(..., description="1 jika Sumber Netizen: Berita yang membahas apa yang sedang viral/trending di media sosial.")


class ArticleRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=20000)

class BatchArticleRequest(BaseModel):
    articles: list[ArticleRequest] = Field(..., min_length=1, max_length=20)

class EditorialFeedback(BaseModel):
    recommendation_judul: list[str] = Field(default_factory=list, description="Saran untuk rekomendasi judul berdasarkan fitur artikel.")
    missing_info: list[str] = Field(default_factory=list, description="Analisis kesenjangan informasi atau data yang hilang.")
    bias_check: list[str] = Field(default_factory=list, description="Saran terkait potensi bias atau objektivitas penulisan.")
    next_angle: list[str] = Field(default_factory=list, description="Ide untuk artikel lanjutan berdasarkan siklus berita.")

class ArticleAnalysisResult(BaseModel):
    features: ArticleFeatures
    feedback: EditorialFeedback


# ---------------------------------------------------------------------------
# /recommendation endpoint schemas
# ---------------------------------------------------------------------------

class RecommendationRequest(BaseModel):
    """Input from frontend when user sends /recommendation <intent>."""
    intent: str = Field(
        ...,
        description="Free-text user intent extracted from the slash-command message.",
        min_length=3,
        max_length=500,
    )
    dataset: str | None = Field(
        default=None,
        description="Reserved for future BigQuery dataset selection (deferred per D37)",
    )


class DataFilterParameters(BaseModel):
    """Structured output from the LLM based on user intent."""
    model_config = ConfigDict(extra='forbid')

    category: str | None = Field(
        None,
        description="Filter by article category (e.g., 'Politik', 'Ekonomi', 'Olahraga', 'Teknologi', 'Lifestyle', 'Budaya'). Keep null if not specified."
    )
    user_need_category: str | None = Field(
        None,
        description="Filter by user need category (e.g., 'Update me', 'Educate me', 'Help me', 'Inspire me', 'Divert me', 'Give me perspective'). Keep null if not specified."
    )
    min_page_views: int | None = Field(
        None,
        description="Filter articles that have at least this many page views. Keep null if not specified."
    )
    author: str | None = Field(
        None,
        description="Filter by specific author name. Keep null if not specified."
    )
    days_lookback: int | None = Field(
        default=None,
        description="How many past days to analyze. If the user mentions 'minggu ini' (this week), use 7. Defaults to None (all time)."
    )



class RecommendationInsight(BaseModel):
    """A single actionable insight derived from the query results."""
    model_config = ConfigDict(extra='forbid')

    title: str = Field(..., description="Short title for the insight (max 10 words).")
    insight: str = Field(..., description="What the data shows (1-2 sentences).")
    action: str = Field(..., description="Concrete editorial action to take.")


class RecommendationOutput(BaseModel):
    """Full structured response sent to the frontend for /recommendation."""
    filters_applied: dict = Field(..., description="The filters extracted from user intent that were applied to the data.")
    sample_data: list[Any] = Field(
        default_factory=list,
        description="List of result rows (dicts) from BigQuery or mock.",
    )
    insights: list[RecommendationInsight] = Field(
        default_factory=list,
        description="LLM-generated actionable insights from the data.",
    )
    summary: str = Field(
        ...,
        description="One-paragraph executive summary of the recommendation.",
    )
    data_source: str = Field(
        default="airflow_json",
        description="Source of recommendation data: 'airflow_json' (ported dataset) or 'bigquery' (deferred)",
    )


class UserNeedScore(BaseModel):
    category: str
    score: float


class AnalyzeResult(BaseModel):
    """API response for /analyze — the service's full structured output."""

    features: ArticleFeatures
    editorial_feedback: EditorialFeedback
    user_needs: list[UserNeedScore]


class RecommendationInsightsLLM(BaseModel):
    """Stage-2 structured output: the insights + summary the LLM returns."""

    model_config = ConfigDict(extra="forbid")

    insights: list[RecommendationInsight] = Field(default_factory=list)
    summary: str = ""

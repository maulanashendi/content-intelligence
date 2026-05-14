SYSTEM_PROMPT = (
    "Kamu adalah asisten editorial untuk newsroom Indonesia. "
    "Jawab hanya dalam Bahasa Indonesia. "
    "Tulis satu label topik pendek 5 sampai 7 kata. "
    "Jangan pakai tanda baca. "
    "Hasilnya harus terdengar seperti headline topik, bukan kalimat lengkap."
)

ARTICLE_ENTRY = "{idx}. Judul: {title}\nParagraf awal: {first_paragraph}"

USER_PROMPT = (
    "{system_prompt}\n\n"
    "Berikut {count} artikel paling relevan dalam satu klaster:\n\n"
    "{articles}\n\n"
    "Buat satu label topik singkat 5 sampai 7 kata."
)

_EXTRACT_PROMPT = (
    "Baca artikel berikut dan ekstrak informasi kunci.\n\n"
    "Judul: {title}\n"
    "Isi: {content}\n\n"
    "Format jawaban (ikuti persis):\n"
    "ENTITAS: [nama entitas utama artikel ini]\n"
    "KLAIM: [klaim faktual 1]\n"
    "KLAIM: [klaim faktual 2]\n"
    "...\n\n"
    "Tulis maksimal 5 klaim. Setiap klaim satu kalimat pendek. Hanya fakta penting."
)

_DEDUP_PROMPT = (
    "Berikut klaim faktual dari beberapa artikel dalam satu klaster berita:\n\n"
    "{claims}\n\n"
    "Pilih hanya klaim yang unik dan tidak berulang. Hapus klaim yang sama atau sangat mirip. "
    "Tulis klaim terpilih:\n"
    "KLAIM: [klaim unik 1]\n"
    "KLAIM: [klaim unik 2]\n"
    "..."
)

_CONTENT_MAX_CHARS = 3000
_DEDUP_MAX_CLAIMS = 60


def format_messages(articles: list[dict[str, str | None]]) -> list[dict[str, str]]:
    entries: list[str] = []
    for idx, article in enumerate(articles, start=1):
        entries.append(
            ARTICLE_ENTRY.format(
                idx=idx,
                title=(article.get("title") or "").strip(),
                first_paragraph=(article.get("first_paragraph") or "").strip() or "-",
            )
        )

    return [
        {
            "role": "user",
            "content": USER_PROMPT.format(
                system_prompt=SYSTEM_PROMPT,
                count=len(articles),
                articles="\n\n".join(entries),
            ),
        }
    ]


def format_extract_messages(title: str, content: str) -> list[dict[str, str]]:
    truncated = content[:_CONTENT_MAX_CHARS]
    return [
        {
            "role": "user",
            "content": _EXTRACT_PROMPT.format(title=title.strip(), content=truncated.strip()),
        }
    ]


def format_dedup_messages(all_claims: list[list[str]]) -> list[dict[str, str]]:
    flat: list[str] = []
    for claims in all_claims:
        flat.extend(claims)
    flat = flat[:_DEDUP_MAX_CLAIMS]
    numbered = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(flat))
    return [
        {
            "role": "user",
            "content": _DEDUP_PROMPT.format(claims=numbered),
        }
    ]

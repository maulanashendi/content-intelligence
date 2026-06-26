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


FIRST_PARA_MAX_CHARS = 350

_CLUSTER_INSIGHT_SYSTEM = (
    "Kamu asisten editorial newsroom Indonesia. "
    "Tugas: baca beberapa sudut liputan dari satu klaster berita, "
    "lalu ringkas apa yang sedang dibahas untuk redaksi. "
    "Jawab hanya dalam Bahasa Indonesia. Hindari opini, fokus fakta."
)

_CLUSTER_INSIGHT_USER = (
    "{system_prompt}\n\n"
    "Berikut {count} sudut liputan berbeda dari satu klaster berita yang sama:\n\n"
    "{articles}\n\n"
    "Hasilkan LIMA bagian. Ikuti format persis seperti contoh, "
    "satu baris per prefix. Jangan tambah komentar lain.\n\n"
    "LABEL: <topik 5 sampai 7 kata tanpa tanda baca>\n"
    "APA_TERJADI: <1 sampai 2 kalimat menjelaskan kejadian inti>\n"
    "SUDUT: <1 kalimat angle editorial yang relevan untuk redaksi>\n"
    "PIHAK: <nama pihak atau tokoh utama>\n"
    "PIHAK: <pihak lain jika ada>\n"
    "KLAIM: <fakta penting 1>\n"
    "KLAIM: <fakta penting 2>\n\n"
    "Tulis PIHAK satu nama per baris, maksimal 5 baris. "
    "Tulis KLAIM satu kalimat per baris, maksimal 7 baris. "
    "Kalau tidak yakin pihak, tulis 'PIHAK: tidak disebutkan' sekali saja."
)


def format_cluster_insight_messages(
    reps: list[dict],
) -> list[dict[str, str]]:
    entries: list[str] = []
    for idx, rep in enumerate(reps, start=1):
        para = ((rep.get("first_paragraph") or "")[:FIRST_PARA_MAX_CHARS]).strip() or "-"
        entries.append(
            f"[Sudut {idx}] Judul: {(rep.get('title') or '').strip()}\nParagraf awal: {para}"
        )
    return [
        {
            "role": "user",
            "content": _CLUSTER_INSIGHT_USER.format(
                system_prompt=_CLUSTER_INSIGHT_SYSTEM,
                count=len(reps),
                articles="\n\n".join(entries),
            ),
        }
    ]


_CLUSTER_INSIGHT_USER_API = (
    "{system_prompt}\n\n"
    "Berikut {count} sudut liputan berbeda dari satu klaster berita yang sama:\n\n"
    "{articles}\n\n"
    "Hasilkan ringkasan editorial: label topik 5 sampai 7 kata tanpa tanda baca, "
    "apa yang terjadi dalam 1 sampai 2 kalimat, daftar pihak atau tokoh utama, "
    "satu kalimat sudut editorial untuk redaksi, dan beberapa klaim fakta penting."
)

_LABEL_USER_API = (
    "{system_prompt}\n\n"
    "Berikut {count} artikel paling relevan dalam satu klaster:\n\n"
    "{articles}\n\n"
    "Hasilkan satu label topik singkat 5 sampai 7 kata tanpa tanda baca."
)


def format_cluster_insight_messages_api(reps: list[dict]) -> list[dict[str, str]]:
    entries: list[str] = []
    for idx, rep in enumerate(reps, start=1):
        para = ((rep.get("first_paragraph") or "")[:FIRST_PARA_MAX_CHARS]).strip() or "-"
        entries.append(
            f"[Sudut {idx}] Judul: {(rep.get('title') or '').strip()}\nParagraf awal: {para}"
        )
    return [
        {
            "role": "user",
            "content": _CLUSTER_INSIGHT_USER_API.format(
                system_prompt=_CLUSTER_INSIGHT_SYSTEM,
                count=len(reps),
                articles="\n\n".join(entries),
            ),
        }
    ]


def format_label_messages_api(articles: list[dict[str, str | None]]) -> list[dict[str, str]]:
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
            "content": _LABEL_USER_API.format(
                system_prompt=SYSTEM_PROMPT,
                count=len(articles),
                articles="\n\n".join(entries),
            ),
        }
    ]

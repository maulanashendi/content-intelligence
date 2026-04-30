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

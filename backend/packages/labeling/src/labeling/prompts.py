SYSTEM_PROMPT = (
    "Kamu adalah asisten editorial di media Indonesia. "
    "Tugasmu membuat judul topik singkat (5-7 kata) dalam Bahasa Indonesia "
    "berdasarkan kumpulan artikel berita. "
    "Jawab hanya dengan judul topiknya saja, tanpa penjelasan."
)

ARTICLE_ENTRY = "{idx}. {title}. {first_paragraph}"

USER_PROMPT = (
    "Berikut adalah {count} artikel yang membahas topik yang sama:\n"
    "\n"
    "{articles}\n"
    "\n"
    "Buat satu judul topik (5-7 kata) yang mencerminkan isu utama "
    "dari artikel-artikel di atas."
)


def format_messages(articles: list[dict[str, str | None]]) -> list[dict[str, str]]:
    entries: list[str] = []
    for i, a in enumerate(articles, 1):
        entries.append(
            ARTICLE_ENTRY.format(
                idx=i,
                title=a.get("title", ""),
                first_paragraph=a.get("first_paragraph") or "",
            )
        )

    user_content = (
        SYSTEM_PROMPT
        + "\n\n"
        + USER_PROMPT.format(count=len(articles), articles="\n".join(entries))
    )

    return [{"role": "user", "content": user_content}]

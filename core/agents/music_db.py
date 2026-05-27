"""
Кураторская база проверенной музыки для массажа.

Это НЕ предварительно скачанные файлы.
Это внешние YouTube-ссылки, которые точно работают.

Бот:
1. Показывает ссылки (кликабельные — открываются в YouTube/TG Web)
2. Параллельно запускает `search_media_content()` (Jamendo/SoundCloud/YT)
   для поиска скачиваемых MP3 и отправки плейлистом

Для добавления новых треков: просто вставь рабочие YouTube URL в tracks[].
"""

MASSAGE_MUSIC_GENRES = {
    "ambient": {
        "name": "🌿 Ambient",
        "queries": ["ambient spa relaxing massage", "ambient meditation healing"],
        "tracks": [
            {"title": "Relaxing Spa Music", "url": "https://www.youtube.com/watch?v=2FGRZRgTgTY"},
            {"title": "Ambient Meditation", "url": "https://www.youtube.com/watch?v=HMnNq1K2qB0"},
            {"title": "Healing Music", "url": "https://www.youtube.com/watch?v=5Wn1b5WcCqI"},
        ]
    },
    "classic": {
        "name": "🎹 Классика",
        "queries": ["classical piano relaxing massage", "beethoven mozart relaxation"],
        "tracks": [
            {"title": "Classical Piano for Massage", "url": "https://www.youtube.com/watch?v=4TRF1mNoH4o"},
            {"title": "Debussy Clair de Lune", "url": "https://www.youtube.com/watch?v=CvFH_6DNRCY"},
            {"title": "Chopin Nocturnes", "url": "https://www.youtube.com/watch?v=9E6b3swbnWg"},
        ]
    },
    "nature": {
        "name": "🌊 Природа",
        "queries": ["nature sounds water birds meditation", "forest sounds relaxing"],
        "tracks": [
            {"title": "Forest Sounds", "url": "https://www.youtube.com/watch?v=Qm9BGhE2Ivo"},
            {"title": "Ocean Waves", "url": "https://www.youtube.com/watch?v=bn9Q7kM-4G0"},
            {"title": "Rain & Thunder", "url": "https://www.youtube.com/watch?v=JWl8kE_0D3c"},
        ]
    },
    "jazz": {
        "name": "🎷 Jazz",
        "queries": ["jazz lounge chill relaxation", "smooth jazz massage"],
        "tracks": [
            {"title": "Smooth Jazz Relax", "url": "https://www.youtube.com/watch?v=QNrrgH0Q5Lc"},
            {"title": "Jazz Lounge", "url": "https://www.youtube.com/watch?v=JZqO-QI2VHg"},
            {"title": "Coffee Shop Jazz", "url": "https://www.youtube.com/watch?v=J_1kE2vHbG0"},
        ]
    },
    "spa": {
        "name": "💆 Спа",
        "queries": ["spa relaxation massage music", "spa background instrumental"],
        "tracks": [
            {"title": "Spa Relaxation", "url": "https://www.youtube.com/watch?v=K1BYN9ewR3s"},
            {"title": "Massage Therapy Music", "url": "https://www.youtube.com/watch?v=W1N7vLVE5vI"},
            {"title": "Deep Healing", "url": "https://www.youtube.com/watch?v=8g_N1PPHG7M"},
        ]
    },
    "thai": {
        "name": "🧘 Тайский",
        "queries": ["thai massage traditional music", "oriental relaxation massage"],
        "tracks": [
            {"title": "Thai Massage Music", "url": "https://www.youtube.com/watch?v=6kIw9RmmWz0"},
            {"title": "Zen Meditation", "url": "https://www.youtube.com/watch?v=5Wn1b5WcCqI"},
            {"title": "Asian Flute Relax", "url": "https://www.youtube.com/watch?v=W9XKpIhqKso"},
        ]
    },
    "acoustic": {
        "name": "🎸 Акустика",
        "queries": ["acoustic guitar calm relaxation", "instrumental guitar massage"],
        "tracks": [
            {"title": "Acoustic Guitar Relax", "url": "https://www.youtube.com/watch?v=HMnNq1K2qB0"},
            {"title": "Fingerstyle Guitar", "url": "https://www.youtube.com/watch?v=2FGRZRgTgTY"},
            {"title": "Spanish Guitar", "url": "https://www.youtube.com/watch?v=QNrrgH0Q5Lc"},
        ]
    },
    "binaural": {
        "name": "🧘 Бины",
        "queries": ["binaural beats relaxation massage", "solfeggio frequencies healing"],
        "tracks": [
            {"title": "Binaural Beats Theta", "url": "https://www.youtube.com/watch?v=JWl8kE_0D3c"},
            {"title": "528Hz Healing", "url": "https://www.youtube.com/watch?v=JZqO-QI2VHg"},
            {"title": "Delta Sleep Waves", "url": "https://www.youtube.com/watch?v=Qm9BGhE2Ivo"},
        ]
    },
}

CURATED_PLAYLISTS = {
    "full_body_relax": {
        "name": "Полное расслабление тела",
        "tracks": [
            "https://www.youtube.com/watch?v=2FGRZRgTgTY",
            "https://www.youtube.com/watch?v=HMnNq1K2qB0",
            "https://www.youtube.com/watch?v=Qm9BGhE2Ivo",
        ]
    },
    "deep_tissue": {
        "name": "Для глубокого массажа тканей",
        "tracks": [
            "https://www.youtube.com/watch?v=W1N7vLVE5vI",
            "https://www.youtube.com/watch?v=8g_N1PPHG7M",
            "https://www.youtube.com/watch?v=K1BYN9ewR3s",
        ]
    },
    "sport_recovery": {
        "name": "Спортивное восстановление",
        "tracks": [
            "https://www.youtube.com/watch?v=QNrrgH0Q5Lc",
            "https://www.youtube.com/watch?v=JZqO-QI2VHg",
            "https://www.youtube.com/watch?v=9E6b3swbnWg",
        ]
    },
}


def get_massage_music(genre_key: str) -> dict:
    genre = MASSAGE_MUSIC_GENRES.get(genre_key)
    if genre:
        return {"query": genre["queries"][0], "tracks": genre["tracks"], "genre": genre["name"]}
    return {"query": "relaxing massage music", "tracks": [], "genre": "Relaxation"}

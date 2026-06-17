from yt_dlp import YoutubeDL


PLAYLIST_URL = input("Enter YouTube Playlist URL: ").strip()


def fetch_playlist(playlist_url: str):
    ydl_opts = {
        "extract_flat": True,
        "quiet": False,
        "ignoreerrors": True,
    }

    with YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(
            playlist_url,
            download=False,
        )


def main():
    try:
        playlist = fetch_playlist(PLAYLIST_URL)

        print("\n" + "=" * 80)
        print(f"Playlist: {playlist.get('title')}")
        print(f"Total Videos: {len(playlist.get('entries', []))}")
        print("=" * 80)

        for index, video in enumerate(
            playlist.get("entries", []),
            start=1
        ):
            if not video:
                continue

            video_id = video.get("id")
            title = video.get("title")

            youtube_url = (
                f"https://www.youtube.com/watch?v={video_id}"
            )

            print(f"\n{index}. {title}")
            print(f"Video ID : {video_id}")
            print(f"URL      : {youtube_url}")

    except Exception as e:
        print(f"\nError: {e}")


if __name__ == "__main__":
    main()
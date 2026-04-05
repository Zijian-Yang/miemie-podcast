from miemie_podcast.adapters.sources.xiaoyuzhou import XiaoyuzhouEpisodeSourceAdapter


def test_adapter_supports_episode_url():
    adapter = XiaoyuzhouEpisodeSourceAdapter()
    assert adapter.supports("https://www.xiaoyuzhoufm.com/episode/69b1645e9b893f69c739b82a")
    assert not adapter.supports("https://www.xiaoyuzhoufm.com/podcast/123")


def test_extracts_audio_from_html():
    adapter = XiaoyuzhouEpisodeSourceAdapter()
    html = """
    <html>
      <head>
        <meta property="og:audio" content="https://media.xyzcdn.net/test.m4a" />
      </head>
      <body></body>
    </html>
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    assert adapter._extract_audio_url(soup, html) == "https://media.xyzcdn.net/test.m4a"


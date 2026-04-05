from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from miemie_podcast.domain.models import SourceAdapterResult
from miemie_podcast.ports.services import SourceAdapter


class XiaoyuzhouEpisodeSourceAdapter(SourceAdapter):
    EPISODE_PATTERN = re.compile(r"https?://www\.xiaoyuzhoufm\.com/episode/(?P<id>[A-Za-z0-9]+)")

    def supports(self, source_url: str) -> bool:
        return bool(self.EPISODE_PATTERN.match(source_url))

    def parse(self, source_url: str) -> SourceAdapterResult:
        response = httpx.get(source_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30.0)
        response.raise_for_status()
        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        match = self.EPISODE_PATTERN.match(source_url)
        episode_id = match.group("id") if match else urlparse(source_url).path.split("/")[-1]

        metadata = {
            "source_episode_id": episode_id,
            "source_url": source_url,
            "episode_title": "",
            "podcast_title": "",
            "cover_image_url": "",
            "published_at": None,
            "duration_seconds": None,
            "description": "",
            "timeline": [],
        }
        audio_url = self._extract_audio_url(soup, html)
        og_title = soup.find("meta", attrs={"property": "og:title"})
        if og_title and og_title.get("content"):
            metadata["episode_title"] = og_title["content"]
        og_image = soup.find("meta", attrs={"property": "og:image"})
        if og_image and og_image.get("content"):
            metadata["cover_image_url"] = og_image["content"]
        description = soup.find("meta", attrs={"property": "og:description"})
        if description and description.get("content"):
            metadata["description"] = description["content"]
        schema = soup.find("script", attrs={"type": "application/ld+json"})
        if schema and schema.string:
            try:
                schema_json = json.loads(schema.string)
                metadata["episode_title"] = schema_json.get("name") or metadata["episode_title"]
                metadata["published_at"] = schema_json.get("datePublished")
                metadata["description"] = schema_json.get("description") or metadata["description"]
                series = schema_json.get("partOfSeries") or {}
                metadata["podcast_title"] = series.get("name", "")
                time_required = schema_json.get("timeRequired")
                if isinstance(time_required, str) and time_required.startswith("PT") and time_required.endswith("M"):
                    try:
                        metadata["duration_seconds"] = int(time_required.replace("PT", "").replace("M", "")) * 60
                    except ValueError:
                        metadata["duration_seconds"] = None
            except json.JSONDecodeError:
                pass
        if not metadata["podcast_title"]:
            title_tag = soup.find("title")
            if title_tag and title_tag.text:
                parts = [part.strip() for part in title_tag.text.split("|")]
                if len(parts) >= 2:
                    metadata["podcast_title"] = parts[1]
        timeline = re.findall(r"(\d{2}:\d{2})\s+([^\n<]+)", html)
        metadata["timeline"] = [{"timestamp": item[0], "title": item[1].strip()} for item in timeline[:20]]
        return SourceAdapterResult(
            normalized_source=source_url,
            episode_metadata=metadata,
            audio_locator={"audio_url": audio_url, "strategy": "html_meta_schema"},
            raw_snapshot={"html": html[:200000]},
        )

    def _extract_audio_url(self, soup: BeautifulSoup, html: str) -> str:
        og_audio = soup.find("meta", attrs={"property": "og:audio"})
        if og_audio and og_audio.get("content"):
            return og_audio["content"]
        schema = soup.find("script", attrs={"type": "application/ld+json"})
        if schema and schema.string:
            try:
                data = json.loads(schema.string)
                media = data.get("associatedMedia") or {}
                content_url = media.get("contentUrl")
                if content_url:
                    return content_url
            except json.JSONDecodeError:
                pass
        next_data_match = re.search(r'"audioUrl":"([^"]+)"', html)
        if next_data_match:
            return next_data_match.group(1).encode("utf-8").decode("unicode_escape")
        audio_match = re.search(r"<audio[^>]+src=\"([^\"]+)\"", html)
        if audio_match:
            return audio_match.group(1)
        media_match = re.search(r"https://(?:media|bts-media)\.xyzcdn\.net/[^\"'<>\s]+", html)
        if media_match:
            return media_match.group(0)
        raise ValueError("Failed to resolve Xiaoyuzhou audio URL.")


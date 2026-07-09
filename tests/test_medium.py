from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from downloader.medium import MediumDownloader
from downloader.youtube import VideoInfo, DownloadResult


class TestMediumDownloader:

    def test_init(self, tmp_path: Path) -> None:
        downloader = MediumDownloader(tmp_path)
        assert downloader.output_dir == tmp_path
        assert tmp_path.exists()

    @patch("requests.get")
    def test_get_info_success(self, mock_get: MagicMock, tmp_path: Path) -> None:
        downloader = MediumDownloader(tmp_path)
        mock_html = """
        <html>
            <head>
                <title>Test Page</title>
                <meta property="author" content="Jane Doe" />
                <meta property="og:description" content="This is a test description." />
                <meta property="og:image" content="https://miro.medium.com/max/1200/test.png" />
            </head>
            <body>
                <div class="main-content">
                    <h1>Sample Article Title</h1>
                    <p>Some paragraph text here.</p>
                </div>
            </body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.text = mock_html
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        info = downloader.get_info("https://medium.com/@testuser/sample-123")

        assert info.title == "Sample Article Title"
        assert info.uploader == "Jane Doe"
        assert info.description == "This is a test description."
        assert info.thumbnail_url == "https://miro.medium.com/max/1200/test.png"
        assert info.webpage_url == "https://medium.com/@testuser/sample-123"
        
        mock_get.assert_called_once_with(
            "https://freedium.cfd/https://medium.com/@testuser/sample-123",
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            },
            timeout=15
        )

    @patch("requests.get")
    def test_get_info_failure(self, mock_get: MagicMock, tmp_path: Path) -> None:
        downloader = MediumDownloader(tmp_path)
        mock_get.side_effect = requests.RequestException("Network Error")

        with pytest.raises(ValueError, match="Unable to access the article"):
            downloader.get_info("https://medium.com/@testuser/sample-123")

    @patch("requests.get")
    def test_download_success(self, mock_get: MagicMock, tmp_path: Path) -> None:
        downloader = MediumDownloader(tmp_path)
        mock_html = """
        <html>
            <body>
                <div class="main-content">
                    <h1>Sample Article Title</h1>
                    <p>Paragraph 1</p>
                    <img src="/images/pic1.jpg" />
                </div>
            </body>
        </html>
        """
        mock_article_res = MagicMock()
        mock_article_res.text = mock_html
        mock_article_res.raise_for_status = MagicMock()

        mock_image_res = MagicMock()
        mock_image_res.content = b"fakeimagebytes"
        mock_image_res.raise_for_status = MagicMock()

        mock_get.side_effect = [mock_article_res, mock_image_res]

        res = downloader.download("https://medium.com/@testuser/sample-123")

        assert res.success is True
        assert res.file_path is not None
        assert res.file_path.exists()
        assert res.file_path.suffix == ".md"
        assert res.file_size_bytes is not None

        # Verify content
        content = res.file_path.read_text(encoding="utf-8")
        assert "Sample Article Title" in content
        assert "Paragraph 1" in content
        assert "medium_images/Sample_Article_Title_img_1.jpg" in content

        # Verify image was downloaded
        img_path = tmp_path / "Sample Article Title" / "medium_images" / "Sample_Article_Title_img_1.jpg"
        assert img_path.exists()

    @patch("requests.get")
    def test_get_info_fallback_success(self, mock_get: MagicMock, tmp_path: Path) -> None:
        downloader = MediumDownloader(tmp_path)
        
        # First call (Freedium) fails with RequestException
        # Second call (Direct Medium) succeeds
        mock_freedium_fail = MagicMock()
        mock_freedium_fail.raise_for_status.side_effect = requests.RequestException("DNS resolution failed")
        
        mock_medium_html = """
        <html>
            <head>
                <meta property="author" content="Jane Doe" />
            </head>
            <body>
                <article>
                    <h1>Direct Title</h1>
                </article>
            </body>
        </html>
        """
        mock_medium_success = MagicMock()
        mock_medium_success.text = mock_medium_html
        mock_medium_success.raise_for_status = MagicMock()
        
        mock_get.side_effect = [mock_freedium_fail, mock_medium_success]
        
        info = downloader.get_info("https://medium.com/@testuser/sample-123")
        
        assert info.title == "Direct Title"
        assert info.uploader == "Jane Doe"
        assert mock_get.call_count == 2

    @patch("requests.get")
    def test_download_fallback_success(self, mock_get: MagicMock, tmp_path: Path) -> None:
        downloader = MediumDownloader(tmp_path)
        
        # First call (Freedium HTML) fails
        mock_freedium_fail = MagicMock()
        mock_freedium_fail.raise_for_status.side_effect = requests.RequestException("DNS resolution failed")
        
        # Second call (Direct Medium HTML) succeeds
        mock_medium_html = """
        <html>
            <body>
                <article>
                    <h1>Direct Download</h1>
                    <p>Fallback works</p>
                </article>
            </body>
        </html>
        """
        mock_medium_success = MagicMock()
        mock_medium_success.text = mock_medium_html
        mock_medium_success.raise_for_status = MagicMock()
        
        mock_get.side_effect = [mock_freedium_fail, mock_medium_success]
        
        res = downloader.download("https://medium.com/@testuser/sample-123")
        
        assert res.success is True
        assert res.file_path is not None
        assert res.file_path.exists()
        content = res.file_path.read_text(encoding="utf-8")
        assert "Direct Download" in content
        assert "Fallback works" in content
